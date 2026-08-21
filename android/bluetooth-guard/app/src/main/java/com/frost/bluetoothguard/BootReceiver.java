package com.frost.bluetoothguard;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

public final class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) return;
        Intent service = new Intent(context, BluetoothMonitorService.class)
                .setAction(BluetoothMonitorService.ACTION_START);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(service);
            else context.startService(service);
        } catch (RuntimeException e) {
            String hash = EvidenceStore.appendEvent(context, "BOOT_START_FAILED", "", "",
                    e.getClass().getSimpleName(), android.os.Process.myUid(), context.getPackageName());
            WarningEngine.Warning warning = WarningEngine.monitorDegraded(
                    "Monitor could not restart after boot: " + e.getClass().getSimpleName());
            EvidenceStore.appendWarning(context, warning, "", "", hash);
        }
    }
}
