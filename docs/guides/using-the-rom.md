# Use T440W Android

## Controls

- **Back**: Android Back
- **Home/Power**: Android Home; normal power behavior is unchanged
- **Messages**: open Messaging
- **Contacts**: toggle the C9 cursor
- **D-pad / center**: move and click while the cursor is active
- **Call/F1**: page scroll where supported

Press Contacts again to return the D-pad to normal navigation. The on-screen
navigation bar is disabled for the non-touch 240x320 display.

## First boot

Use the keypad and C9 cursor for setup. Do not change display-composition
developer settings. A flickering or gray panel is a failure even if ADB
screenshots look normal.

Run the security check after every install:

```bash
tooling/scripts/verify-post-boot.sh
```

Also verify the display and every physical control yourself.

## Apps and root

microG Services and Companion are included. Aurora Store supports anonymous
login, normal downloads, and Android's Session Installer.

Install Magisk Manager after the post-boot checks:

```bash
adb shell pm install -r -g /system/etc/t440w/release/Magisk-v31.1.apk
```

Grant root only to chosen apps in Magisk's Superuser screen. Apps are denied by
default; ADB shell must remain unprivileged.

## Limits and updates

Telephony, cameras, Bluetooth, carrier behavior, and broad app compatibility
are not yet release-tested. There is no OTA updater; rerun the
[guided installer](install.md) for a newer supported release.

Returning to stock requires the verified full backup made for that physical
phone. Backups and logs may contain personal data and device identifiers.
