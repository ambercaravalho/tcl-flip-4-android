#!/usr/bin/env python3
"""Patch T440W spi_lcd spi-max-frequency values in an Android DTBO image."""

import argparse
import os
import struct

DTBO_MAGIC = 0xD7B7AB1E
FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE = 1
FDT_END_NODE = 2
FDT_PROP = 3
FDT_NOP = 4
FDT_END = 9


def align4(value: int) -> int:
    return (value + 3) & ~3


def cstring(data: bytes, offset: int) -> str:
    end = data.index(0, offset)
    return data[offset:end].decode("utf-8", errors="replace")


def patch_fdt(blob: bytearray, new_hz: int) -> list[tuple[str, int]]:
    if len(blob) < 40 or struct.unpack_from(">I", blob, 0)[0] != FDT_MAGIC:
        raise ValueError("entry does not start with an FDT")
    (
        _,
        total_size,
        struct_off,
        strings_off,
        _,
        _,
        _,
        _,
        strings_size,
        struct_size,
    ) = struct.unpack_from(">10I", blob, 0)
    if total_size > len(blob):
        raise ValueError("FDT total size exceeds DTBO entry size")

    pos = struct_off
    struct_end = struct_off + struct_size
    strings_end = strings_off + strings_size
    if struct_end > total_size or strings_end > total_size:
        raise ValueError("FDT structure or strings block is out of range")

    nodes: list[str] = []
    changed: list[tuple[str, int]] = []
    while pos + 4 <= struct_end:
        token = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        if token == FDT_BEGIN_NODE:
            name = cstring(blob, pos)
            nodes.append(name)
            pos = align4(pos + len(name.encode("utf-8")) + 1)
        elif token == FDT_END_NODE:
            if not nodes:
                raise ValueError("unbalanced FDT_END_NODE")
            nodes.pop()
        elif token == FDT_PROP:
            length, name_offset = struct.unpack_from(">II", blob, pos)
            pos += 8
            value_offset = pos
            pos = align4(pos + length)
            name = cstring(blob, strings_off + name_offset)
            path = "/" + "/".join(part for part in nodes if part)
            if (
                name == "spi-max-frequency"
                and "spi_lcd@" in path
                and length == 4
            ):
                old_hz = struct.unpack_from(">I", blob, value_offset)[0]
                struct.pack_into(">I", blob, value_offset, new_hz)
                changed.append((path, old_hz))
        elif token == FDT_NOP:
            continue
        elif token == FDT_END:
            break
        else:
            raise ValueError(f"unknown FDT token {token:#x}")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("frequency_hz", type=int)
    parser.add_argument("output")
    args = parser.parse_args()
    if args.frequency_hz <= 0 or args.frequency_hz > 0xFFFFFFFF:
        parser.error("frequency_hz must fit in a positive u32")

    data = bytearray(open(args.input, "rb").read())
    if len(data) < 32:
        parser.error("input is too short for a DTBO header")
    (
        magic,
        total_size,
        header_size,
        entry_size,
        entry_count,
        entries_offset,
        _,
        _,
    ) = struct.unpack_from(">8I", data, 0)
    if magic != DTBO_MAGIC:
        parser.error(f"bad DTBO magic {magic:#x}")
    if total_size > len(data) or header_size < 32 or entry_size < 32:
        parser.error("invalid DTBO header")

    all_changes: list[tuple[int, str, int]] = []
    for index in range(entry_count):
        entry = entries_offset + index * entry_size
        if entry + 8 > total_size:
            parser.error("DTBO entry table is truncated")
        dt_size, dt_offset = struct.unpack_from(">II", data, entry)
        if dt_offset + dt_size > total_size:
            parser.error(f"DTBO entry {index} is out of range")
        blob = bytearray(data[dt_offset:dt_offset + dt_size])
        try:
            changes = patch_fdt(blob, args.frequency_hz)
        except ValueError as error:
            parser.error(f"entry {index}: {error}")
        if changes:
            data[dt_offset:dt_offset + dt_size] = blob
            all_changes.extend((index, path, old) for path, old in changes)

    if not all_changes:
        raise SystemExit("error: no spi_lcd spi-max-frequency properties found")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "wb") as output:
        output.write(data)

    for index, path, old_hz in all_changes:
        print(f"entry {index}: {path}: {old_hz} -> {args.frequency_hz} Hz")
    print(
        f"wrote {args.output} ({len(data)} bytes, "
        f"{len(all_changes)} properties patched)"
    )


if __name__ == "__main__":
    main()
