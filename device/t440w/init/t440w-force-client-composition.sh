#!/system/bin/sh

# init may report SurfaceFlinger running before its Binder service is visible.
wait_for_surfaceflinger() {
    while true; do
        if /system/bin/service check SurfaceFlinger 2>&1 |
            /system/bin/grep -q "found"; then
            return 0
        fi
        /system/bin/sleep 0.1
    done
}

# Android can reset this runtime-only control after boot has settled. Keep the
# device-required composition contract active for the service lifetime.
while true; do
    wait_for_surfaceflinger
    /system/bin/service call SurfaceFlinger 1008 i32 1 >/dev/null 2>&1
    /system/bin/sleep 1
done
