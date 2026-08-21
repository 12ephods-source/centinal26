package com.frost.bluetoothguard;

import android.content.Context;
import android.content.SharedPreferences;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public final class EvidenceStore {
    private static final String PREFS = "evidence_chain";
    private static final String KEY_HEAD = "chain_head";
    private static final String KEY_SEQ = "sequence";
    private static final Object LOCK = new Object();

    private EvidenceStore() {}

    public static String appendEvent(Context context, String eventType, String address, String name,
            String detail, int senderUid, String senderPackage) {
        synchronized (LOCK) {
            SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            String prev = prefs.getString(KEY_HEAD, "GENESIS");
            long seq = prefs.getLong(KEY_SEQ, 0L) + 1L;
            String timestamp = Instant.now().toString();
            String payload = "{" + "\"seq\":" + seq + "," + "\"timestamp\":\"" + esc(timestamp)
                    + "\"," + "\"event_type\":\"" + esc(eventType) + "\"," + "\"address\":\""
                    + esc(address) + "\"," + "\"name\":\"" + esc(name) + "\"," + "\"detail\":\""
                    + esc(detail) + "\"," + "\"sender_uid\":" + senderUid + ","
                    + "\"sender_package\":\"" + esc(senderPackage) + "\"," + "\"prev_hash\":\""
                    + esc(prev) + "\"}";
            String eventHash = sha256(prev + "\n" + payload);
            String line = payload.substring(0, payload.length() - 1) + ",\"event_hash\":\"" + eventHash + "\"}\n";
            append(context, "bluetooth_events.jsonl", line);
            prefs.edit().putString(KEY_HEAD, eventHash).putLong(KEY_SEQ, seq).apply();
            return eventHash;
        }
    }

    public static void appendWarning(Context context, WarningEngine.Warning warning,
            String address, String name, String eventHash) {
        String line = "{" + "\"timestamp\":\"" + esc(Instant.now().toString()) + "\"," + "\"code\":\""
                + esc(warning.code) + "\"," + "\"severity\":\"" + esc(warning.severity.name()) + "\","
                + "\"title\":\"" + esc(warning.title) + "\"," + "\"detail\":\"" + esc(warning.detail)
                + "\"," + "\"address\":\"" + esc(address) + "\"," + "\"name\":\"" + esc(name)
                + "\"," + "\"event_hash\":\"" + esc(eventHash) + "\"}\n";
        append(context, "bluetooth_alerts.jsonl", line);
    }

    public static File buildExportZip(Context context) throws IOException {
        File out = new File(context.getCacheDir(), "frost_bluetooth_evidence_" + System.currentTimeMillis() + ".zip");
        try (ZipOutputStream zos = new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(out)))) {
            addIfPresent(zos, new File(context.getFilesDir(), "bluetooth_events.jsonl"));
            addIfPresent(zos, new File(context.getFilesDir(), "bluetooth_alerts.jsonl"));
            SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            String manifest = "{\n  \"created_at\": \"" + esc(Instant.now().toString()) + "\",\n"
                    + "  \"event_chain_head\": \"" + esc(prefs.getString(KEY_HEAD, "GENESIS")) + "\",\n"
                    + "  \"event_count\": " + prefs.getLong(KEY_SEQ, 0L) + "\n}\n";
            zos.putNextEntry(new ZipEntry("manifest.json"));
            zos.write(manifest.getBytes(StandardCharsets.UTF_8));
            zos.closeEntry();
        }
        return out;
    }

    public static String currentHead(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_HEAD, "GENESIS");
    }

    public static long currentCount(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getLong(KEY_SEQ, 0L);
    }

    private static void addIfPresent(ZipOutputStream zos, File file) throws IOException {
        if (!file.isFile()) return;
        zos.putNextEntry(new ZipEntry(file.getName()));
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) zos.write(buf, 0, n);
        }
        zos.closeEntry();
    }

    private static void append(Context context, String fileName, String line) {
        try (FileOutputStream out = context.openFileOutput(fileName, Context.MODE_APPEND)) {
            out.write(line.getBytes(StandardCharsets.UTF_8));
            out.flush();
        } catch (IOException e) {
            throw new IllegalStateException("Unable to append evidence", e);
        }
    }

    private static String sha256(String value) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(64);
            for (byte b : digest) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String esc(String value) {
        if (value == null) return "";
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
                .replace("\r", "\\r").replace("\t", "\\t");
    }
}
