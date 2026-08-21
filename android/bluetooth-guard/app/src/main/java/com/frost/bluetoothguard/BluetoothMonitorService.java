package com.frost.bluetoothguard;

import android.Manifest;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.IBinder;
import java.util.List;
import java.util.Set;

public final class BluetoothMonitorService extends Service {
    public static final String ACTION_START = "com.frost.bluetoothguard.START";
    public static final String ACTION_STOP = "com.frost.bluetoothguard.STOP";
    private boolean registered;

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            try {
                handleBluetoothEvent(intent, this);
            } catch (SecurityException e) {
                handleDegraded("Bluetooth permission denied while handling " + intent.getAction());
            } catch (RuntimeException e) {
                handleDegraded("Monitor error for " + intent.getAction() + ": " + e.getClass().getSimpleName());
            }
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        AlertNotifier.ensureChannels(this);
        startForeground(AlertNotifier.FOREGROUND_ID,
                AlertNotifier.foreground(this, "Watching connection, bond, identity, and adapter events"));
        registerBluetoothReceiver();
        EvidenceStore.appendEvent(this, "MONITOR_STARTED", "", "", "Foreground monitor started.",
                android.os.Process.myUid(), getPackageName());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!hasBluetoothPermission()) handleDegraded("BLUETOOTH_CONNECT permission is not granted.");
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (registered) {
            try {
                unregisterReceiver(receiver);
            } catch (IllegalArgumentException ignored) {
            }
            registered = false;
        }
        EvidenceStore.appendEvent(this, "MONITOR_STOPPED", "", "", "Foreground monitor stopped.",
                android.os.Process.myUid(), getPackageName());
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void registerBluetoothReceiver() {
        IntentFilter filter = new IntentFilter();
        filter.addAction(BluetoothDevice.ACTION_ACL_CONNECTED);
        filter.addAction(BluetoothDevice.ACTION_ACL_DISCONNECTED);
        filter.addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED);
        filter.addAction(BluetoothDevice.ACTION_NAME_CHANGED);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) filter.addAction(BluetoothDevice.ACTION_ALIAS_CHANGED);
        filter.addAction(BluetoothAdapter.ACTION_STATE_CHANGED);
        filter.addAction(BluetoothAdapter.ACTION_CONNECTION_STATE_CHANGED);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED);
        } else {
            registerReceiver(receiver, filter);
        }
        registered = true;
    }

    private void handleBluetoothEvent(Intent intent, BroadcastReceiver sourceReceiver) {
        String action = intent.getAction();
        if (action == null) return;
        int senderUid = Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE
                ? sourceReceiver.getSentFromUid() : -1;
        String senderPackage = Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE
                ? sourceReceiver.getSentFromPackage() : "";

        if (BluetoothAdapter.ACTION_STATE_CHANGED.equals(action)) {
            int newState = intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR);
            int previous = intent.getIntExtra(BluetoothAdapter.EXTRA_PREVIOUS_STATE,
                    MonitorState.previousAdapterState(this));
            String hash = EvidenceStore.appendEvent(this, "ADAPTER_STATE", "", "",
                    "previous=" + previous + ", current=" + newState, senderUid, senderPackage);
            if (previous == BluetoothAdapter.STATE_OFF && newState == BluetoothAdapter.STATE_ON) {
                emitWarning(WarningEngine.adapterReenabled(), "", "", hash);
            }
            MonitorState.setAdapterState(this, newState);
            return;
        }

        BluetoothDevice device = getDevice(intent);
        String address = device == null ? "UNKNOWN" : safeAddress(device);
        String name = device == null ? "" : safeName(device);
        Set<String> trusted = MonitorState.trusted(this);
        boolean isTrusted = WarningEngine.isTrusted(address, trusted);

        if (BluetoothDevice.ACTION_ACL_CONNECTED.equals(action)) {
            long now = System.currentTimeMillis();
            List<Long> history = MonitorState.recordConnection(this, address, now);
            String previousName = MonitorState.previousName(this, address);
            int count = MonitorState.markConnected(this, address);
            String transport = String.valueOf(intent.getIntExtra(BluetoothDevice.EXTRA_TRANSPORT, -1));
            String hash = EvidenceStore.appendEvent(this, "ACL_CONNECTED", address, name,
                    "transport=" + transport + ", trusted=" + isTrusted + ", connected_count=" + count,
                    senderUid, senderPackage);
            for (WarningEngine.Warning warning : WarningEngine.onConnect(address, name, isTrusted, history,
                    previousName, count, MonitorState.multiDeviceThreshold(this))) {
                emitWarning(warning, address, name, hash);
            }
            MonitorState.rememberName(this, address, name);
            return;
        }

        if (BluetoothDevice.ACTION_ACL_DISCONNECTED.equals(action)) {
            int count = MonitorState.markDisconnected(this, address);
            EvidenceStore.appendEvent(this, "ACL_DISCONNECTED", address, name, "connected_count=" + count,
                    senderUid, senderPackage);
            return;
        }

        if (BluetoothDevice.ACTION_BOND_STATE_CHANGED.equals(action)) {
            int oldBond = intent.getIntExtra(BluetoothDevice.EXTRA_PREVIOUS_BOND_STATE, BluetoothDevice.ERROR);
            int newBond = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, BluetoothDevice.ERROR);
            String hash = EvidenceStore.appendEvent(this, "BOND_STATE", address, name,
                    "previous=" + oldBond + ", current=" + newBond + ", trusted=" + isTrusted,
                    senderUid, senderPackage);
            for (WarningEngine.Warning warning : WarningEngine.onBondChange(address, name, oldBond, newBond,
                    isTrusted)) emitWarning(warning, address, name, hash);
            return;
        }

        if (BluetoothDevice.ACTION_NAME_CHANGED.equals(action)
                || (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
                && BluetoothDevice.ACTION_ALIAS_CHANGED.equals(action))) {
            String previousName = MonitorState.previousName(this, address);
            String hash = EvidenceStore.appendEvent(this, "IDENTITY_CHANGED", address, name,
                    "previous_name=" + previousName, senderUid, senderPackage);
            if (previousName != null && !previousName.isBlank() && name != null && !name.isBlank()
                    && !previousName.equals(name)) {
                emitWarning(new WarningEngine.Warning("IDENTITY_NAME_CHANGED", WarningEngine.Severity.HIGH,
                        "Bluetooth device identity changed", address + " changed name from \"" + previousName
                        + "\" to \"" + name + "\"."), address, name, hash);
            }
            MonitorState.rememberName(this, address, name);
            return;
        }

        if (BluetoothAdapter.ACTION_CONNECTION_STATE_CHANGED.equals(action)) {
            int state = intent.getIntExtra(BluetoothAdapter.EXTRA_CONNECTION_STATE, -1);
            int previous = intent.getIntExtra(BluetoothAdapter.EXTRA_PREVIOUS_CONNECTION_STATE, -1);
            EvidenceStore.appendEvent(this, "ADAPTER_CONNECTION_STATE", address, name,
                    "previous=" + previous + ", current=" + state, senderUid, senderPackage);
        }
    }

    private void emitWarning(WarningEngine.Warning warning, String address, String name, String eventHash) {
        EvidenceStore.appendWarning(this, warning, address, name, eventHash);
        AlertNotifier.warning(this, warning);
    }

    private void handleDegraded(String detail) {
        String hash = EvidenceStore.appendEvent(this, "MONITOR_DEGRADED", "", "", detail,
                android.os.Process.myUid(), getPackageName());
        emitWarning(WarningEngine.monitorDegraded(detail), "", "", hash);
    }

    private boolean hasBluetoothPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.S
                || checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED;
    }

    @SuppressWarnings("deprecation")
    private static BluetoothDevice getDevice(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            return intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice.class);
        }
        return intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE);
    }

    private String safeAddress(BluetoothDevice device) {
        try {
            return WarningEngine.normalizeAddress(device.getAddress());
        } catch (SecurityException e) {
            return "PERMISSION_DENIED";
        }
    }

    private String safeName(BluetoothDevice device) {
        try {
            String alias = Build.VERSION.SDK_INT >= Build.VERSION_CODES.R ? device.getAlias() : null;
            if (alias != null && !alias.isBlank()) return alias;
            String name = device.getName();
            return name == null ? "" : name;
        } catch (SecurityException e) {
            return "";
        }
    }
}
