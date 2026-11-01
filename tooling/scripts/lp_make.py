#!/usr/bin/env python3
"""Pure-Python Android liblp (super partition) metadata & image builder.

Supports two workflows for the TCL Flip 4 5G (T440W):

1. Surgical Slot-B Metadata Mode (`--surgical`):
   Keeps `odm_b`, `product_b`, `system_dlkm_b`, `system_ext_b`, `vendor_b`, and
   `vendor_dlkm_b` at their exact stock physical sectors in `super`, removes the
   dead VABC `-cow` extents, and maps the new Android `system_b` image into:
     - 1 contiguous extent at super sector 2568192 (if system_b <= 1,906,311,168 B / ~1.78 GiB),
       leaving stock `system` sectors 12288..1253208 completely untouched for instant rollback!
     - OR 2 contiguous extents (12288..1253208 + 2568192..) if system_b is up to 2,541,662,208 B (~2.37 GiB).
   Writes a 524,288-byte `super_meta.img` (to flash at super start LBA 3686400)
   and prints the exact `tooling/scripts/edl ws` commands for Phase 2.

2. Full Super Image Mode (`--full`):
   Packs a complete 3,221,225,472-byte (3,072 MiB) `super.img` with contiguous
   linear extents for all Slot B partitions.

Usage:
    tooling/scripts/lp_make.py --surgical --system <system_b_signed.img> --out-dir <dir>
        [--stock-meta artifacts/build/super_meta_live.img]
        [--product-size BYTES] [--system-ext-size BYTES] [--odm-size BYTES]

    tooling/scripts/lp_make.py --full --out <super-android.img>
        --odm <odm_b.img> --product <product_b.img> --system <system_b.img>
        --system-dlkm <system_dlkm_b.img> --system-ext <system_ext_b.img>
        --vendor <vendor_b.img> --vendor-dlkm <vendor_dlkm_b.img>
"""
import argparse
import hashlib
import os
import struct
import sys

SECTOR = 512
SUPER_START_LBA = 3686400
SUPER_TOTAL_BYTES = 3221225472
SUPER_TOTAL_SECTORS = SUPER_TOTAL_BYTES // SECTOR  # 6,291,456
GROUP_MAX_BYTES = 3217031168

GEOMETRY_OFFSET = 4096
GEOMETRY_SIZE = 4096
GEOMETRY_MAGIC = 0x616C4467
GEOMETRY_STRUCT_SIZE = 52
METADATA_MAX_SIZE = 65536
METADATA_SLOTS = 3
LOGICAL_BLOCK_SIZE = 4096

HEADER_MAGIC = 0x414C5030
HEADER_MAJOR = 10
HEADER_MINOR = 2
HEADER_SIZE = 256
HEADER_FLAGS = 1  # LP_METADATA_HEADER_VIRTUAL_AB_DEVICE

LP_PARTITION_ATTR_READONLY = 0x1
LP_PARTITION_ATTR_UPDATED = 0x4
LP_TARGET_TYPE_LINEAR = 0

# Stock Slot B extents in super (from super_meta_live.img):
#   odm_b         : (2872,   0, 2048,    0)
#   product_b     : (4784,   0, 6144,    0)
#   system_dlkm_b : (23968,  0, 1253376, 0)
#   system_ext_b  : (232576, 0, 1277952, 0)
#   vendor_b      : (939000, 0, 1511424, 0), (80, 0, 2566584, 0)
#   vendor_dlkm_b : (105072, 0, 2451456, 0)
# Free regions when -cow extents (2566664..2741984) are dropped:
#   Region A (stock system_a/b base): start=12288,   sectors=1240920 (635,351,040 B)
#   Region B (tail after vendor_b)  : start=2568192, sectors=3723264 (1,906,311,168 B)
TAIL_FREE_START = 2568192
TAIL_FREE_SECTORS = SUPER_TOTAL_SECTORS - TAIL_FREE_START  # 3,723,264
PRIMARY_SYS_START = 12288
PRIMARY_SYS_SECTORS = 1240920


def build_geometry():
    raw = bytearray(GEOMETRY_STRUCT_SIZE)
    struct.pack_into(
        "<II32sIII",
        raw,
        0,
        GEOMETRY_MAGIC,
        GEOMETRY_STRUCT_SIZE,
        b"\x00" * 32,
        METADATA_MAX_SIZE,
        METADATA_SLOTS,
        LOGICAL_BLOCK_SIZE,
    )
    csum = hashlib.sha256(raw).digest()
    raw[8:40] = csum
    block = bytearray(GEOMETRY_SIZE)
    block[:GEOMETRY_STRUCT_SIZE] = raw
    return bytes(block)


def build_metadata_slot(partitions, extents, groups, block_devices):
    """Build one 65536-byte metadata slot (header + tables)."""
    part_table = bytearray()
    for name, attrs, fei, ne, grp_idx in partitions:
        entry = bytearray(52)
        name_bytes = name.encode("utf-8")[:36]
        entry[:len(name_bytes)] = name_bytes
        struct.pack_into("<IIII", entry, 36, attrs, fei, ne, grp_idx)
        part_table.extend(entry)

    ext_table = bytearray()
    for num_sec, ttype, tdata, tsource in extents:
        entry = struct.pack("<QIQI", num_sec, ttype, tdata, tsource)
        ext_table.extend(entry)

    grp_table = bytearray()
    for name, flags, max_size in groups:
        entry = bytearray(48)
        name_bytes = name.encode("utf-8")[:36]
        entry[:len(name_bytes)] = name_bytes
        struct.pack_into("<IQ", entry, 36, flags, max_size)
        grp_table.extend(entry)

    bdev_table = bytearray()
    for first_sec, alignment, align_off, size, pname, bflags in block_devices:
        entry = bytearray(64)
        struct.pack_into("<QIIQ", entry, 0, first_sec, alignment, align_off, size)
        pname_bytes = pname.encode("utf-8")[:36]
        entry[24:24 + len(pname_bytes)] = pname_bytes
        struct.pack_into("<I", entry, 60, bflags)
        bdev_table.extend(entry)

    p_off = 0
    e_off = len(part_table)
    g_off = e_off + len(ext_table)
    b_off = g_off + len(grp_table)
    tables = bytes(part_table + ext_table + grp_table + bdev_table)
    tables_csum = hashlib.sha256(tables).digest()

    hdr = bytearray(HEADER_SIZE)
    struct.pack_into("<IHHI", hdr, 0, HEADER_MAGIC, HEADER_MAJOR, HEADER_MINOR, HEADER_SIZE)
    # hdr[12:44] is header_checksum (zeroed during calculation)
    struct.pack_into("<I", hdr, 44, len(tables))
    hdr[48:80] = tables_csum
    # Table descriptors at 80: partitions(0), extents(1), groups(2), block_devices(3)
    struct.pack_into("<III", hdr, 80 + 0 * 12, p_off, len(partitions), 52)
    struct.pack_into("<III", hdr, 80 + 1 * 12, e_off, len(extents), 24)
    struct.pack_into("<III", hdr, 80 + 2 * 12, g_off, len(groups), 48)
    struct.pack_into("<III", hdr, 80 + 3 * 12, b_off, len(block_devices), 64)
    struct.pack_into("<I", hdr, 128, HEADER_FLAGS)

    hdr_csum = hashlib.sha256(hdr).digest()
    hdr[12:44] = hdr_csum

    slot_buf = bytearray(METADATA_MAX_SIZE)
    slot_buf[:HEADER_SIZE] = hdr
    slot_buf[HEADER_SIZE:HEADER_SIZE + len(tables)] = tables
    return bytes(slot_buf)


def build_surgical_slot_b(args):
    sys_size = os.path.getsize(args.system)
    if sys_size % SECTOR != 0:
        raise SystemExit(f"error: system image size {sys_size} is not a multiple of 512 bytes")
    sys_sectors = sys_size // SECTOR

    odm_sectors = (args.odm_size // SECTOR) if args.odm_size else 2872
    prod_sectors = (args.product_size // SECTOR) if args.product_size else 4784
    sysext_sectors = (args.system_ext_size // SECTOR) if args.system_ext_size else 232576

    if odm_sectors > 2872:
        raise SystemExit(f"error: odm_b sectors {odm_sectors} exceeds stock 2872")
    if prod_sectors > 4784:
        raise SystemExit(f"error: product_b sectors {prod_sectors} exceeds stock 4784")
    if sysext_sectors > 232576:
        raise SystemExit(f"error: system_ext_b sectors {sysext_sectors} exceeds stock 232576")

    # Determine system_b extent allocation
    if sys_sectors <= TAIL_FREE_SECTORS:
        sys_extents = [(sys_sectors, LP_TARGET_TYPE_LINEAR, TAIL_FREE_START, 0)]
        mode_desc = (
            f"SINGLE CONTIGUOUS EXTENT at super sector {TAIL_FREE_START} "
            f"(eMMC LBA {SUPER_START_LBA + TAIL_FREE_START}) — stock system_a/b sectors "
            f"{PRIMARY_SYS_START}..{PRIMARY_SYS_START + PRIMARY_SYS_SECTORS} UNTOUCHED"
        )
    elif sys_sectors <= (PRIMARY_SYS_SECTORS + TAIL_FREE_SECTORS):
        rem = sys_sectors - PRIMARY_SYS_SECTORS
        sys_extents = [
            (PRIMARY_SYS_SECTORS, LP_TARGET_TYPE_LINEAR, PRIMARY_SYS_START, 0),
            (rem, LP_TARGET_TYPE_LINEAR, TAIL_FREE_START, 0),
        ]
        mode_desc = (
            f"TWO CONTIGUOUS EXTENTS: [0] super sector {PRIMARY_SYS_START} ({PRIMARY_SYS_SECTORS} sectors) "
            f"+ [1] super sector {TAIL_FREE_START} ({rem} sectors)"
        )
    else:
        max_b = (PRIMARY_SYS_SECTORS + TAIL_FREE_SECTORS) * SECTOR
        raise SystemExit(
            f"error: system image ({sys_size} B) exceeds available surgical space ({max_b} B)"
        )

    if args.keep_product_system_ext:
        extents = [
            (odm_sectors, LP_TARGET_TYPE_LINEAR, 2048, 0),
            (prod_sectors, LP_TARGET_TYPE_LINEAR, 6144, 0),
        ]
        prod_fei, prod_ne = 1, 1
    else:
        extents = [
            (odm_sectors, LP_TARGET_TYPE_LINEAR, 2048, 0),
        ]
        prod_fei, prod_ne = 1, 0

    sys_fei = len(extents)
    extents.extend(sys_extents)
    sys_ne = len(sys_extents)

    dlkm_fei = len(extents)
    extents.append((23968, LP_TARGET_TYPE_LINEAR, 1253376, 0))   # system_dlkm_b
    if args.keep_product_system_ext:
        sysext_fei, sysext_ne = len(extents), 1
        extents.append((sysext_sectors, LP_TARGET_TYPE_LINEAR, 1277952, 0))  # system_ext_b
    else:
        sysext_fei, sysext_ne = len(extents), 0
    ven_fei = len(extents)
    extents.extend([
        (939000, LP_TARGET_TYPE_LINEAR, 1511424, 0),  # vendor_b [0]
        (80, LP_TARGET_TYPE_LINEAR, 2566584, 0),      # vendor_b [1]
        (105072, LP_TARGET_TYPE_LINEAR, 2451456, 0),  # vendor_dlkm_b
    ])

    attr = LP_PARTITION_ATTR_READONLY | LP_PARTITION_ATTR_UPDATED
    partitions = [
        ("odm_b", attr, 0, 1, 1),
        ("product_b", attr, prod_fei, prod_ne, 1),
        ("system_b", attr, sys_fei, sys_ne, 1),
        ("system_dlkm_b", attr, dlkm_fei, 1, 1),
        ("system_ext_b", attr, sysext_fei, sysext_ne, 1),
        ("vendor_b", attr, ven_fei, 2, 1),
        ("vendor_dlkm_b", attr, ven_fei + 2, 1, 1),
    ]
    groups = [
        ("default", 0, 0),
        ("qti_dynamic_partitions_b", 0, GROUP_MAX_BYTES),
        ("cow", 0, 0),
    ]
    block_devices = [
        (2048, 512, 0, SUPER_TOTAL_BYTES, "super", 0),
    ]

    slot1_bytes = build_metadata_slot(partitions, extents, groups, block_devices)

    # Preserve Slot 0 and Slot 2 from stock super_meta_live.img if available
    if args.stock_meta and os.path.exists(args.stock_meta):
        with open(args.stock_meta, "rb") as fh:
            meta_img = bytearray(fh.read(524288))
    else:
        meta_img = bytearray(524288)
        geom = build_geometry()
        meta_img[GEOMETRY_OFFSET:GEOMETRY_OFFSET + GEOMETRY_SIZE] = geom
        meta_img[GEOMETRY_OFFSET + GEOMETRY_SIZE:GEOMETRY_OFFSET + GEOMETRY_SIZE * 2] = geom
        for s in range(METADATA_SLOTS):
            off = GEOMETRY_OFFSET + GEOMETRY_SIZE * 2 + METADATA_MAX_SIZE * s
            meta_img[off:off + METADATA_MAX_SIZE] = slot1_bytes

    # Write updated Slot 1 into primary and backup copies
    slot1_off = GEOMETRY_OFFSET + GEOMETRY_SIZE * 2 + METADATA_MAX_SIZE * 1
    meta_img[slot1_off:slot1_off + METADATA_MAX_SIZE] = slot1_bytes
    # In liblp, backup metadata slots immediately follow the 3 primary slots:
    backup_slot1_off = GEOMETRY_OFFSET + GEOMETRY_SIZE * 2 + METADATA_MAX_SIZE * (METADATA_SLOTS + 1)
    if backup_slot1_off + METADATA_MAX_SIZE <= len(meta_img):
        meta_img[backup_slot1_off:backup_slot1_off + METADATA_MAX_SIZE] = slot1_bytes

    # SECURITY-REVIEW: CLI tool creating output directory for user-specified output path
    os.makedirs(args.out_dir, exist_ok=True)
    out_meta = os.path.join(args.out_dir, "super_meta_android.img")
    with open(out_meta, "wb") as out:
        out.write(meta_img)

    print(f"Wrote surgical super metadata: {out_meta} ({len(meta_img)} bytes)")
    print(f"  system_b layout: {mode_desc}")
    if len(sys_extents) == 1:
        s_start = sys_extents[0][2]
        emmc_lba = SUPER_START_LBA + s_start
        print(f"  Flash commands (Phase 2 over EDL, NO --skipresponse on writes):")
        print(f"    tooling/scripts/edl ws {SUPER_START_LBA} {out_meta} --loader=tooling/loader/flip-4-edl.bin --memory=emmc")
        print(f"    tooling/scripts/edl ws {emmc_lba} {args.system} --loader=tooling/loader/flip-4-edl.bin --memory=emmc")
    else:
        chunk0 = os.path.join(args.out_dir, "system_b_extent0.img")
        chunk1 = os.path.join(args.out_dir, "system_b_extent1.img")
        b0 = PRIMARY_SYS_SECTORS * SECTOR
        with open(args.system, "rb") as sfh:
            with open(chunk0, "wb") as c0:
                c0.write(sfh.read(b0))
            with open(chunk1, "wb") as c1:
                while buf := sfh.read(4 * 1024 * 1024):
                    c1.write(buf)
        lba0 = SUPER_START_LBA + PRIMARY_SYS_START
        lba1 = SUPER_START_LBA + TAIL_FREE_START
        print(f"  Split system_b into:")
        print(f"    {chunk0} ({b0} bytes -> eMMC LBA {lba0})")
        print(f"    {chunk1} ({sys_size - b0} bytes -> eMMC LBA {lba1})")
        print(f"  Flash commands (Phase 2 over EDL, NO --skipresponse on writes):")
        print(f"    tooling/scripts/edl ws {SUPER_START_LBA} {out_meta} --loader=tooling/loader/flip-4-edl.bin --memory=emmc")
        print(f"    tooling/scripts/edl ws {lba0} {chunk0} --loader=tooling/loader/flip-4-edl.bin --memory=emmc")
        print(f"    tooling/scripts/edl ws {lba1} {chunk1} --loader=tooling/loader/flip-4-edl.bin --memory=emmc")


def align_up(val, align):
    return (val + align - 1) // align * align


def build_full_super(args):
    part_Order = [
        ("odm_b", args.odm),
        ("product_b", args.product),
        ("system_b", args.system),
        ("system_dlkm_b", args.system_dlkm),
        ("system_ext_b", args.system_ext),
        ("vendor_b", args.vendor),
        ("vendor_dlkm_b", args.vendor_dlkm),
    ]
    cur_sector = 2048  # 1 MiB offset
    align_sectors = (1024 * 1024) // SECTOR  # 2048 sectors (1 MiB)
    partitions = []
    extents = []
    placements = []

    attr = LP_PARTITION_ATTR_READONLY | LP_PARTITION_ATTR_UPDATED
    for name, path in part_Order:
        sz = os.path.getsize(path)
        if sz % SECTOR != 0:
            raise SystemExit(f"error: {name} ({path}) size {sz} not 512-aligned")
        n_sec = sz // SECTOR
        cur_sector = align_up(cur_sector, align_sectors)
        fei = len(extents)
        extents.append((n_sec, LP_TARGET_TYPE_LINEAR, cur_sector, 0))
        partitions.append((name, attr, fei, 1, 1))
        placements.append((name, path, cur_sector, n_sec, sz))
        cur_sector += n_sec

    if cur_sector > SUPER_TOTAL_SECTORS:
        raise SystemExit(
            f"error: total sectors {cur_sector} exceeds super size {SUPER_TOTAL_SECTORS}"
        )

    groups = [
        ("default", 0, 0),
        ("qti_dynamic_partitions_b", 0, GROUP_MAX_BYTES),
    ]
    block_devices = [
        (2048, 1048576, 0, SUPER_TOTAL_BYTES, "super", 0),
    ]
    geom = build_geometry()
    slot_bytes = build_metadata_slot(partitions, extents, groups, block_devices)

    # SECURITY-REVIEW: CLI tool creating output directory for user-specified output path
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "wb") as out:
        out.truncate(SUPER_TOTAL_BYTES)
        out.seek(GEOMETRY_OFFSET)
        out.write(geom)
        out.write(geom)
        for s in range(METADATA_SLOTS * 2):
            out.seek(GEOMETRY_OFFSET + GEOMETRY_SIZE * 2 + METADATA_MAX_SIZE * s)
            out.write(slot_bytes)
        for name, path, start_sec, n_sec, sz in placements:
            out.seek(start_sec * SECTOR)
            with open(path, "rb") as pfh:
                while chunk := pfh.read(4 * 1024 * 1024):
                    out.write(chunk)
            print(f"  packed {name:16}: start_sector={start_sec:>8} sectors={n_sec:>8} ({sz:>12} B)")
    print(f"Wrote full super image: {args.out} ({SUPER_TOTAL_BYTES} bytes)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--surgical", action="store_true", help="Build surgical Slot-B super metadata")
    mode.add_argument("--full", action="store_true", help="Build full 3 GiB super.img")

    ap.add_argument("--system", required=True, help="Path to signed system_b.img")
    ap.add_argument("--out-dir", default="artifacts/build/android-flash", help="Output dir for --surgical mode")
    ap.add_argument("--stock-meta", default="artifacts/build/super_meta_live.img", help="Stock super_meta_live.img")
    ap.add_argument("--odm-size", type=int, default=0, help="Override odm_b size in bytes")
    ap.add_argument("--product-size", type=int, default=0, help="Override product_b size in bytes")
    ap.add_argument("--system-ext-size", type=int, default=0, help="Override system_ext_b size in bytes")
    ap.add_argument(
        "--keep-product-system-ext",
        action="store_true",
        help="Keep stock product_b and system_ext_b mapped (default: zero-length so GSI /system/product and /system/system_ext are used)",
    )

    ap.add_argument("--out", help="Output super.img path for --full mode")
    ap.add_argument("--odm", default="artifacts/build/odm_b-dbg-patched.img")
    ap.add_argument("--product", default="artifacts/build/product_b.img")
    ap.add_argument("--system-dlkm", default="artifacts/build/system_dlkm_b.img")
    ap.add_argument("--system-ext", default="artifacts/build/system_ext_b.img")
    ap.add_argument("--vendor", default="artifacts/build/vendor_b.img")
    ap.add_argument("--vendor-dlkm", default="artifacts/build/vendor_dlkm_b.img")

    args = ap.parse_args()
    if args.surgical:
        build_surgical_slot_b(args)
    else:
        if not args.out:
            ap.error("--out is required with --full")
        build_full_super(args)


if __name__ == "__main__":
    main()
