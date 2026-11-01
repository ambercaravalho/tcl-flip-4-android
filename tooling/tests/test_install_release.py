from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "tooling/scripts"
sys.path.insert(0, str(SCRIPTS))

import t440w_install_lib as install_lib

SPEC = importlib.util.spec_from_file_location(
    "install_release", SCRIPTS / "install-release.py"
)
assert SPEC is not None and SPEC.loader is not None
install_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_release)


class FakeResponse(io.BytesIO):
    status = 200


class InstallerTests(unittest.TestCase):
    def test_tracked_manifest_is_valid_and_ordered(self) -> None:
        manifest, assets = install_lib.load_release()
        self.assertEqual(manifest["release"], install_lib.RELEASE)
        self.assertEqual(len(assets), 8)
        self.assertEqual(assets[-1]["target"], "vbmeta_b")
        kinds = [asset["kind"] for asset in assets]
        self.assertEqual(kinds, sorted(kinds, key=("payload", "metadata", "verification").index))

    def test_download_asset_writes_exact_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "asset.img"
            with mock.patch.object(
                install_release.urllib.request,
                "urlopen",
                return_value=FakeResponse(b"abc"),
            ):
                install_release.download_asset(
                    "https://example.invalid/asset.img", destination, 3
                )
            self.assertEqual(destination.read_bytes(), b"abc")
            self.assertFalse(destination.with_name("asset.img.part").exists())

    def test_guided_session_round_trip_is_version_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(install_release, "REPO_ROOT", root):
                session = {
                    "schema": 1,
                    "release": "v-test",
                    "full_backup": "artifacts/backups/full.img",
                }
                install_release.save_guided_session(session)
                self.assertEqual(
                    install_release.load_guided_session("v-test"), session
                )
                wrong_path = install_release.guided_session_path("v-other")
                wrong_path.parent.mkdir(parents=True)
                wrong_path.write_text(
                    json.dumps(session),
                    encoding="utf-8",
                )
                with self.assertRaises(SystemExit):
                    install_release.load_guided_session("v-other")

    def test_backup_protection_is_boolean_and_digest_bound(self) -> None:
        digest = "a" * 64
        self.assertFalse(
            install_release.backup_is_protected(
                {
                    "backup_protected": "false",
                    "protected_backup_sha256": digest,
                },
                digest,
            )
        )
        self.assertFalse(
            install_release.backup_is_protected(
                {
                    "backup_protected": True,
                    "protected_backup_sha256": "b" * 64,
                },
                digest,
            )
        )
        self.assertTrue(
            install_release.backup_is_protected(
                {
                    "backup_protected": True,
                    "protected_backup_sha256": digest,
                },
                digest,
            )
        )

    def test_partial_flash_rechecks_prefix_and_writes_only_remaining(self) -> None:
        first_data = b"a"
        second_data = b"b"
        first_hash = hashlib.sha256(first_data).hexdigest()
        second_hash = hashlib.sha256(second_data).hexdigest()
        assets = [
            {
                "name": "first.img",
                "target": "first",
                "raw_lba": 10,
                "sectors": 1,
                "size": 1,
                "sha256": first_hash,
            },
            {
                "name": "second.img",
                "target": "second",
                "raw_lba": 20,
                "sectors": 1,
                "size": 1,
                "sha256": second_hash,
            },
        ]
        manifest = {"release": "v-test"}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_backup = root / "target"
            flash_dir = target_backup / "flash-v-test"
            flash_dir.mkdir(parents=True)
            (flash_dir / "flash-receipt.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "release": "v-test",
                        "complete": False,
                        "verified": [
                            {
                                "target": "first",
                                "raw_lba": 10,
                                "sectors": 1,
                                "sha256": first_hash,
                                "verified_utc": "test",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            sources = {}
            backups = {}
            for asset, data, backup_data in zip(
                assets,
                (first_data, second_data),
                (b"x", b"z"),
            ):
                source = root / asset["name"]
                source.write_bytes(data)
                sources[asset["name"]] = source
                backup = root / f"{asset['target']}-before.img"
                backup.write_bytes(backup_data)
                backups[asset["target"]] = backup

            commands: list[list[str]] = []
            live_second = b"z"

            def fake_edl(
                args: list[str], loader: Path, log_path: Path, *, capture: bool = False
            ) -> str:
                nonlocal live_second
                del loader, log_path, capture
                commands.append(args)
                if args[0] == "ws" and args[1] == "20":
                    live_second = Path(args[2]).read_bytes()
                if args[0] == "rs":
                    output = Path(args[3])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(
                        first_data if args[1] == "10" else live_second
                    )
                return ""

            full_state = {
                "sha256": "0" * 64,
                "device_identity": {},
                "gpt_geometry_sha256": "1" * 64,
            }
            target_state = {
                "live_primary_gpt_sha256": "2" * 64,
                "paths": backups,
                "digests": {
                    target: hashlib.sha256(path.read_bytes()).hexdigest()
                    for target, path in backups.items()
                },
            }
            live_state = {
                "primary_gpt_sha256": "2" * 64,
                "gpt_geometry_sha256": "1" * 64,
            }
            with (
                mock.patch.object(
                    install_release, "verify_full_backup", return_value=full_state
                ),
                mock.patch.object(
                    install_release, "verify_target_backup", return_value=target_state
                ),
                mock.patch.object(
                    install_release, "probe_live", return_value=live_state
                ),
                mock.patch.object(install_release, "require_same_device"),
                mock.patch.object(
                    install_release, "get_active_slot", return_value="b"
                ),
                mock.patch.object(install_release, "confirm_exact") as confirm,
                mock.patch.object(install_release, "run_edl", side_effect=fake_edl),
            ):
                install_release.flash(
                    manifest,
                    assets,
                    sources,
                    root / "loader.bin",
                    root / "full.img",
                    target_backup,
                )

            writes = [command for command in commands if command[0] == "ws"]
            reads = [command for command in commands if command[0] == "rs"]
            self.assertEqual([command[1] for command in writes], ["20"])
            self.assertTrue(all("--skipresponse" not in command for command in writes))
            self.assertTrue(all("--skipresponse" in command for command in reads))
            confirm.assert_called_once()
            receipt = json.loads(
                (flash_dir / "flash-receipt.json").read_text(encoding="utf-8")
            )
            self.assertTrue(receipt["complete"])
            self.assertEqual(
                [entry["target"] for entry in receipt["verified"]],
                ["first", "second"],
            )

    def test_resume_cannot_reuse_a_stale_readback_file(self) -> None:
        data = b"a"
        digest = hashlib.sha256(data).hexdigest()
        asset = {
            "name": "first.img",
            "target": "first",
            "raw_lba": 10,
            "sectors": 1,
            "size": 1,
            "sha256": digest,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_backup = root / "target"
            flash_dir = target_backup / "flash-v-test"
            flash_dir.mkdir(parents=True)
            stale = flash_dir / "first-resume-check.img"
            stale.write_bytes(data)
            install_lib.write_json(
                flash_dir / "flash-receipt.json",
                {
                    "schema": 1,
                    "release": "v-test",
                    "complete": True,
                    "verified": [
                        {
                            "target": "first",
                            "raw_lba": 10,
                            "sectors": 1,
                            "sha256": digest,
                        }
                    ],
                },
            )
            source = root / "first.img"
            source.write_bytes(data)
            full_state = {
                "sha256": "0" * 64,
                "device_identity": {},
                "gpt_geometry_sha256": "1" * 64,
            }
            with (
                mock.patch.object(
                    install_release, "verify_full_backup", return_value=full_state
                ),
                mock.patch.object(
                    install_release,
                    "verify_target_backup",
                    return_value={
                        "live_primary_gpt_sha256": "2" * 64,
                        "paths": {},
                        "digests": {},
                    },
                ),
                mock.patch.object(
                    install_release,
                    "probe_live",
                    return_value={
                        "primary_gpt_sha256": "2" * 64,
                        "gpt_geometry_sha256": "1" * 64,
                    },
                ),
                mock.patch.object(install_release, "require_same_device"),
                mock.patch.object(
                    install_release, "get_active_slot", return_value="b"
                ),
                mock.patch.object(install_release, "run_edl", return_value=""),
            ):
                with self.assertRaises(SystemExit):
                    install_release.flash(
                        {"release": "v-test"},
                        [asset],
                        {"first.img": source},
                        root / "loader.bin",
                        root / "full.img",
                        target_backup,
                    )
            self.assertFalse(stale.exists())

    def test_in_progress_write_is_promoted_when_live_bytes_match_release(self) -> None:
        release_data = b"r"
        backup_data = b"b"
        digest = hashlib.sha256(release_data).hexdigest()
        asset = {
            "name": "release.img",
            "target": "target",
            "raw_lba": 10,
            "sectors": 1,
            "size": 1,
            "sha256": digest,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_backup = root / "target-backup"
            flash_dir = target_backup / "flash-v-test"
            flash_dir.mkdir(parents=True)
            install_lib.write_json(
                flash_dir / "flash-receipt.json",
                {
                    "schema": 1,
                    "release": "v-test",
                    "complete": False,
                    "in_progress": "target",
                    "verified": [],
                },
            )
            source = root / "release.img"
            source.write_bytes(release_data)
            backup = root / "target-before.img"
            backup.write_bytes(backup_data)
            commands: list[list[str]] = []

            def fake_edl(
                args: list[str], loader: Path, log_path: Path, *, capture: bool = False
            ) -> str:
                del loader, log_path, capture
                commands.append(args)
                if args[0] == "rs":
                    Path(args[3]).write_bytes(release_data)
                return ""

            full_state = {
                "sha256": "0" * 64,
                "device_identity": {},
                "gpt_geometry_sha256": "1" * 64,
            }
            with (
                mock.patch.object(
                    install_release, "verify_full_backup", return_value=full_state
                ),
                mock.patch.object(
                    install_release,
                    "verify_target_backup",
                    return_value={
                        "live_primary_gpt_sha256": "2" * 64,
                        "paths": {"target": backup},
                        "digests": {
                            "target": hashlib.sha256(backup_data).hexdigest()
                        },
                    },
                ),
                mock.patch.object(
                    install_release,
                    "probe_live",
                    return_value={
                        "primary_gpt_sha256": "2" * 64,
                        "gpt_geometry_sha256": "1" * 64,
                    },
                ),
                mock.patch.object(install_release, "require_same_device"),
                mock.patch.object(
                    install_release, "get_active_slot", return_value="b"
                ),
                mock.patch.object(install_release, "confirm_exact") as confirm,
                mock.patch.object(install_release, "run_edl", side_effect=fake_edl),
            ):
                install_release.flash(
                    {"release": "v-test"},
                    [asset],
                    {"release.img": source},
                    root / "loader.bin",
                    root / "full.img",
                    target_backup,
                )

            self.assertFalse(any(command[0] == "ws" for command in commands))
            confirm.assert_not_called()
            receipt = install_lib.load_json(flash_dir / "flash-receipt.json")
            self.assertTrue(receipt["complete"])
            self.assertNotIn("in_progress", receipt)

    def test_device_binding_rejects_serial_mismatch(self) -> None:
        backup = {
            "device_identity": {
                "hwid": "h",
                "chip_serial": "chip",
                "emmc_serial": 1,
                "total_blocks": 2,
                "block_size": 512,
            },
            "gpt_geometry_sha256": "gpt",
        }
        live = {
            **backup["device_identity"],
            "emmc_serial": 2,
            "gpt_geometry_sha256": "gpt",
        }
        with self.assertRaises(SystemExit):
            install_release.require_same_device(backup, live)


if __name__ == "__main__":
    unittest.main()
