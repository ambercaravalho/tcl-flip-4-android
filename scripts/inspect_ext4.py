#!/usr/bin/env python3
"""Pure-Python seek-based ext4 filesystem inspector and file extractor.

Reads ext4 superblock, block group descriptors, inode tables, extent trees,
and directory entries using random-access seek() calls so files and directory
trees can be inspected or extracted in milliseconds on macOS/Linux without
root mount permissions or debugfs.

Usage:
    scripts/inspect_ext4.py <ext4.img> ls [path]
    scripts/inspect_ext4.py <ext4.img> find [subpath] [--pattern=GLOB]
    scripts/inspect_ext4.py <ext4.py> cat <path>
    scripts/inspect_ext4.py <ext4.img> dump <path_in_img> <host_output_path>
"""
import fnmatch
import os
import stat
import struct
import sys

EXT4_SUPER_MAGIC = 0xEF53
EXT4_EXTENTS_FL = 0x80000
EXT4_EXT_MAGIC = 0xF30A
ROOT_INO = 2


class Ext4Reader:
    def __init__(self, fh):
        self.fh = fh
        self.fh.seek(1024)
        sb = self.fh.read(1024)
        magic = struct.unpack_from("<H", sb, 0x38)[0]
        if magic != EXT4_SUPER_MAGIC:
            raise ValueError(f"not an ext4 image (magic={magic:#x})")

        self.inodes_count = struct.unpack_from("<I", sb, 0x00)[0]
        log_block_size = struct.unpack_from("<I", sb, 0x18)[0]
        self.block_size = 1024 << log_block_size
        self.blocks_per_group = struct.unpack_from("<I", sb, 0x20)[0]
        self.inodes_per_group = struct.unpack_from("<I", sb, 0x28)[0]
        self.inode_size = struct.unpack_from("<H", sb, 0x58)[0]
        self.feature_incompat = struct.unpack_from("<I", sb, 0x60)[0]
        # INCOMPAT_64BIT = 0x80
        self.is_64bit = bool(self.feature_incompat & 0x80)
        self.desc_size = struct.unpack_from("<H", sb, 0xFE)[0] if self.is_64bit else 32
        if self.desc_size < 32:
            self.desc_size = 32

        self.gdt_offset = 2048 if self.block_size == 1024 else self.block_size
        self._inode_table_cache = {}

    def _get_inode_table_block(self, bg_idx):
        if bg_idx in self._inode_table_cache:
            return self._inode_table_cache[bg_idx]
        self.fh.seek(self.gdt_offset + bg_idx * self.desc_size)
        desc = self.fh.read(self.desc_size)
        lo = struct.unpack_from("<I", desc, 0x08)[0]
        hi = struct.unpack_from("<I", desc, 0x28)[0] if (self.is_64bit and self.desc_size >= 64) else 0
        blk = lo | (hi << 32)
        self._inode_table_cache[bg_idx] = blk
        return blk

    def read_inode(self, ino):
        bg_idx = (ino - 1) // self.inodes_per_group
        idx_in_bg = (ino - 1) % self.inodes_per_group
        itable_blk = self._get_inode_table_block(bg_idx)
        offset = itable_blk * self.block_size + idx_in_bg * self.inode_size
        self.fh.seek(offset)
        raw = self.fh.read(self.inode_size)
        mode = struct.unpack_from("<H", raw, 0x00)[0]
        size_lo = struct.unpack_from("<I", raw, 0x04)[0]
        flags = struct.unpack_from("<I", raw, 0x20)[0]
        size_hi = struct.unpack_from("<I", raw, 0x6C)[0] if stat.S_ISREG(mode) or stat.S_ISDIR(mode) else 0
        size = size_lo | (size_hi << 32)
        i_block = raw[0x28:0x64]
        return {
            "ino": ino,
            "mode": mode,
            "size": size,
            "flags": flags,
            "i_block": i_block,
        }

    def _collect_extents(self, node_bytes):
        magic, entries, max_entries, depth, _ = struct.unpack_from("<HHHHI", node_bytes, 0)
        if magic != EXT4_EXT_MAGIC:
            raise ValueError(f"bad extent header magic {magic:#x}")
        result = []
        if depth == 0:
            for i in range(entries):
                ee_block, ee_len, ee_start_hi, ee_start_lo = struct.unpack_from(
                    "<IHHI", node_bytes, 12 + i * 12
                )
                uninit = False
                if ee_len > 32768:
                    ee_len -= 32768
                    uninit = True
                pblock = ee_start_lo | (ee_start_hi << 32)
                result.append((ee_block, ee_len, pblock, uninit))
        else:
            for i in range(entries):
                ei_block, ei_leaf_lo, ei_leaf_hi, _ = struct.unpack_from(
                    "<IIHH", node_bytes, 12 + i * 12
                )
                leaf_blk = ei_leaf_lo | (ei_leaf_hi << 32)
                self.fh.seek(leaf_blk * self.block_size)
                child = self.fh.read(self.block_size)
                result.extend(self._collect_extents(child))
        return result

    def read_inode_data(self, inode):
        size = inode["size"]
        mode = inode["mode"]
        if stat.S_ISLNK(mode) and size < 60 and not (inode["flags"] & EXT4_EXTENTS_FL):
            return inode["i_block"][:size]

        if not (inode["flags"] & EXT4_EXTENTS_FL):
            # Direct blocks (0..11) for non-extent inodes
            out = bytearray()
            for i in range(12):
                if len(out) >= size:
                    break
                blk = struct.unpack_from("<I", inode["i_block"], i * 4)[0]
                if blk == 0:
                    out.extend(b"\x00" * min(self.block_size, size - len(out)))
                else:
                    self.fh.seek(blk * self.block_size)
                    out.extend(self.fh.read(min(self.block_size, size - len(out))))
            return bytes(out[:size])

        extents = sorted(self._collect_extents(inode["i_block"]), key=lambda x: x[0])
        out = bytearray()
        cur_lblock = 0
        for ee_block, ee_len, pblock, uninit in extents:
            if ee_block > cur_lblock:
                hole_bytes = (ee_block - cur_lblock) * self.block_size
                out.extend(b"\x00" * min(hole_bytes, max(0, size - len(out))))
                cur_lblock = ee_block
            byte_len = ee_len * self.block_size
            to_read = min(byte_len, max(0, size - len(out)))
            if to_read <= 0:
                break
            if uninit:
                out.extend(b"\x00" * to_read)
            else:
                self.fh.seek(pblock * self.block_size)
                out.extend(self.fh.read(to_read))
            cur_lblock += ee_len
        if len(out) < size:
            out.extend(b"\x00" * (size - len(out)))
        return bytes(out[:size])

    def list_dir_inode(self, inode):
        if not stat.S_ISDIR(inode["mode"]):
            raise ValueError("not a directory")
        data = self.read_inode_data(inode)
        pos = 0
        entries = []
        while pos + 8 <= len(data):
            ino, rec_len, name_len, file_type = struct.unpack_from("<IHBB", data, pos)
            if rec_len == 0:
                break
            if ino != 0 and name_len > 0:
                name = data[pos + 8:pos + 8 + name_len].decode("utf-8", errors="replace")
                if name not in (".", ".."):
                    entries.append((name, ino, file_type))
            pos += rec_len
        return entries

    def resolve_path(self, path, follow_final_symlink=True):
        parts = [p for p in path.strip("/").split("/") if p]
        cur_ino = ROOT_INO
        visited = 0
        while parts:
            visited += 1
            if visited > 40:
                raise ValueError("symlink loop")
            inode = self.read_inode(cur_ino)
            if stat.S_ISLNK(inode["mode"]):
                target = self.read_inode_data(inode).decode("utf-8", errors="replace")
                target_parts = [p for p in target.strip("/").split("/") if p]
                if target.startswith("/"):
                    cur_ino = ROOT_INO
                parts = target_parts + parts
                continue
            name = parts.pop(0)
            entries = self.list_dir_inode(inode)
            match = next((e for e in entries if e[0] == name), None)
            if match is None:
                raise FileNotFoundError(f"path not found: {path} (missing '{name}')")
            cur_ino = match[1]

        inode = self.read_inode(cur_ino)
        if follow_final_symlink and stat.S_ISLNK(inode["mode"]):
            target = self.read_inode_data(inode).decode("utf-8", errors="replace")
            if target.startswith("/"):
                return self.resolve_path(target, follow_final_symlink=True)
        return inode

    def walk(self, start_path="/"):
        start_inode = self.resolve_path(start_path, follow_final_symlink=False)
        prefix = "/" + start_path.strip("/") if start_path.strip("/") else ""
        stack = [(prefix, start_inode)]
        while stack:
            cur_path, inode = stack.pop()
            entries = sorted(self.list_dir_inode(inode), key=lambda x: x[0])
            yield cur_path or "/", entries
            for name, ino, ftype in reversed(entries):
                # ftype == 2 is directory in ext4 dir_entry_2
                child_path = f"{cur_path}/{name}"
                if ftype == 2:
                    child_inode = self.read_inode(ino)
                    if stat.S_ISDIR(child_inode["mode"]):
                        stack.append((child_path, child_inode))


FTYPE_NAMES = {1: "f", 2: "d", 3: "c", 4: "b", 5: "p", 6: "s", 7: "l"}


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    img_path, cmd = argv[1], argv[2]
    with open(img_path, "rb") as fh:
        reader = Ext4Reader(fh)
        if cmd == "ls":
            target = argv[3] if len(argv) > 3 else "/"
            inode = reader.resolve_path(target)
            for name, ino, ftype in sorted(reader.list_dir_inode(inode), key=lambda x: x[0]):
                child = reader.read_inode(ino)
                tchar = FTYPE_NAMES.get(ftype, "?")
                extra = ""
                if ftype == 7:
                    extra = " -> " + reader.read_inode_data(child).decode("utf-8", errors="replace")
                print(f"{tchar} {child['mode'] & 0o7777:04o} {child['size']:>10}  {name}{extra}")
        elif cmd == "find":
            subpath = "/"
            pattern = None
            for a in argv[3:]:
                if a.startswith("--pattern="):
                    pattern = a.split("=", 1)[1]
                else:
                    subpath = a
            for dirpath, entries in reader.walk(subpath):
                for name, ino, ftype in entries:
                    full = f"{dirpath.rstrip('/')}/{name}"
                    if pattern is None or fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(full, pattern):
                        tchar = FTYPE_NAMES.get(ftype, "?")
                        print(f"{tchar} {full}")
        elif cmd == "cat":
            if len(argv) < 4:
                raise SystemExit("usage: inspect_ext4.py <img_path> cat <path>")
            inode = reader.resolve_path(argv[3])
            sys.stdout.buffer.write(reader.read_inode_data(inode))
        elif cmd == "dump":
            if len(argv) < 5:
                raise SystemExit("usage: inspect_ext4.py <img_path> dump <path_in_img> <host_output_path>")
            inode = reader.resolve_path(argv[3])
            data = reader.read_inode_data(inode)
            out_path = argv[4]
            # SECURITY-REVIEW: CLI tool creating output directory for user-specified output path
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as out:
                out.write(data)
            print(f"dumped {argv[3]} -> {out_path} ({len(data)} bytes)")
        else:
            raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
