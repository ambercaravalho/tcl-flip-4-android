# Using T440W Android

This guide describes the accepted `v0.1.0` release profile. Complete every
post-boot check in the [installation guide](install-v0.1.0.md) first.

## Physical controls

- **Back**: Android Back
- **Home/Power**: Android Home for the mapped Home key; normal power behavior
  remains device-controlled
- **Messages/Envelope**: open Messaging
- **Contacts**: toggle the C9 on-screen cursor
- **D-pad**: move the cursor while C9 is active
- **D-pad center**: click
- **Call/F1 behavior in C9**: conditional vertical page scrolling
- **Contacts again**: disable the cursor and return the D-pad to normal
  navigation

The left/right app-reserved softkeys are intentionally inert outside the
accepted cursor behavior. The on-screen Android navigation bar is disabled
because it is not usable on the 240x320 non-touch panel.

If CONTACTS opens the Contacts application instead of toggling C9, stop and
verify that the baked T440W Key Actions package is version `1.1` / code `2` and
that both accessibility services are enabled. Do not install the obsolete
version-code-1 keypad package.

## First boot

Use the physical keypad and C9 cursor to complete Android setup. Avoid changing
display-composition developer settings; the retained driver requires the
bounded forced-client-composition profile installed by the ROM.

The display helper runs only during startup and stops normally after about one
minute. Persistent helper CPU usage or a flickering/gray physical panel is a
release failure even if ADB screenshots look correct.

## Magisk application root

The root payload is already in `init_boot_b`, but Manager must be installed as
a normal data application:

```bash
adb shell pm install -r -g \
  /system/etc/t440w/release/Magisk-v31.1.apk
adb shell pm path com.topjohnwu.magisk
```

The returned path must be under `/data/app`. A path under `/system/app` or an
“abnormal state” warning is a release failure.

Magisk 31.1 on this image uses a manual **Grant Superuser** list. Unknown apps
do not receive a pop-up and are denied by default:

1. Open Magisk with the C9 cursor.
2. Open **Superuser** / **Grant Superuser**.
3. Enable only the application that should receive root.
4. Remove the grant when it is no longer needed.

ADB shell is not a root app and must remain denied. Do not enable the
research-only rooted-debugging profile from older findings.

## microG

microG Services and Companion are privileged system components. In microG
Self-Check, the required signature-spoofing, Services, Companion, and runtime
permission checks should pass. The optional legacy GsfProxy/C2DM item is not
included and may remain unchecked.

Android's add-account screen exposes a microG-backed **Google** account type.
microG is open source, but enabled features can still communicate with
proprietary Google network services.

## Aurora Store

Aurora Store is a non-privileged system application. The accepted path uses:

- anonymous login;
- normal downloads;
- Android's Session Installer.

Aurora receives neither silent-install privileges nor a root grant. Review
each requested permission and installation prompt normally.

## ADB security

USB debugging is authenticated and non-root:

```bash
adb shell getprop ro.debuggable
adb shell getprop ro.force_debuggable
adb shell getprop service.adb.root
adb shell id
adb root
adb shell id
adb shell 'su -c id; echo exit=$?'
```

Expected results are `ro.debuggable=0`, an empty `ro.force_debuggable`,
`service.adb.root=0`, shell UID 2000 before and after `adb root`, and denied
shell `su`.

Do not infer security state from image contents or a Settings toggle. Verify
the running boot after every update.

## Known limits

- The release has passed on one T440W reference phone.
- Telephony, carrier-specific behavior, cameras, Bluetooth, and broad
  application compatibility do not yet have release acceptance gates.
- The AVB chain uses public AOSP test keys.
- There is no over-the-air updater. Future releases require a new guarded EDL
  procedure.
- Returning to stock requires the same phone's verified full eMMC backup; a
  metadata-only rollback is insufficient.

Report failures with the exact model, current slot, release asset hashes,
runtime fingerprint, and whether the physical panel and keypad passed. Do not
publish full backups or logs containing personal data or device identifiers.
