package com.frost.bluetoothguard;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

public final class AlertNotifier {
    public static final String CHANNEL_MONITOR = "frost_bt_monitor";
    public static final String CHANNEL_ALERTS = "frost_bt_alerts";
    public static final int FOREGROUND_ID = 26001;

    private AlertNotifier() {}

    public static void ensureChannels(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = context.getSystemService(NotificationManager.class);
        NotificationChannel monitor = new NotificationChannel(
                CHANNEL_MONITOR, "Bluetooth Guard monitoring", NotificationManager.IMPORTANCE_LOW);
        monitor.setDescription("Persistent Bluetooth connection monitoring status.");
        NotificationChannel alerts = new NotificationChannel(
                CHANNEL_ALERTS, "Bluetooth Guard warnings", NotificationManager.IMPORTANCE_HIGH);
        alerts.setDescription("Connection, pairing, identity-change, and monitor-health warnings.");
        alerts.enableVibration(true);
        nm.createNotificationChannel(monitor);
        nm.createNotificationChannel(alerts);
    }

    public static Notification foreground(Context context, String text) {
        PendingIntent pi = PendingIntent.getActivity(context, 0, new Intent(context, MainActivity.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = new Notification.Builder(context)
                .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
                .setContentTitle("Frost Bluetooth Guard active")
                .setContentText(text)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setContentIntent(pi);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) b.setChannelId(CHANNEL_MONITOR);
        return b.build();
    }

    public static void warning(Context context, WarningEngine.Warning warning) {
        if (!WarningEngine.isAlert(warning)) return;
        PendingIntent pi = PendingIntent.getActivity(context, warning.code.hashCode(),
                new Intent(context, MainActivity.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = new Notification.Builder(context)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle(warning.title)
                .setContentText(warning.detail)
                .setStyle(new Notification.BigTextStyle().bigText(warning.detail))
                .setAutoCancel(true)
                .setContentIntent(pi);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) b.setChannelId(CHANNEL_ALERTS);
        context.getSystemService(NotificationManager.class)
                .notify((warning.code + System.nanoTime()).hashCode(), b.build());
    }
}
