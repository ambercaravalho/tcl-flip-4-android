package org.tclflip4.keypadcursor;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;
import android.widget.Toast;

/**
 * T440W global key actions that are outside C9's maintained cursor scope.
 *
 * <p>Back and Home are static keylayout mappings. C9 owns cursor movement,
 * click, and conditional scrolling; this service only toggles C9 and launches
 * Messaging. The legacy DEL/ENDCALL branches retain reversible-prototype
 * compatibility and are unreachable with the final keylayouts.</p>
 */
public final class KeypadActionService extends AccessibilityService {
    private static final String TAG = "T440WKeyActions";
    private static final String C9_PACKAGE = "com.austinauyeung.nyuma.c9";
    private static final String C9_TOGGLE_ACTIVITY =
            C9_PACKAGE + ".shortcuts.StandardCursorActivity";

    private static final int SCAN_ENVELOPE = 30;
    private static final int SCAN_DEL = 48;
    private static final int SCAN_ENDCALL = 116;
    private static final int SCAN_CONTACTS = 138;
    private static final int SCAN_SOFT_RIGHT = 158;

    @Override
    protected void onServiceConnected() {
        AccessibilityServiceInfo info = getServiceInfo();
        info.flags |= AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS;
        setServiceInfo(info);
        Log.i(TAG, "service connected");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Global key filtering does not require window contents.
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "service interrupted");
    }

    @Override
    protected boolean onKeyEvent(KeyEvent event) {
        final int scanCode = event.getScanCode();
        final int keyCode = event.getKeyCode();
        final boolean firstDown = event.getAction() == KeyEvent.ACTION_DOWN
                && event.getRepeatCount() == 0;

        if (scanCode == SCAN_SOFT_RIGHT) {
            // Suppress only the old prototype BACK mapping; final F2 is inert.
            return keyCode == KeyEvent.KEYCODE_BACK;
        }

        if (scanCode == SCAN_CONTACTS
                || keyCode == KeyEvent.KEYCODE_CONTACTS) {
            if (firstDown) {
                toggleC9Cursor();
            }
            return true;
        }

        if (scanCode == SCAN_ENVELOPE
                || keyCode == KeyEvent.KEYCODE_ENVELOPE) {
            if (firstDown) {
                launchMessaging();
            }
            return true;
        }

        if (scanCode == SCAN_DEL || keyCode == KeyEvent.KEYCODE_DEL) {
            if (firstDown) {
                runGlobalAction(GLOBAL_ACTION_BACK, "back");
            }
            return true;
        }

        if (scanCode == SCAN_ENDCALL
                || keyCode == KeyEvent.KEYCODE_ENDCALL) {
            if (firstDown) {
                runGlobalAction(GLOBAL_ACTION_HOME, "home");
            }
            return true;
        }

        return false;
    }

    private void toggleC9Cursor() {
        Intent intent = new Intent();
        intent.setComponent(new ComponentName(C9_PACKAGE, C9_TOGGLE_ACTIVITY));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(intent);
            Log.i(TAG, "requested C9 standard-cursor toggle");
        } catch (ActivityNotFoundException exception) {
            Log.e(TAG, "C9 cursor activity unavailable", exception);
            Toast.makeText(this, "Cursor unavailable", Toast.LENGTH_SHORT).show();
        }
    }

    private void runGlobalAction(int action, String name) {
        boolean accepted = performGlobalAction(action);
        Log.i(TAG, name + " action accepted=" + accepted);
    }

    private void launchMessaging() {
        Intent selector = Intent.makeMainSelectorActivity(
                Intent.ACTION_MAIN, Intent.CATEGORY_APP_MESSAGING);
        selector.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(selector);
            Log.i(TAG, "launched messaging selector");
            return;
        } catch (ActivityNotFoundException exception) {
            Log.w(TAG, "messaging selector unresolved; trying smsto", exception);
        }

        Intent fallback = new Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:"));
        fallback.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(fallback);
            Log.i(TAG, "launched smsto fallback");
        } catch (ActivityNotFoundException exception) {
            Log.e(TAG, "no messaging activity", exception);
            Toast.makeText(this, "Messaging unavailable", Toast.LENGTH_SHORT).show();
        }
    }
}
