#!/system/bin/sh

# init may report SurfaceFlinger running before its Binder service is visible.
wait_for_surfaceflinger() {
    wait_attempt=0
    while [ "$wait_attempt" -lt 50 ]; do
        if /system/bin/service check SurfaceFlinger 2>&1 |
            /system/bin/grep -q "found"; then
            return 0
        fi
        wait_attempt=$((wait_attempt + 1))
        /system/bin/sleep 0.1
    done
    return 1
}

# SurfaceFlinger restarts early and Android reapplies developer-option defaults
# late in boot. Reassert for one minute, then exit instead of polling forever.
reassert_attempt=0
while [ "$reassert_attempt" -lt 13 ]; do
    wait_for_surfaceflinger || exit 1
    /system/bin/service call SurfaceFlinger 1008 i32 1 >/dev/null 2>&1
    reassert_attempt=$((reassert_attempt + 1))
    if [ "$reassert_attempt" -lt 13 ]; then
        /system/bin/sleep 5
    fi
done

exit 0
