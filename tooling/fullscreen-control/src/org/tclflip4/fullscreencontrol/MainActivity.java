package org.tclflip4.fullscreencontrol;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;

/** One hardware-accelerated full-screen client surface for T440W trace controls. */
@SuppressWarnings("deprecation")
public final class MainActivity extends Activity {
    private ControlView controlView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Window window = getWindow();
        window.setDecorFitsSystemWindows(false);
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);

        controlView = new ControlView();
        setContentView(controlView);
        hideSystemBars();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemBars();
            controlView.requestFocus();
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (isDpadDirection(keyCode)) {
            if (event.getRepeatCount() == 0) {
                controlView.togglePattern();
            }
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public boolean onKeyUp(int keyCode, KeyEvent event) {
        if (isDpadDirection(keyCode)) {
            return true;
        }
        return super.onKeyUp(keyCode, event);
    }

    private void hideSystemBars() {
        WindowInsetsController controller = getWindow().getInsetsController();
        if (controller == null) {
            return;
        }
        controller.hide(
                WindowInsets.Type.statusBars()
                        | WindowInsets.Type.navigationBars()
                        | WindowInsets.Type.captionBar());
        controller.setSystemBarsBehavior(
                WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }

    private static boolean isDpadDirection(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_DPAD_UP
                || keyCode == KeyEvent.KEYCODE_DPAD_DOWN
                || keyCode == KeyEvent.KEYCODE_DPAD_LEFT
                || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT;
    }

    private final class ControlView extends View {
        private final Paint paint = new Paint();
        private boolean alternate;

        ControlView() {
            super(MainActivity.this);
            setFocusable(true);
            setFocusableInTouchMode(true);
            setKeepScreenOn(true);
            setLayerType(View.LAYER_TYPE_HARDWARE, null);
        }

        void togglePattern() {
            alternate = !alternate;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            int width = getWidth();
            int height = getHeight();

            if (alternate) {
                paint.setColor(Color.rgb(0, 255, 0));
                canvas.drawRect(0, 0, width / 2.0f, height, paint);
                paint.setColor(Color.rgb(255, 0, 255));
                canvas.drawRect(width / 2.0f, 0, width, height, paint);
            } else {
                paint.setColor(Color.rgb(0, 80, 255));
                canvas.drawRect(0, 0, width, height / 2.0f, paint);
                paint.setColor(Color.rgb(255, 220, 0));
                canvas.drawRect(0, height / 2.0f, width, height, paint);
            }
        }
    }
}
