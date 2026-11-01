package org.tclflip4.rootprobe;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.InputStreamReader;

/** Test-only activity that makes one Magisk su request from an application UID. */
public final class RootProbeActivity extends Activity {
    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView result = new TextView(this);
        result.setText("Requesting application root...");
        result.setTextSize(20);
        result.setPadding(16, 16, 16, 16);
        setContentView(result);
        final boolean cleanupPolicy =
                getIntent().getBooleanExtra("cleanup_policy", false);
        final boolean queryComposition =
                getIntent().getBooleanExtra("query_composition", false);
        final boolean enableComposition =
                getIntent().getBooleanExtra("enable_composition", false);
        final boolean holdComposition =
                getIntent().getBooleanExtra("hold_composition", false);
        final boolean sustainComposition =
                getIntent().getBooleanExtra("sustain_composition", false);
        new Thread(new Runnable() {
            @Override
            public void run() {
                requestRoot(
                        result,
                        cleanupPolicy,
                        queryComposition,
                        enableComposition,
                        holdComposition,
                        sustainComposition);
            }
        }, "root-probe").start();
    }

    private void requestRoot(
            TextView result,
            boolean cleanupPolicy,
            boolean queryComposition,
            boolean enableComposition,
            boolean holdComposition,
            boolean sustainComposition) {
        StringBuilder output = new StringBuilder();
        int status = -1;
        try {
            String command = "id";
            if (sustainComposition) {
                command += "; i=0"
                        + "; while [ \"$i\" -lt 60 ]; do"
                        + " service call SurfaceFlinger 1008 i32 1 >/dev/null"
                        + "; i=$((i + 1)); sleep 1; done"
                        + "; service call SurfaceFlinger 1010";
            } else if (holdComposition) {
                command += "; service call SurfaceFlinger 1008 i32 1"
                        + "; service call SurfaceFlinger 1010"
                        + "; sleep 10"
                        + "; service call SurfaceFlinger 1010";
            } else if (enableComposition) {
                command += "; service call SurfaceFlinger 1008 i32 1"
                        + "; service call SurfaceFlinger 1010";
            } else if (queryComposition) {
                command += "; service call SurfaceFlinger 1010";
            }
            if (cleanupPolicy) {
                command += "; /debug_ramdisk/magisk --sqlite "
                        + "\"DELETE FROM policies WHERE uid="
                        + android.os.Process.myUid() + "\"";
            }
            Process process = new ProcessBuilder(
                    "/debug_ramdisk/su", "-c", command)
                    .redirectErrorStream(true).start();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append('\n');
                }
            }
            status = process.waitFor();
        } catch (Exception error) {
            output.append(error);
        }
        final String text = "exit=" + status + "\n" + output;
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                result.setText(text);
            }
        });
    }
}
