package com.frost.bluetoothguard;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class MainActivity extends Activity {
    private static final int REQ_PERMISSIONS = 2601;
    private static final int REQ_EXPORT = 2602;
    private TextView status;
    private File pendingExport;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        requestNeededPermissions();
        refreshStatus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 32, 32, 32);
        scroll.addView(root);

        TextView title = new TextView(this);
        title.setText("Frost Bluetooth Guard");
        title.setTextSize(24f);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title);

        TextView explanation = new TextView(this);
        explanation.setText("Constant connection monitoring. Nearby advertisements are intentionally not treated as connections. Trust only devices you have reviewed.");
        explanation.setPadding(0, 16, 0, 16);
        root.addView(explanation);

        status = new TextView(this);
        status.setTextIsSelectable(true);
        root.addView(status);

        Button start = button("Start / keep monitoring");
        start.setOnClickListener(v -> startMonitoring());
        root.addView(start);

        Button stop = button("Stop monitoring");
        stop.setOnClickListener(v -> {
            stopService(new Intent(this, BluetoothMonitorService.class));
            Toast.makeText(this, "Bluetooth Guard stopped", Toast.LENGTH_SHORT).show();
            refreshStatus();
        });
        root.addView(stop);

        Button trust = button("Trust all currently bonded devices");
        trust.setOnClickListener(v -> trustCurrentBondedDevices());
        root.addView(trust);

        Button clear = button("Clear trusted-device baseline");
        clear.setOnClickListener(v -> {
            MonitorState.clearTrusted(this);
            Toast.makeText(this, "Trusted-device baseline cleared", Toast.LENGTH_SHORT).show();
            refreshStatus();
        });
        root.addView(clear);

        Button export = button("Export evidence ZIP");
        export.setOnClickListener(v -> exportEvidence());
        root.addView(export);

        Button battery = button("Open battery settings");
        battery.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.parse("package:" + getPackageName()))));
        root.addView(battery);

        Button permissions = button("Request Bluetooth / notification permissions");
        permissions.setOnClickListener(v -> requestNeededPermissions());
        root.addView(permissions);
        return scroll;
    }

    private Button button(String text) {
        Button b = new Button(this);
        b.setText(text);
        return b;
    }

    private void startMonitoring() {
        if (!hasBluetoothConnectPermission()) {
            requestNeededPermissions();
            Toast.makeText(this, "Grant Nearby devices permission first", Toast.LENGTH_LONG).show();
            return;
        }
        Intent intent = new Intent(this, BluetoothMonitorService.class)
                .setAction(BluetoothMonitorService.ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent);
        else startService(intent);
        Toast.makeText(this, "Bluetooth Guard monitoring active", Toast.LENGTH_SHORT).show();
        refreshStatus();
    }

    private void trustCurrentBondedDevices() {
        if (!hasBluetoothConnectPermission()) {
            requestNeededPermissions();
            return;
        }
        BluetoothManager manager = getSystemService(BluetoothManager.class);
        BluetoothAdapter adapter = manager == null ? null : manager.getAdapter();
        if (adapter == null) {
            Toast.makeText(this, "Bluetooth adapter unavailable", Toast.LENGTH_LONG).show();
            return;
        }
        try {
            Set<String> trusted = new HashSet<>(MonitorState.trusted(this));
            for (BluetoothDevice device : adapter.getBondedDevices()) {
                trusted.add(WarningEngine.normalizeAddress(device.getAddress()));
                MonitorState.rememberName(this, device.getAddress(), safeDeviceName(device));
            }
            MonitorState.setTrusted(this, trusted);
            EvidenceStore.appendEvent(this, "TRUST_BASELINE_UPDATED", "", "",
                    "trusted_count=" + trusted.size(), android.os.Process.myUid(), getPackageName());
            Toast.makeText(this, trusted.size() + " bonded device(s) trusted", Toast.LENGTH_SHORT).show();
            refreshStatus();
        } catch (SecurityException e) {
            requestNeededPermissions();
        }
    }

    private void exportEvidence() {
        try {
            pendingExport = EvidenceStore.buildExportZip(this);
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("application/zip")
                    .putExtra(Intent.EXTRA_TITLE, pendingExport.getName());
            startActivityForResult(intent, REQ_EXPORT);
        } catch (Exception e) {
            Toast.makeText(this, "Unable to build evidence export: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_EXPORT || resultCode != RESULT_OK || data == null
                || data.getData() == null || pendingExport == null) return;
        try (FileInputStream in = new FileInputStream(pendingExport);
             OutputStream out = getContentResolver().openOutputStream(data.getData())) {
            if (out == null) throw new IllegalStateException("No output stream");
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) out.write(buf, 0, n);
            out.flush();
            Toast.makeText(this, "Evidence ZIP exported", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Export failed: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void refreshStatus() {
        if (status == null) return;
        Set<String> trusted = MonitorState.trusted(this);
        Set<String> connected = MonitorState.connected(this);
        StringBuilder sb = new StringBuilder();
        sb.append("Bluetooth permission: ").append(hasBluetoothConnectPermission() ? "GRANTED" : "NOT GRANTED").append('\n');
        sb.append("Trusted devices: ").append(trusted.size()).append('\n');
        sb.append("Currently tracked ACL connections: ").append(connected.size()).append('\n');
        sb.append("Evidence events: ").append(EvidenceStore.currentCount(this)).append('\n');
        sb.append("Evidence chain head: ").append(EvidenceStore.currentHead(this)).append('\n');
        if (!trusted.isEmpty()) {
            sb.append("\nTrusted addresses:\n");
            List<String> ordered = new ArrayList<>(trusted);
            java.util.Collections.sort(ordered);
            for (String address : ordered) sb.append(" • ").append(address).append('\n');
        }
        status.setText(sb.toString());
    }

    private boolean hasBluetoothConnectPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.S
                || checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    private void requestNeededPermissions() {
        List<String> permissions = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        if (!permissions.isEmpty()) requestPermissions(permissions.toArray(new String[0]), REQ_PERMISSIONS);
    }

    private String safeDeviceName(BluetoothDevice device) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                String alias = device.getAlias();
                if (alias != null && !alias.isBlank()) return alias;
            }
            String name = device.getName();
            return name == null ? "" : name;
        } catch (SecurityException e) {
            return "";
        }
    }
}
