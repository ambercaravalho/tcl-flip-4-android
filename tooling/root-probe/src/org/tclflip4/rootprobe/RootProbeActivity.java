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
        new Thread(new Runnable() {
            @Override
            public void run() {
                requestRoot(result, cleanupPolicy);
            }
        }, "root-probe").start();
    }

    private void requestRoot(TextView result, boolean cleanupPolicy) {
        StringBuilder output = new StringBuilder();
        int status = -1;
        try {
            String command = "id";
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
