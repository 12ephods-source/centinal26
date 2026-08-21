package com.frost.bluetoothguard;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class MonitorState {
    private static final String PREFS = "monitor_state";
    private static final String TRUSTED = "trusted_addresses";
    private static final String CONNECTED = "connected_addresses";
    private static final String MULTI_THRESHOLD = "multi_threshold";

    private MonitorState() {}

    public static Set<String> trusted(Context context) {
        Set<String> values = prefs(context).getStringSet(TRUSTED, Collections.emptySet());
        Set<String> normalized = new HashSet<>();
        for (String value : values) normalized.add(WarningEngine.normalizeAddress(value));
        return normalized;
    }

    public static void setTrusted(Context context, Set<String> addresses) {
        Set<String> normalized = new HashSet<>();
        for (String address : addresses) normalized.add(WarningEngine.normalizeAddress(address));
        prefs(context).edit().putStringSet(TRUSTED, normalized).apply();
    }

    public static void clearTrusted(Context context) {
        prefs(context).edit().remove(TRUSTED).apply();
    }

    public static Set<String> connected(Context context) {
        return new HashSet<>(prefs(context).getStringSet(CONNECTED, Collections.emptySet()));
    }

    public static int markConnected(Context context, String address) {
        Set<String> set = connected(context);
        set.add(WarningEngine.normalizeAddress(address));
        prefs(context).edit().putStringSet(CONNECTED, set).apply();
        return set.size();
    }

    public static int markDisconnected(Context context, String address) {
        Set<String> set = connected(context);
        set.remove(WarningEngine.normalizeAddress(address));
        prefs(context).edit().putStringSet(CONNECTED, set).apply();
        return set.size();
    }

    public static List<Long> recordConnection(Context context, String address, long nowMs) {
        String key = historyKey(address);
        String raw = prefs(context).getString(key, "");
        List<Long> kept = new ArrayList<>();
        if (!raw.isBlank()) {
            for (String token : raw.split(",")) {
                try {
                    long value = Long.parseLong(token);
                    if (nowMs - value <= WarningEngine.RAPID_RECONNECT_WINDOW_MS) kept.add(value);
                } catch (NumberFormatException ignored) {
                    // Ignore malformed local state and continue with valid timestamps.
                }
            }
        }
        kept.add(nowMs);
        StringBuilder encoded = new StringBuilder();
        for (Long value : kept) {
            if (encoded.length() > 0) encoded.append(',');
            encoded.append(value);
        }
        prefs(context).edit().putString(key, encoded.toString()).apply();
        return Collections.unmodifiableList(kept);
    }

    public static String previousName(Context context, String address) {
        return prefs(context).getString(nameKey(address), null);
    }

    public static void rememberName(Context context, String address, String name) {
        if (name == null || name.isBlank()) return;
        prefs(context).edit().putString(nameKey(address), name).apply();
    }

    public static int multiDeviceThreshold(Context context) {
        return prefs(context).getInt(MULTI_THRESHOLD, WarningEngine.DEFAULT_MULTI_DEVICE_THRESHOLD);
    }

    public static void setMultiDeviceThreshold(Context context, int threshold) {
        prefs(context).edit().putInt(MULTI_THRESHOLD, Math.max(1, threshold)).apply();
    }

    public static int previousAdapterState(Context context) {
        return prefs(context).getInt("adapter_state", -1);
    }

    public static void setAdapterState(Context context, int state) {
        prefs(context).edit().putInt("adapter_state", state).apply();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static String historyKey(String address) {
        return "history_" + WarningEngine.normalizeAddress(address).replace(':', '_');
    }

    private static String nameKey(String address) {
        return "name_" + WarningEngine.normalizeAddress(address).replace(':', '_');
    }
}
