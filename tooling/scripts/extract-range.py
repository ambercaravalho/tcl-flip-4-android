#!/usr/bin/env python3
"""Extract a sector range from a raw storage image without loading it in RAM."""

import argparse
import hashlib
import os


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Source raw image")
    parser.add_argument("start_sector", type=int, help="First sector to copy")
    parser.add_argument("sector_count", type=int, help="Number of sectors to copy")
    parser.add_argument("output", help="Output image")
    parser.add_argument("--sector-size", type=int, default=512)
    args = parser.parse_args()

    if args.start_sector < 0 or args.sector_count <= 0 or args.sector_size <= 0:
        parser.error("sector values must be positive (start may be zero)")

    offset = args.start_sector * args.sector_size
    length = args.sector_count * args.sector_size
    source_size = os.path.getsize(args.image)
    if offset + length > source_size:
        parser.error(
            f"requested range ends at {offset + length} bytes, "
            f"past the {source_size}-byte source"
        )

    digest = hashlib.sha256()
    remaining = length
    with open(args.image, "rb") as source, open(args.output, "wb") as output:
        source.seek(offset)
        while remaining:
            chunk = source.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise SystemExit("error: unexpected end of source image")
            output.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)

    print(
        f"extracted sectors {args.start_sector}.."
        f"{args.start_sector + args.sector_count - 1} "
        f"({length} bytes) -> {args.output}"
    )
    print(f"sha256 {digest.hexdigest()}")


if __name__ == "__main__":
    main()
