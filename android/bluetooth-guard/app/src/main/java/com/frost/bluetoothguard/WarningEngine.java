package com.frost.bluetoothguard;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Set;

public final class WarningEngine {
    public enum Severity { INFO, LOW, MEDIUM, HIGH, CRITICAL }

    public static final class Warning {
        public final String code;
        public final Severity severity;
        public final String title;
        public final String detail;

        public Warning(String code, Severity severity, String title, String detail) {
            this.code = Objects.requireNonNull(code);
            this.severity = Objects.requireNonNull(severity);
            this.title = Objects.requireNonNull(title);
            this.detail = Objects.requireNonNull(detail);
        }
    }

    public static final long RAPID_RECONNECT_WINDOW_MS = 10L * 60L * 1000L;
    public static final int RAPID_RECONNECT_THRESHOLD = 3;
    public static final int DEFAULT_MULTI_DEVICE_THRESHOLD = 3;

    private WarningEngine() {}

    public static List<Warning> onConnect(
            String address,
            String name,
            boolean trusted,
            List<Long> recentConnectTimes,
            String previousName,
            int connectedDeviceCount,
            int multiDeviceThreshold) {
        List<Warning> out = new ArrayList<>();
        String label = label(address, name);

        if (!trusted) {
            out.add(new Warning(
                    "UNKNOWN_CONNECTED",
                    Severity.CRITICAL,
                    "Unknown Bluetooth device connected",
                    label + " established an ACL connection and is not trusted."));
        } else {
            out.add(new Warning(
                    "TRUSTED_CONNECTED",
                    Severity.INFO,
                    "Trusted Bluetooth device connected",
                    label + " connected."));
        }

        if (previousName != null && !previousName.isBlank()
                && name != null && !name.isBlank()
                && !previousName.equals(name)) {
            out.add(new Warning(
                    "IDENTITY_NAME_CHANGED",
                    Severity.HIGH,
                    "Bluetooth device name changed",
                    address + " changed name from \"" + previousName + "\" to \"" + name + "\"."));
        }

        if (recentConnectTimes != null && recentConnectTimes.size() >= RAPID_RECONNECT_THRESHOLD) {
            out.add(new Warning(
                    "RAPID_RECONNECT",
                    Severity.HIGH,
                    "Repeated Bluetooth reconnects",
                    label + " connected at least " + RAPID_RECONNECT_THRESHOLD
                            + " times within " + (RAPID_RECONNECT_WINDOW_MS / 60000L) + " minutes."));
        }

        if (connectedDeviceCount > Math.max(1, multiDeviceThreshold)) {
            out.add(new Warning(
                    "MULTIPLE_CONNECTED",
                    Severity.MEDIUM,
                    "Multiple Bluetooth devices connected",
                    connectedDeviceCount + " ACL-connected devices are currently tracked."));
        }

        return Collections.unmodifiableList(out);
    }

    public static List<Warning> onBondChange(String address, String name, int oldBond, int newBond, boolean trusted) {
        List<Warning> out = new ArrayList<>();
        String label = label(address, name);
        if (newBond == 12 && oldBond != 12) {
            out.add(new Warning(
                    "NEW_BOND",
                    trusted ? Severity.LOW : Severity.HIGH,
                    trusted ? "Trusted device paired" : "New untrusted Bluetooth pairing",
                    label + " entered the bonded/paired state."));
        } else if (oldBond == 12 && newBond == 10) {
            out.add(new Warning(
                    "BOND_REMOVED",
                    Severity.MEDIUM,
                    "Bluetooth pairing removed",
                    label + " is no longer bonded/paired."));
        }
        return Collections.unmodifiableList(out);
    }

    public static Warning adapterReenabled() {
        return new Warning(
                "ADAPTER_REENABLED",
                Severity.MEDIUM,
                "Bluetooth was re-enabled",
                "The local Bluetooth adapter transitioned from OFF to ON while monitoring was active.");
    }

    public static Warning monitorDegraded(String detail) {
        return new Warning(
                "MONITOR_DEGRADED",
                Severity.HIGH,
                "Bluetooth monitor degraded",
                detail == null ? "Monitoring encountered an error." : detail);
    }

    public static boolean isAlert(Warning warning) {
        return warning.severity.ordinal() >= Severity.MEDIUM.ordinal();
    }

    public static String normalizeAddress(String address) {
        return address == null ? "UNKNOWN" : address.trim().toUpperCase(Locale.ROOT);
    }

    public static boolean isTrusted(String address, Set<String> trusted) {
        if (trusted == null) return false;
        return trusted.contains(normalizeAddress(address));
    }

    private static String label(String address, String name) {
        String a = normalizeAddress(address);
        if (name == null || name.isBlank()) return a;
        return name + " (" + a + ")";
    }
}
