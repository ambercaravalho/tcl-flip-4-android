# T440W Android 14

An experimental Android ROM for the TCL Flip 4 5G / Go Flip 5G (T440W).
It provides a stable physical display, keypad navigation, a D-pad cursor,
microG, Aurora Store, and optional per-app root.

It has been tested on one T-Mobile T440W. Do not use it on another model or
storage layout. Qualcomm EDL writes can permanently brick a phone, so the
installer requires a verified full backup and checks every write before reboot.

## Install

On macOS or Linux, clone this repository and run:

```bash
tooling/scripts/install-release.sh
```

The guided installer downloads the latest supported release, verifies the
phone and images, creates rollback backups, flashes slot B, and reads every
written range back. You will need Python 3, ADB, about 65 GiB free, and a
data-capable USB cable.

Read the short [installation guide](docs/guides/install.md) before starting.

## Current state

Working:

- Android 14 on the stock kernel and vendor stack
- 240x320 physical display
- physical navigation and toggleable D-pad cursor
- microG and Aurora Store
- enforcing SELinux, non-root ADB, and Magisk-managed app root

Telephony, cameras, Bluetooth, carrier behavior, and broad app compatibility
are not yet release-tested. AVB uses public AOSP test keys.

## More

- [Use the ROM](docs/guides/using-the-rom.md)
- [Recover from a failed install](docs/runbooks/backup-and-restore.md)
- [Research and maintainer documentation](docs/README.md)

License and notices: [LICENSE](LICENSE), [NOTICE](NOTICE).
