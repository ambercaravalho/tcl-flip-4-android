#!/system/bin/sh

package="org.tclflip4.keypadcursor"
component="${package}/${package}.KeypadActionService"
c9_package="com.austinauyeung.nyuma.c9"
c9_component="${c9_package}/${c9_package}.accessibility.AppAccessibilityService"

# Package Manager and Settings may become available after boot_completed.
attempt=0
while [ "$attempt" -lt 60 ]; do
    if /system/bin/cmd package path "$package" >/dev/null 2>&1 \
        && /system/bin/cmd package path "$c9_package" >/dev/null 2>&1; then
        break
    fi
    attempt=$((attempt + 1))
    /system/bin/sleep 1
done

if [ "$attempt" -ge 60 ]; then
    exit 1
fi

enabled="$(/system/bin/settings --user 0 get secure enabled_accessibility_services)"
case "$enabled" in
    ""|"null")
        merged="${component}:${c9_component}"
        ;;
    *)
        merged="$enabled"
        case ":$merged:" in
            *:"$component":*) ;;
            *) merged="${merged}:${component}" ;;
        esac
        case ":$merged:" in
            *:"$c9_component":*) ;;
            *) merged="${merged}:${c9_component}" ;;
        esac
        ;;
esac

/system/bin/settings --user 0 put secure enabled_accessibility_services "$merged"
/system/bin/settings --user 0 put secure accessibility_enabled 1
