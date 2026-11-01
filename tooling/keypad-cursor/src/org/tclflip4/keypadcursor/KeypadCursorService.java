package org.tclflip4.keypadcursor;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.accessibilityservice.GestureDescription;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.Toast;

/** System-wide physical-keypad navigation for the TCL Flip 4 5G. */
public final class KeypadCursorService extends AccessibilityService {
    private static final String TAG = "T440WKeypadCursor";

    private static final int SCAN_ENVELOPE = 30;
    private static final int SCAN_DEL = 48;
    private static final int SCAN_ENDCALL = 116;
    private static final int SCAN_CONTACTS = 138;
    private static final int SCAN_SOFT_LEFT = 139;
    private static final int SCAN_SOFT_RIGHT = 158;
    private static final int SCAN_CALL = 231;
    private static final float CURSOR_STEP_PX = 12.0f;
    private static final long MOVE_INITIAL_DELAY_MS = 180;
    private static final long MOVE_REPEAT_DELAY_MS = 50;

    private final Handler movementHandler = new Handler(Looper.getMainLooper());
    private WindowManager windowManager;
    private CursorView cursorView;
    private boolean cursorEnabled;
    private int activeDirection = KeyEvent.KEYCODE_UNKNOWN;
    private final Runnable movementRunnable = new Runnable() {
        @Override
        public void run() {
            if (!cursorEnabled || activeDirection == KeyEvent.KEYCODE_UNKNOWN) {
                return;
            }
            moveCursor(activeDirection);
            movementHandler.postDelayed(this, MOVE_REPEAT_DELAY_MS);
        }
    };

    @Override
    protected void onServiceConnected() {
        AccessibilityServiceInfo info = getServiceInfo();
        info.flags |= AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS;
        setServiceInfo(info);

        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        cursorView = new CursorView();
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.setTitle("T440W Keypad Cursor");
        windowManager.addView(cursorView, params);
        Log.i(TAG, "service connected");
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        // Key filtering and gesture dispatch do not require window contents.
    }

    @Override
    public void onInterrupt() {
        Log.w(TAG, "service interrupted");
    }

    @Override
    protected boolean onKeyEvent(KeyEvent event) {
        final int scanCode = event.getScanCode();
        final int keyCode = event.getKeyCode();
        final boolean down = event.getAction() == KeyEvent.ACTION_DOWN;
        final boolean firstDown = down && event.getRepeatCount() == 0;

        if (scanCode == SCAN_SOFT_RIGHT) {
            boolean needsPrototypeSuppression = keyCode == KeyEvent.KEYCODE_BACK;
            logKey(needsPrototypeSuppression
                    ? "suppress-current-soft-right"
                    : "pass-inert-soft-right", event);
            return needsPrototypeSuppression;
        }

        if (scanCode == SCAN_CONTACTS
                || keyCode == KeyEvent.KEYCODE_CONTACTS) {
            if (firstDown) {
                setCursorEnabled(!cursorEnabled);
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

        if (scanCode == SCAN_SOFT_LEFT) {
            if (firstDown && cursorEnabled) {
                scrollPage(true);
            }
            logKey(cursorEnabled ? "page-up" : "inert-soft-left", event);
            return cursorEnabled || keyCode == KeyEvent.KEYCODE_MENU;
        }

        if (scanCode == SCAN_CALL && cursorEnabled) {
            if (firstDown) {
                scrollPage(false);
            }
            logKey("page-down", event);
            return true;
        }

        if (!cursorEnabled) {
            return false;
        }

        if (isDpadDirection(keyCode)) {
            if (firstDown) {
                startCursorMovement(keyCode);
            } else if (!down) {
                stopCursorMovement(keyCode);
            }
            return true;
        }

        if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER) {
            if (firstDown) {
                clickCursor();
            }
            return true;
        }

        return false;
    }

    @Override
    public void onDestroy() {
        stopCursorMovement(activeDirection);
        if (windowManager != null && cursorView != null) {
            windowManager.removeView(cursorView);
        }
        cursorView = null;
        windowManager = null;
        super.onDestroy();
    }

    private void setCursorEnabled(boolean enabled) {
        cursorEnabled = enabled;
        if (!enabled) {
            stopCursorMovement(activeDirection);
        }
        if (cursorView != null) {
            cursorView.setCursorVisible(enabled);
        }
        Toast.makeText(
                        this,
                        enabled ? "Cursor on" : "Cursor off",
                        Toast.LENGTH_SHORT)
                .show();
        Log.i(TAG, enabled ? "cursor enabled" : "cursor disabled");
    }

    private void startCursorMovement(int keyCode) {
        movementHandler.removeCallbacks(movementRunnable);
        activeDirection = keyCode;
        moveCursor(keyCode);
        movementHandler.postDelayed(movementRunnable, MOVE_INITIAL_DELAY_MS);
    }

    private void stopCursorMovement(int keyCode) {
        if (activeDirection != keyCode) {
            return;
        }
        activeDirection = KeyEvent.KEYCODE_UNKNOWN;
        movementHandler.removeCallbacks(movementRunnable);
    }

    private void moveCursor(int keyCode) {
        if (cursorView == null) {
            return;
        }
        float dx = 0;
        float dy = 0;
        if (keyCode == KeyEvent.KEYCODE_DPAD_UP) {
            dy = -CURSOR_STEP_PX;
        } else if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
            dy = CURSOR_STEP_PX;
        } else if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT) {
            dx = -CURSOR_STEP_PX;
        } else if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) {
            dx = CURSOR_STEP_PX;
        }
        cursorView.move(dx, dy);
        Log.i(TAG, "cursor moved to " + cursorView.getCursorX()
                + "," + cursorView.getCursorY());
    }

    private void clickCursor() {
        if (cursorView == null) {
            return;
        }
        Path path = new Path();
        path.moveTo(cursorView.getCursorX(), cursorView.getCursorY());
        dispatchPath(path, 1, 80, "click");
    }

    private void scrollPage(boolean up) {
        if (cursorView == null) {
            return;
        }
        float x = cursorView.getCursorX();
        float startY = cursorView.getHeight() * (up ? 0.35f : 0.75f);
        float endY = cursorView.getHeight() * (up ? 0.75f : 0.35f);
        Path path = new Path();
        path.moveTo(x, startY);
        path.lineTo(x, endY);
        dispatchPath(path, 0, 300, up ? "page-up" : "page-down");
    }

    private void dispatchPath(Path path, long startMs, long durationMs, String name) {
        GestureDescription gesture = new GestureDescription.Builder()
                .addStroke(new GestureDescription.StrokeDescription(
                        path, startMs, durationMs))
                .build();
        boolean accepted = dispatchGesture(gesture, null, null);
        Log.i(TAG, name + " gesture accepted=" + accepted);
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

    private void logKey(String action, KeyEvent event) {
        Log.i(TAG, action + " scan=" + event.getScanCode()
                + " key=" + event.getKeyCode()
                + " event=" + event.getAction()
                + " repeat=" + event.getRepeatCount());
    }

    private static boolean isDpadDirection(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_DPAD_UP
                || keyCode == KeyEvent.KEYCODE_DPAD_DOWN
                || keyCode == KeyEvent.KEYCODE_DPAD_LEFT
                || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT;
    }

    private final class CursorView extends View {
        private static final float ARROW_WIDTH_PX = 18.0f;
        private static final float ARROW_HEIGHT_PX = 16.0f;
        private final Paint outlinePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint cursorPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private float cursorX = -1;
        private float cursorY = -1;
        private boolean visible;

        CursorView() {
            super(KeypadCursorService.this);
            outlinePaint.setColor(Color.WHITE);
            outlinePaint.setStyle(Paint.Style.STROKE);
            outlinePaint.setStrokeWidth(2.0f);
            outlinePaint.setStrokeJoin(Paint.Join.ROUND);
            cursorPaint.setColor(Color.BLACK);
            cursorPaint.setStyle(Paint.Style.FILL);
        }

        void setCursorVisible(boolean newVisible) {
            visible = newVisible;
            ensurePosition();
            invalidate();
        }

        void move(float dx, float dy) {
            ensurePosition();
            cursorX = clamp(cursorX + dx, 1.0f, getWidth() - ARROW_WIDTH_PX);
            cursorY = clamp(cursorY + dy, 1.0f, getHeight() - ARROW_HEIGHT_PX);
            invalidate();
        }

        float getCursorX() {
            ensurePosition();
            return cursorX;
        }

        float getCursorY() {
            ensurePosition();
            return cursorY;
        }

        @Override
        protected void onSizeChanged(int width, int height, int oldWidth, int oldHeight) {
            super.onSizeChanged(width, height, oldWidth, oldHeight);
            if (cursorX < 0 || cursorY < 0) {
                cursorX = width / 2.0f;
                cursorY = height / 2.0f;
            } else {
                cursorX = clamp(cursorX, 1.0f, width - ARROW_WIDTH_PX);
                cursorY = clamp(cursorY, 1.0f, height - ARROW_HEIGHT_PX);
            }
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            if (!visible) {
                return;
            }
            Path arrow = new Path();
            arrow.moveTo(cursorX, cursorY);
            arrow.lineTo(cursorX + 4.0f, cursorY + 15.0f);
            arrow.lineTo(cursorX + 8.0f, cursorY + 10.0f);
            arrow.lineTo(cursorX + 14.0f, cursorY + 15.0f);
            arrow.lineTo(cursorX + 17.0f, cursorY + 11.0f);
            arrow.lineTo(cursorX + 11.0f, cursorY + 6.0f);
            arrow.lineTo(cursorX + 16.0f, cursorY + 2.0f);
            arrow.close();
            canvas.drawPath(arrow, cursorPaint);
            canvas.drawPath(arrow, outlinePaint);
        }

        private void ensurePosition() {
            if (cursorX < 0 || cursorY < 0) {
                cursorX = Math.max(1.0f, getWidth() / 2.0f);
                cursorY = Math.max(1.0f, getHeight() / 2.0f);
            }
        }

        private float clamp(float value, float minimum, float maximum) {
            return Math.max(minimum, Math.min(value, maximum));
        }
    }
}
