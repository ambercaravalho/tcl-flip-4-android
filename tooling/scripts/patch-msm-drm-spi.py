#!/usr/bin/env python3
"""Create controlled binary-patch variants of the stock T440W msm_drm.ko."""

import argparse
import hashlib
import struct

STOCK_SHA256 = "39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065"

# (symbol, symbol-relative offset, expected instruction, replacement)
PROFILES = {
    # Keep queueing/transmitting frames, but do not change the RGB565 staging
    # buffer. This separates source-buffer/composition defects from TE/SPI.
    "immutable": (
        ("spi_display_update_fb", 0x60, 0x52884829, 0x14000045),
    ),
    # Coalesce all plane updates observed before the worker runs into one
    # pending transfer. This controls transfer amplification but does not fix
    # the missing plane composition.
    "coalesce": (
        ("spi_display_update_fb", 0x190, 0xB828013F, 0xB9000128),
        ("spi_display_update_fb", 0x20C, 0x11000529, 0x52800029),
        ("spi_display_update_fb", 0x210, 0x880A7D09, 0xB9000109),
        ("spi_display_update_fb", 0x214, 0x35FFFFAA, 0x17FFFFE0),
    ),
    # Accept only a full-height client target, use the known 256-pixel row
    # stride, and skip status/navigation/overlay plane updates. Pair this with
    # forced client composition; it is the smallest testable contract fix.
    "full-height-client": (
        ("spi_display_update_fb", 0x28, 0x1AC308A8, 0x7105005F),
        ("spi_display_update_fb", 0x2C, 0x2A0603F6, 0x54000DC1),
        ("spi_display_update_fb", 0x34, 0x2A0303F4, 0x52802014),
        ("spi_display_update_fb", 0x40, 0x1B039509, 0x2A0603F6),
        ("spi_display_update_fb", 0x44, 0x34000069, 0x14000003),
        # Also coalesce repeated full-height submissions.
        ("spi_display_update_fb", 0x190, 0xB828013F, 0xB9000128),
        ("spi_display_update_fb", 0x20C, 0x11000529, 0x52800029),
        ("spi_display_update_fb", 0x210, 0x880A7D09, 0xB9000109),
        ("spi_display_update_fb", 0x214, 0x35FFFFAA, 0x17FFFFE0),
    ),
}


def elf_sections(data: bytes) -> list[dict]:
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit("error: expected a little-endian ELF64 module")
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    entry_size, count, names_index = struct.unpack_from("<HHH", data, 58)
    raw_sections = []
    for index in range(count):
        offset = section_offset + index * entry_size
        fields = struct.unpack_from("<IIQQQQIIQQ", data, offset)
        raw_sections.append(
            {
                "name_offset": fields[0],
                "type": fields[1],
                "address": fields[3],
                "offset": fields[4],
                "size": fields[5],
                "link": fields[6],
                "entry_size": fields[9],
            }
        )
    names = raw_sections[names_index]
    names_data = data[names["offset"]:names["offset"] + names["size"]]
    for section in raw_sections:
        end = names_data.index(0, section["name_offset"])
        section["name"] = names_data[section["name_offset"]:end].decode()
    return raw_sections


def elf_symbols(data: bytes, sections: list[dict]) -> dict[str, tuple[int, int]]:
    symbols = {}
    for section in sections:
        if section["type"] != 2:  # SHT_SYMTAB
            continue
        strings = sections[section["link"]]
        string_data = data[strings["offset"]:strings["offset"] + strings["size"]]
        entry_size = section["entry_size"] or 24
        for offset in range(
            section["offset"], section["offset"] + section["size"], entry_size
        ):
            name_offset, _, _, section_index, value, size = struct.unpack_from(
                "<IBBHQQ", data, offset
            )
            if not name_offset or section_index >= len(sections):
                continue
            end = string_data.index(0, name_offset)
            name = string_data[name_offset:end].decode(errors="replace")
            target_section = sections[section_index]
            file_offset = (
                target_section["offset"] + value - target_section["address"]
            )
            symbols[name] = (file_offset, size)
    return symbols


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("profile", choices=sorted(PROFILES))
    parser.add_argument("output")
    args = parser.parse_args()

    data = bytearray(open(args.input, "rb").read())
    digest = hashlib.sha256(data).hexdigest()
    if digest != STOCK_SHA256:
        raise SystemExit(
            f"error: unsupported msm_drm.ko sha256 {digest}; expected {STOCK_SHA256}"
        )
    sections = elf_sections(data)
    symbols = elf_symbols(data, sections)

    for symbol, relative, expected, replacement in PROFILES[args.profile]:
        if symbol not in symbols:
            raise SystemExit(f"error: symbol {symbol!r} not found")
        symbol_offset, symbol_size = symbols[symbol]
        if relative + 4 > symbol_size:
            raise SystemExit(f"error: patch is outside {symbol}")
        offset = symbol_offset + relative
        actual = struct.unpack_from("<I", data, offset)[0]
        if actual != expected:
            raise SystemExit(
                f"error: {symbol}+{relative:#x} is {actual:#010x}, "
                f"expected {expected:#010x}"
            )
        struct.pack_into("<I", data, offset, replacement)
        print(
            f"{symbol}+{relative:#x}: {expected:#010x} -> {replacement:#010x}"
        )

    with open(args.output, "wb") as output:
        output.write(data)
    print(f"wrote {args.output}: sha256={hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
