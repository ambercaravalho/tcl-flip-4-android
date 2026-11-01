#!/usr/bin/env python3
"""Surgically patch one hashtree or hash descriptor in a signed vbmeta image,
then re-sign, leaving every other descriptor byte-identical.

This is used to update individual verity descriptors (e.g., `system`,
`system_ext`, `product` in `vbmeta_system` signed with `testkey_rsa2048.pem`,
or `odm`, `vendor` in `vbmeta` signed with `testkey_rsa4096.pem`) without
disturbing other hash/chain descriptors (such as `dtbo`, which has no
standalone AVB footer).

For a hashtree descriptor, `--from-image=<part.img>` copies its complete AVB
footer geometry and digest. For a raw hash descriptor such as `dtbo`, it
computes `hash(salt || image)` and updates `image_size`. Use `auto` as the
digest argument for either form.

AVB signature == RSA-PKCS1v1.5(SHA256(header || aux)), which is exactly what
`openssl dgst -sha256 -sign` produces, so we shell out to openssl for signing.

Usage:
  patch_vbmeta.py <stock_vbmeta> <partition> <new_root_digest_hex|auto> <key.pem> <out> [--zero-fec] [--from-image=<part.img>]
"""
import hashlib
import os
import struct
import subprocess
import sys

DESC_HASHTREE = 1
DESC_HASH = 2
AVB_FOOTER_MAGIC = b"AVBf"
AVB_FOOTER_SIZE = 64


def read_footer_hashtree_desc(img_path, expected_part):
    """Extract hashtree descriptor fields from an image's AVB footer."""
    size = os.path.getsize(img_path)
    with open(img_path, "rb") as fh:
        fh.seek(size - AVB_FOOTER_SIZE)
        footer = fh.read(AVB_FOOTER_SIZE)
        if footer[0:4] != AVB_FOOTER_MAGIC:
            raise SystemExit(f"error: no AVBf footer at end of {img_path}")
        orig_img_size, vbmeta_off, vbmeta_size = struct.unpack_from(">QQQ", footer, 12)
        fh.seek(vbmeta_off)
        vb = fh.read(vbmeta_size)

    if vb[0:4] != b"AVB0":
        raise SystemExit(f"error: bad AVB0 header at {vbmeta_off:#x} in {img_path}")
    auth_size = struct.unpack_from(">Q", vb, 12)[0]
    aux_size = struct.unpack_from(">Q", vb, 20)[0]
    desc_off = struct.unpack_from(">Q", vb, 96)[0]
    desc_size = struct.unpack_from(">Q", vb, 104)[0]
    aux = vb[256 + auth_size:256 + auth_size + aux_size]

    pos = desc_off
    end = desc_off + desc_size
    while pos < end:
        tag, nbf = struct.unpack_from(">QQ", aux, pos)
        body = pos + 16
        if tag == DESC_HASHTREE:
            image_size, tree_offset, tree_size = struct.unpack_from(">QQQ", aux, body + 4)
            fec_num_roots, fec_offset, fec_size = struct.unpack_from(">LQQ", aux, body + 36)
            name_len, salt_len, digest_len = struct.unpack_from(">LLL", aux, body + 88)
            name_off = body + 164
            name = aux[name_off:name_off + name_len].decode()
            salt = aux[name_off + name_len:name_off + name_len + salt_len]
            digest = aux[name_off + name_len + salt_len:name_off + name_len + salt_len + digest_len]
            if name == expected_part:
                return {
                    "image_size": image_size,
                    "tree_offset": tree_offset,
                    "tree_size": tree_size,
                    "fec_num_roots": fec_num_roots,
                    "fec_offset": fec_offset,
                    "fec_size": fec_size,
                    "salt": salt,
                    "digest": digest,
                }
        pos += 16 + nbf
    raise SystemExit(f"error: hashtree descriptor '{expected_part}' not found in footer of {img_path}")


def find_descriptor(aux, desc_off, desc_size, target):
    """Return (tag, descriptor fields) for a hash/hashtree partition."""
    pos = desc_off
    end = desc_off + desc_size
    while pos < end:
        tag, nbf = struct.unpack_from(">QQ", aux, pos)
        body = pos + 16
        if tag == DESC_HASHTREE:
            name_len, salt_len, digest_len = struct.unpack_from(
                ">LLL", aux, body + 88
            )
            name_off = body + 164
        elif tag == DESC_HASH:
            name_len, salt_len, digest_len = struct.unpack_from(
                ">LLL", aux, body + 40
            )
            name_off = body + 116
        else:
            pos += 16 + nbf
            continue
        name = aux[name_off:name_off + name_len].decode()
        if name == target:
            return tag, {
                "body": body,
                "name_off": name_off,
                "name_len": name_len,
                "salt_len": salt_len,
                "digest_len": digest_len,
                "salt": aux[
                    name_off + name_len:name_off + name_len + salt_len
                ],
            }
        pos += 16 + nbf
    raise SystemExit(f"error: hash/hashtree descriptor '{target}' not found")


def calculate_hash_descriptor(image_path, algorithm, salt):
    digest = hashlib.new(algorithm)
    digest.update(salt)
    image_size = os.path.getsize(image_path)
    with open(image_path, "rb") as image:
        while chunk := image.read(4 * 1024 * 1024):
            digest.update(chunk)
    return image_size, digest.digest()


def find_and_patch(aux, desc_off, desc_size, target, new_digest, zero_fec, footer_info=None):
    """Return patched aux bytes; raise if target not found."""
    aux = bytearray(aux)
    pos = desc_off
    end = desc_off + desc_size
    while pos < end:
        tag, nbf = struct.unpack_from(">QQ", aux, pos)
        body = pos + 16
        total = 16 + nbf
        if tag == DESC_HASHTREE:
            # Offsets are relative to the descriptor body (after the 16-byte
            # AvbDescriptor base):
            #   dm_verity_version(4)@0, image_size(8)@4, tree_offset(8)@12,
            #   tree_size(8)@20, data_block_size(4)@28, hash_block_size(4)@32,
            #   fec_num_roots(4)@36, fec_offset(8)@40, fec_size(8)@48,
            #   hash_algorithm(32s)@56, partition_name_len(4)@88, salt_len(4)@92,
            #   root_digest_len(4)@96, flags(4)@100, reserved(60)@104,
            #   and the name/salt/digest blob starts at @164.
            name_len = struct.unpack_from(">L", aux, body + 88)[0]
            salt_len = struct.unpack_from(">L", aux, body + 92)[0]
            digest_len = struct.unpack_from(">L", aux, body + 96)[0]
            name_off = body + 164
            name = aux[name_off:name_off + name_len].decode()
            if name == target:
                if len(new_digest) != digest_len:
                    raise SystemExit(
                        f"digest len {len(new_digest)} != expected {digest_len}")
                if footer_info is not None:
                    struct.pack_into(
                        ">QQQ",
                        aux,
                        body + 4,
                        footer_info["image_size"],
                        footer_info["tree_offset"],
                        footer_info["tree_size"],
                    )
                    struct.pack_into(
                        ">LQQ",
                        aux,
                        body + 36,
                        footer_info["fec_num_roots"],
                        footer_info["fec_offset"],
                        footer_info["fec_size"],
                    )
                    if len(footer_info["salt"]) == salt_len:
                        aux[name_off + name_len:name_off + name_len + salt_len] = footer_info["salt"]
                if zero_fec:
                    struct.pack_into(">L", aux, body + 36, 0)   # fec_num_roots
                    struct.pack_into(">Q", aux, body + 40, 0)   # fec_offset
                    struct.pack_into(">Q", aux, body + 48, 0)   # fec_size
                digest_off = name_off + name_len + salt_len
                aux[digest_off:digest_off + digest_len] = new_digest
                return bytes(aux)
        elif tag == DESC_HASH:
            # Hash descriptor body: image_size(8)@0, hash_algorithm(32s)@8,
            # partition_name_len(4)@40, salt_len(4)@44, digest_len(4)@48,
            # flags(4)@52, reserved(60)@56, name/salt/digest blob @116.
            name_len, salt_len, digest_len = struct.unpack_from(
                ">LLL", aux, body + 40
            )
            name_off = body + 116
            name = aux[name_off:name_off + name_len].decode()
            if name == target:
                if zero_fec:
                    raise SystemExit("--zero-fec is invalid for a hash descriptor")
                if len(new_digest) != digest_len:
                    raise SystemExit(
                        f"digest len {len(new_digest)} != expected {digest_len}"
                    )
                if footer_info is not None:
                    struct.pack_into(">Q", aux, body, footer_info["image_size"])
                digest_off = name_off + name_len + salt_len
                aux[digest_off:digest_off + digest_len] = new_digest
                return bytes(aux)
        pos += total
    raise SystemExit(f"hash/hashtree descriptor '{target}' not found")


def main(argv):
    if len(argv) < 6:
        raise SystemExit(__doc__)
    stock, part, digest_hex, key, out = argv[1:6]
    zero_fec = "--zero-fec" in argv[6:]
    from_image = None
    for a in argv[6:]:
        if a.startswith("--from-image="):
            from_image = a.split("=", 1)[1]

    data = open(stock, "rb").read()
    if data[0:4] != b"AVB0":
        raise SystemExit("not a vbmeta image (missing AVB0 magic)")

    auth_size = struct.unpack_from(">Q", data, 12)[0]
    aux_size = struct.unpack_from(">Q", data, 20)[0]
    hash_off = struct.unpack_from(">Q", data, 32)[0]
    hash_size = struct.unpack_from(">Q", data, 40)[0]
    sig_off = struct.unpack_from(">Q", data, 48)[0]
    sig_size = struct.unpack_from(">Q", data, 56)[0]
    desc_off = struct.unpack_from(">Q", data, 96)[0]
    desc_size = struct.unpack_from(">Q", data, 104)[0]

    header = data[0:256]
    aux_start = 256 + auth_size
    aux = data[aux_start:aux_start + aux_size]
    total_size = len(data)

    descriptor_tag, descriptor = find_descriptor(
        aux, desc_off, desc_size, part
    )
    footer_info = None
    if from_image:
        if descriptor_tag == DESC_HASHTREE:
            footer_info = read_footer_hashtree_desc(from_image, part)
            auto_digest = footer_info["digest"]
        else:
            algorithm = bytes(
                aux[
                    descriptor["body"] + 8:descriptor["body"] + 40
                ]
            ).split(b"\x00", 1)[0].decode()
            image_size, auto_digest = calculate_hash_descriptor(
                from_image, algorithm, descriptor["salt"]
            )
            footer_info = {"image_size": image_size}
        if digest_hex == "auto":
            new_digest = auto_digest
            digest_hex = new_digest.hex()
        else:
            new_digest = bytes.fromhex(digest_hex)
    else:
        if digest_hex == "auto":
            raise SystemExit("error: auto requires --from-image=<part.img>")
        new_digest = bytes.fromhex(digest_hex)

    new_aux = find_and_patch(aux, desc_off, desc_size, part, new_digest, zero_fec, footer_info)

    # AVB signs SHA256(header || aux) with PKCS#1 v1.5 -> openssl dgst -sha256 -sign
    signed_input = header + new_aux
    # SECURITY-REVIEW: CLI tool invoking local openssl binary with fixed arguments for AVB signing
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", key],
        input=signed_input, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("openssl sign failed: " + proc.stderr.decode())
    signature = proc.stdout
    if len(signature) != sig_size:
        raise SystemExit(f"sig len {len(signature)} != header sig_size {sig_size}")

    digest = hashlib.sha256(signed_input).digest()
    if len(digest) != hash_size:
        raise SystemExit(f"digest len {len(digest)} != header hash_size {hash_size}")

    auth = bytearray(auth_size)
    auth[hash_off:hash_off + hash_size] = digest
    auth[sig_off:sig_off + sig_size] = signature

    blob = header + bytes(auth) + new_aux
    if len(blob) > total_size:
        raise SystemExit("patched blob larger than original")
    blob = blob + b"\x00" * (total_size - len(blob))

    open(out, "wb").write(blob)
    extra = []
    if footer_info:
        detail = f"image_size={footer_info['image_size']}"
        if "tree_size" in footer_info:
            detail += f" tree_size={footer_info['tree_size']}"
        extra.append(detail)
    if zero_fec:
        extra.append("fec zeroed")
    suffix = f" ({', '.join(extra)})" if extra else ""
    print(f"wrote {out}: {len(blob)} bytes, {part} digest -> {digest_hex}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
