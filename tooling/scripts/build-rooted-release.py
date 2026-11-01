#!/usr/bin/env python3
"""Build the current-safe T440W rooted community release image set."""

import argparse
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tooling", "scripts"))

from inspect_ext4 import Ext4Reader
from prepare_gsi import (
    apply_system_adb_profile,
    build_odm_android_image,
    calc_partition_size_for_avb,
    inject_ext4_files,
    normalize_ext4_metadata,
    parse_android_properties,
    sha256_file,
    strip_existing_avb_footer,
    verify_vbmeta_signature,
)

AVBTOOL = os.path.join(REPO_ROOT, "tooling", "tools", "avb", "avbtool.py")
PATCH_VBMETA = os.path.join(REPO_ROOT, "tooling", "scripts", "patch_vbmeta.py")
LP_MAKE = os.path.join(REPO_ROOT, "tooling", "scripts", "lp_make.py")
KEY_2048 = os.path.join(
    REPO_ROOT, "tooling", "tools", "avb", "testkeys", "testkey_rsa2048.pem"
)
KEY_4096 = os.path.join(
    REPO_ROOT, "tooling", "tools", "avb", "testkeys", "testkey_rsa4096.pem"
)
COMPONENT_MANIFEST = os.path.join(REPO_ROOT, "tooling", "release-components.json")
PERMISSIONS_DIR = os.path.join(REPO_ROOT, "device", "t440w", "permissions")
SYSTEM_GROWTH = 256 * 1024 * 1024
MAX_SYSTEM_PARTITION = 2_541_662_208
EXPECTED_RAW_SYSTEM = 2_056_237_056
EXPECTED_KEYPAD_ACTIONS = (
    "450e8e06a6b723479b0279d6857bb2d47a3fde594e44b8c403e56749497d21ec"
)


def run(command):
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def require_hash(path, expected, label):
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"error: {label} hash {actual} != expected {expected}")
    return actual


def descriptor_blobs(path):
    data = open(path, "rb").read()
    if data[:4] != b"AVB0":
        raise SystemExit(f"error: {path} is not standalone vbmeta")
    auth_size = struct.unpack_from(">Q", data, 12)[0]
    aux_size = struct.unpack_from(">Q", data, 20)[0]
    desc_off = struct.unpack_from(">Q", data, 96)[0]
    desc_size = struct.unpack_from(">Q", data, 104)[0]
    aux = data[256 + auth_size:256 + auth_size + aux_size]
    result = []
    position = desc_off
    while position < desc_off + desc_size:
        _, following = struct.unpack_from(">QQ", aux, position)
        result.append(aux[position:position + 16 + following])
        position += 16 + following
    if position != desc_off + desc_size:
        raise SystemExit(f"error: malformed descriptor table in {path}")
    return result


def patch_one_descriptor(source, partition, image, key, output):
    run(
        [
            sys.executable,
            PATCH_VBMETA,
            source,
            partition,
            "auto",
            key,
            output,
            "--zero-fec",
            f"--from-image={image}",
        ]
    )
    verify_vbmeta_signature(output, key)
    before = descriptor_blobs(source)
    after = descriptor_blobs(output)
    changed = [
        index
        for index, pair in enumerate(zip(before, after))
        if pair[0] != pair[1]
    ]
    if len(before) != len(after) or len(changed) != 1:
        raise SystemExit(
            f"error: expected one changed {partition} descriptor, got {changed}"
        )
    return changed


def verify_hashtree(image_path, partition_name):
    with tempfile.TemporaryDirectory(prefix=f"t440w-verify-{partition_name}-") as work:
        canonical = os.path.join(work, f"{partition_name}.img")
        os.symlink(os.path.abspath(image_path), canonical)
        run([sys.executable, AVBTOOL, "verify_image", "--image", canonical])


def ext4_free_bytes(path):
    with open(path, "rb") as image:
        image.seek(1024)
        superblock = image.read(1024)
    block_size = 1024 << struct.unpack_from("<I", superblock, 0x18)[0]
    free_low = struct.unpack_from("<I", superblock, 0x0C)[0]
    free_high = struct.unpack_from("<I", superblock, 0x158)[0]
    return (free_low | (free_high << 32)) * block_size


def ext4_inventory(path):
    result = {}
    with open(path, "rb") as image:
        reader = Ext4Reader(image)
        for directory, entries in reader.walk("/"):
            for name, inode_number, file_type in entries:
                if file_type not in (1, 7):
                    continue
                target = f"{directory.rstrip('/')}/{name}"
                inode = reader.read_inode(inode_number)
                data = reader.read_inode_data(inode)
                result[target] = {
                    "mode": inode["mode"],
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": inode["size"],
                }
    return result


def verify_untargeted_files(before, after, changed_paths, expected_new):
    changed_paths = set(changed_paths)
    for path, identity in before.items():
        if path in changed_paths:
            continue
        if after.get(path) != identity:
            raise SystemExit(f"error: untargeted system file changed: {path}")
    actual_new = set(after) - set(before)
    if actual_new != set(expected_new):
        raise SystemExit(
            "error: unexpected new system files: "
            f"expected={sorted(expected_new)} actual={sorted(actual_new)}"
        )


def resize_ext4(path, target_size):
    if target_size % 4096:
        raise SystemExit("error: ext4 target size is not 4096-byte aligned")
    with open(path, "r+b") as image:
        image.truncate(target_size)
    image_dir = os.path.dirname(os.path.abspath(path))
    image_name = os.path.basename(path)
    blocks = target_size // 4096
    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{image_dir}:/image",
            "t440w-tools:local",
            "sh",
            "-c",
            f"e2fsck -fy /image/{image_name} >/dev/null"
            f" && resize2fs /image/{image_name} {blocks} >/dev/null"
            f" && e2fsck -fy /image/{image_name} >/dev/null",
        ]
    )
    if os.path.getsize(path) != target_size:
        raise SystemExit("error: resize2fs produced an unexpected image size")


def component_hashes():
    manifest = json.load(open(COMPONENT_MANIFEST, encoding="utf-8"))
    components = {item["id"]: item for item in manifest["components"]}
    return {
        "aurora": components["aurora-store"]["sha256"],
        "c9": components["c9"]["t440w_build_sha256"],
        "magisk": components["magisk"]["sha256"],
        "microg_companion": components["microg-companion"]["sha256"],
        "microg_services": components["microg-services"]["sha256"],
    }


def release_sources(args, native_work):
    sources = {
        "/system/app/AuroraStore/AuroraStore.apk": (args.aurora_apk, 0o100644),
        "/system/app/C9/C9.apk": (args.c9_apk, 0o100644),
        # Magisk rejects Manager when PackageManager marks it as a system app.
        # Carry the pinned installer in the image without package-scanning it;
        # install it normally into /data after flashing.
        "/system/etc/t440w/release/Magisk-v31.1.apk": (
            args.magisk_apk,
            0o100644,
        ),
        "/system/app/T440WKeypadCursor/T440WKeypadCursor.apk": (
            args.keypad_actions_apk,
            0o100644,
        ),
        "/system/bin/t440w-enable-keypad.sh": (
            os.path.join(
                REPO_ROOT, "device", "t440w", "init", "t440w-enable-keypad.sh"
            ),
            0o100755,
        ),
        "/system/etc/init/init.t440w.keypad.rc": (
            os.path.join(
                REPO_ROOT, "device", "t440w", "init", "init.t440w.keypad.rc"
            ),
            0o100644,
        ),
        "/system/priv-app/GmsCore/GmsCore.apk": (
            args.microg_services_apk,
            0o100644,
        ),
        "/system/priv-app/MicroGCompanion/MicroGCompanion.apk": (
            args.microg_companion_apk,
            0o100644,
        ),
    }
    configs = {
        "/system/etc/default-permissions/default-permissions-com.android.vending.xml":
            "default-permissions-com.android.vending.xml",
        "/system/etc/default-permissions/default-permissions-com.google.android.gms.xml":
            "default-permissions-com.google.android.gms.xml",
        "/system/etc/permissions/privapp-permissions-com.android.vending.xml":
            "privapp-permissions-com.android.vending.xml",
        "/system/etc/permissions/privapp-permissions-com.google.android.gms.xml":
            "privapp-permissions-com.google.android.gms.xml",
        "/system/etc/sysconfig/sysconfig-com.google.android.gms.xml":
            "sysconfig-com.google.android.gms.xml",
    }
    for target, name in configs.items():
        sources[target] = (os.path.join(PERMISSIONS_DIR, name), 0o100644)

    for label, apk, target_dir in (
        ("gms", args.microg_services_apk, "/system/priv-app/GmsCore/lib/arm"),
    ):
        with zipfile.ZipFile(apk) as archive:
            for item in archive.infolist():
                prefix = "lib/armeabi-v7a/"
                if not item.filename.startswith(prefix) or item.is_dir():
                    continue
                name = item.filename[len(prefix):]
                host_path = os.path.join(native_work, f"{label}-{name}")
                with open(host_path, "wb") as output:
                    output.write(archive.read(item))
                sources[f"{target_dir}/{name}"] = (host_path, 0o100755)
    return sources


def read_selinux_hashes(system_path):
    with open(system_path, "rb") as image:
        reader = Ext4Reader(image)
        plat = reader.read_inode_data(
            reader.resolve_path(
                "/system/etc/selinux/plat_sepolicy_and_mapping.sha256"
            )
        )
        optional = []
        for path in (
            "/system/system_ext/etc/selinux/system_ext_sepolicy_and_mapping.sha256",
            "/system/product/etc/selinux/product_sepolicy_and_mapping.sha256",
        ):
            try:
                optional.append(reader.read_inode_data(reader.resolve_path(path)))
            except FileNotFoundError:
                optional.append(None)
    return plat, optional[0], optional[1]


def add_system_footer(path, partition_size):
    with open(path, "rb") as image:
        reader = Ext4Reader(image)
        props = parse_android_properties(
            reader.read_inode_data(reader.resolve_path("/system/build.prop"))
        )
    fingerprint = props.get("ro.system.build.fingerprint") or props.get(
        "ro.build.fingerprint"
    )
    os_version = props.get("ro.system.build.version.release") or props.get(
        "ro.build.version.release"
    )
    security_patch = props.get("ro.system.build.version.security_patch") or props.get(
        "ro.build.version.security_patch"
    )
    if not all((fingerprint, os_version, security_patch)):
        raise SystemExit("error: incomplete system AVB properties")
    run(
        [
            sys.executable,
            AVBTOOL,
            "add_hashtree_footer",
            "--image",
            path,
            "--partition_name",
            "system",
            "--partition_size",
            str(partition_size),
            "--hash_algorithm",
            "sha256",
            "--block_size",
            "4096",
            "--do_not_generate_fec",
            "--salt",
            "b1853b5bc80859b63e7708ed9f862b06ac7d76a06df0421e0544a370ee61b3d1",
            "--prop",
            f"com.android.build.system.os_version:{os_version}",
            "--prop",
            f"com.android.build.system.fingerprint:{fingerprint}",
            "--prop",
            f"com.android.build.system.security_patch:{security_patch}",
        ]
    )
    verify_hashtree(path, "system")


def add_odm_footer(path):
    run(
        [
            sys.executable,
            AVBTOOL,
            "add_hashtree_footer",
            "--image",
            path,
            "--partition_name",
            "odm",
            "--partition_size",
            "1470464",
            "--hash_algorithm",
            "sha256",
            "--block_size",
            "4096",
            "--do_not_generate_fec",
            "--salt",
            "5ff3ad795b534f56467f3d40354fee9798d15819f7f9a0f71cbbbe1b4b5459d5",
            "--prop",
            "com.android.build.odm.os_version:14",
            "--prop",
            "com.android.build.odm.fingerprint:"
            "TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/"
            "jenkins12220921:user/test-keys",
        ]
    )
    verify_hashtree(path, "odm")


def verify_release_odm(path):
    with open(path, "rb") as image:
        reader = Ext4Reader(image)
        build_prop = parse_android_properties(
            reader.read_inode_data(reader.resolve_path("/etc/build.prop"))
        )
        reader.resolve_path("/etc/init/init.t440w.platform.rc")
        try:
            reader.resolve_path("/etc/init/init.t440w.debug.rc")
        except FileNotFoundError:
            pass
        else:
            raise SystemExit("error: release ODM still contains debug init policy")
    expected = {
        "ro.adb.secure": "1",
        "persist.sys.phh.mainkeys": "1",
        "qemu.hw.mainkeys": "1",
    }
    for key, value in expected.items():
        if build_prop.get(key) != value:
            raise SystemExit(f"error: release ODM property {key} is not {value}")
    for forbidden in ("ro.force_debuggable", "service.adb.root"):
        if build_prop.get(forbidden):
            raise SystemExit(f"error: release ODM contains {forbidden}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("system", "odm", "vendor", "vbmeta", "vbmeta-system", "super-meta"):
        parser.add_argument(f"--{name}", required=True)
        parser.add_argument(f"--expect-{name}-sha256", required=True)
    parser.add_argument(
        "--keypad-actions-apk",
        default="artifacts/build/keypad-actions-release-v2/keypad-cursor.apk",
    )
    parser.add_argument(
        "--c9-apk", default="artifacts/build/c9-t440w/c9-t440w.apk"
    )
    parser.add_argument(
        "--magisk-apk",
        default="artifacts/downloads/release-components/Magisk-v31.1.apk",
    )
    parser.add_argument(
        "--microg-services-apk",
        default=(
            "artifacts/downloads/release-components/"
            "com.google.android.gms-252432034.apk"
        ),
    )
    parser.add_argument(
        "--microg-companion-apk",
        default=(
            "artifacts/downloads/release-components/"
            "com.android.vending-84022634.apk"
        ),
    )
    parser.add_argument(
        "--aurora-apk",
        default="artifacts/downloads/release-components/com.aurora.store_76.apk",
    )
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    source_paths = {
        "odm": args.odm,
        "super_meta": args.super_meta,
        "system": args.system,
        "vbmeta": args.vbmeta,
        "vbmeta_system": args.vbmeta_system,
        "vendor": args.vendor,
    }
    expected_hashes = {
        "odm": args.expect_odm_sha256,
        "super_meta": args.expect_super_meta_sha256,
        "system": args.expect_system_sha256,
        "vbmeta": args.expect_vbmeta_sha256,
        "vbmeta_system": args.expect_vbmeta_system_sha256,
        "vendor": args.expect_vendor_sha256,
    }
    source_hashes = {
        name: require_hash(path, expected_hashes[name], name)
        for name, path in source_paths.items()
    }
    pinned = component_hashes()
    component_paths = {
        "aurora": args.aurora_apk,
        "c9": args.c9_apk,
        "keypad_actions": args.keypad_actions_apk,
        "magisk": args.magisk_apk,
        "microg_companion": args.microg_companion_apk,
        "microg_services": args.microg_services_apk,
    }
    component_expected = dict(pinned)
    component_expected["keypad_actions"] = EXPECTED_KEYPAD_ACTIONS
    component_actual = {
        name: require_hash(path, component_expected[name], name)
        for name, path in component_paths.items()
    }

    os.makedirs(args.out_dir, exist_ok=True)
    system_out = os.path.join(args.out_dir, "system_b-rooted-release.img")
    odm_out = os.path.join(args.out_dir, "odm_b-rooted-release.img")
    vbmeta_out = os.path.join(args.out_dir, "vbmeta_b-rooted-release.img")
    vbmeta_system_out = os.path.join(
        args.out_dir, "vbmeta_system_b-rooted-release.img"
    )

    shutil.copyfile(args.system, system_out)
    strip_existing_avb_footer(system_out)
    if os.path.getsize(system_out) != EXPECTED_RAW_SYSTEM:
        raise SystemExit("error: unexpected exact-current raw system size")
    before_files = ext4_inventory(system_out)
    before_free = ext4_free_bytes(system_out)
    target_raw_size = EXPECTED_RAW_SYSTEM + SYSTEM_GROWTH
    resize_ext4(system_out, target_raw_size)
    apply_system_adb_profile(
        system_out, usb_diagnostics=False, unsafe_root_adb=False
    )

    with tempfile.TemporaryDirectory(prefix="t440w-release-native-") as native_work:
        sources = release_sources(args, native_work)
        replacement_paths = {
            "/system/app/T440WKeypadCursor/T440WKeypadCursor.apk",
            "/system/bin/t440w-enable-keypad.sh",
            "/system/etc/init/init.t440w.keypad.rc",
        }
        inject_ext4_files(
            system_out, sources, replace_paths=replacement_paths
        )
        normalize_ext4_metadata(
            system_out,
            set(sources)
            | replacement_paths
            | {
                "/system/build.prop",
                "/system/system_ext/etc/init/adb_root.rc",
            },
        )
        expected_new = set(sources) - set(before_files)
        changed_paths = replacement_paths | {
            "/system/build.prop",
            "/system/system_ext/etc/init/adb_root.rc",
        }
        after_files = ext4_inventory(system_out)
        verify_untargeted_files(
            before_files, after_files, changed_paths, expected_new
        )

    with open(system_out, "rb") as image:
        reader = Ext4Reader(image)
        system_props = parse_android_properties(
            reader.read_inode_data(reader.resolve_path("/system/build.prop"))
        )
        inert_adb_root = reader.read_inode_data(
            reader.resolve_path("/system/system_ext/etc/init/adb_root.rc")
        )
    if system_props.get("ro.debuggable") != "0":
        raise SystemExit("error: release system ro.debuggable is not 0")
    if system_props.get("ro.adb.secure") != "1":
        raise SystemExit("error: release system ro.adb.secure is not 1")
    if b"Disabled in the T440W release profile" not in inert_adb_root:
        raise SystemExit("error: PHH adb-root service was not neutralized")
    after_free = ext4_free_bytes(system_out)

    plat_sha, sysext_sha, prod_sha = read_selinux_hashes(system_out)
    build_odm_android_image(
        system_out,
        args.vendor,
        args.odm,
        odm_out,
        plat_sha,
        sysext_sha,
        prod_sha,
        usb_diagnostics=False,
        unsafe_root_adb=False,
        selinux_mode="enforcing",
        display_profile="none",
    )
    normalize_ext4_metadata(odm_out, ext4_inventory(odm_out))
    verify_release_odm(odm_out)
    add_odm_footer(odm_out)

    system_partition_size = calc_partition_size_for_avb(target_raw_size)
    if system_partition_size > MAX_SYSTEM_PARTITION:
        raise SystemExit("error: signed release system exceeds verified super capacity")
    add_system_footer(system_out, system_partition_size)
    if os.path.getsize(system_out) != system_partition_size:
        raise SystemExit("error: signed system size does not equal partition size")

    changed_system = patch_one_descriptor(
        args.vbmeta_system,
        "system",
        system_out,
        KEY_2048,
        vbmeta_system_out,
    )
    changed_odm = patch_one_descriptor(
        args.vbmeta,
        "odm",
        odm_out,
        KEY_4096,
        vbmeta_out,
    )

    run(
        [
            sys.executable,
            LP_MAKE,
            "--surgical",
            "--system",
            system_out,
            "--stock-meta",
            args.super_meta,
            "--out-dir",
            args.out_dir,
        ]
    )
    super_meta_out = os.path.join(args.out_dir, "super_meta_android.img")
    extent0 = os.path.join(args.out_dir, "system_b_extent0.img")
    extent1 = os.path.join(args.out_dir, "system_b_extent1.img")
    outputs = {
        "odm": odm_out,
        "super_meta": super_meta_out,
        "system": system_out,
        "system_extent0": extent0,
        "system_extent1": extent1,
        "vbmeta": vbmeta_out,
        "vbmeta_system": vbmeta_system_out,
    }
    for label, path in outputs.items():
        if not os.path.isfile(path):
            raise SystemExit(f"error: missing release output {label}: {path}")

    manifest = {
        "changed_descriptor_indexes": {
            "vbmeta": changed_odm,
            "vbmeta_system": changed_system,
        },
        "components": {
            name: {
                "path": os.path.abspath(component_paths[name]),
                "sha256": component_actual[name],
            }
            for name in sorted(component_paths)
        },
        "output": {
            name: {
                "path": os.path.abspath(path),
                "sha256": sha256_file(path),
                "size": os.path.getsize(path),
            }
            for name, path in sorted(outputs.items())
        },
        "source": {
            name: {
                "path": os.path.abspath(path),
                "sha256": source_hashes[name],
                "size": os.path.getsize(path),
            }
            for name, path in sorted(source_paths.items())
        },
        "system": {
            "free_bytes_after_injection": after_free,
            "free_bytes_before_growth": before_free,
            "growth_bytes": SYSTEM_GROWTH,
            "raw_size": target_raw_size,
            "signed_size": system_partition_size,
            "super_capacity_remaining": (
                MAX_SYSTEM_PARTITION - system_partition_size
            ),
        },
        "system_extents": [
            {
                "path": os.path.abspath(extent0),
                "raw_lba": 3_698_688,
                "sectors": os.path.getsize(extent0) // 512,
            },
            {
                "path": os.path.abspath(extent1),
                "raw_lba": 6_254_592,
                "sectors": os.path.getsize(extent1) // 512,
            },
        ],
    }
    manifest_path = os.path.join(args.out_dir, "build-manifest.json")
    with open(manifest_path, "w") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
