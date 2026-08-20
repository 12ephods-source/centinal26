package com.robertfrost.learningos;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ApplicationInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {
    private static final int CREATE_EVIDENCE_DOCUMENT = 1001;
    private static final String DEBUG_ACTION = "com.robertfrost.learningos.DEBUG_TEST";
    private static final String DEBUG_RESULT_FILE = "flos_debug_result.txt";

    private WebView webView;
    private String pendingEvidenceJson;
    private BroadcastReceiver debugReceiver;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setTextZoom(100);

        webView.addJavascriptInterface(new AndroidBridge(), "FrostAndroid");
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        registerDebugTestReceiver();
        webView.loadUrl("file:///android_asset/index.html");
    }

    private final class AndroidBridge {
        @JavascriptInterface
        public void exportEvidence(String json) {
            if (json == null || json.isEmpty()) {
                return;
            }
            runOnUiThread(() -> {
                pendingEvidenceJson = json;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/json");
                intent.putExtra(Intent.EXTRA_TITLE, "frost-learning-evidence.json");
                startActivityForResult(intent, CREATE_EVIDENCE_DOCUMENT);
            });
        }
    }

    private boolean isDebuggable() {
        return (getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
    }

    private void registerDebugTestReceiver() {
        if (!isDebuggable()) {
            return;
        }
        debugReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                String op = intent.getStringExtra("op");
                String value = intent.getStringExtra("value");
                runOnUiThread(() -> runDebugOperation(op, value));
            }
        };
        IntentFilter filter = new IntentFilter(DEBUG_ACTION);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(debugReceiver, filter, Context.RECEIVER_EXPORTED);
        } else {
            registerReceiver(debugReceiver, filter);
        }
    }

    private String snapshotScript() {
        return "(()=>JSON.stringify({"
                + "title:document.querySelector('h1')?.textContent||'',"
                + "question:document.querySelector('#question')?.textContent||'',"
                + "feedback:document.querySelector('#feedback')?.innerText||'',"
                + "teacherAction:document.querySelector('#teacherAction')?.innerText||'',"
                + "evidenceCount:document.querySelector('#evidenceCount')?.textContent||'',"
                + "studentHidden:!!document.querySelector('#student')?.hidden,"
                + "teacherHidden:!!document.querySelector('#teacher')?.hidden,"
                + "evidenceHidden:!!document.querySelector('#evidence')?.hidden"
                + "}))()";
    }

    private void runDebugOperation(String op, String value) {
        if (!isDebuggable() || webView == null) {
            return;
        }
        writeDebugResult("PENDING");
        String script;
        if ("snapshot".equals(op)) {
            script = snapshotScript();
        } else if ("answer".equals(op)) {
            String quoted = JSONObject.quote(value == null ? "" : value);
            script = "(()=>{const e=document.querySelector('#answer');"
                    + "if(!e)return JSON.stringify({error:'NO_ANSWER'});"
                    + "e.value=" + quoted + ";document.querySelector('#submit')?.click();"
                    + "return JSON.stringify({question:document.querySelector('#question')?.textContent||'',"
                    + "feedback:document.querySelector('#feedback')?.innerText||''});})()";
        } else if ("next".equals(op)) {
            script = "(()=>{const b=document.querySelector('#nextBtn');"
                    + "if(!b)return JSON.stringify({error:'NO_NEXT'});b.click();"
                    + "return JSON.stringify({question:document.querySelector('#question')?.textContent||''});})()";
        } else if ("tab".equals(op)) {
            String tab = value == null ? "" : value;
            if (!("student".equals(tab) || "teacher".equals(tab) || "evidence".equals(tab))) {
                writeDebugResult("INVALID_TAB");
                return;
            }
            String quoted = JSONObject.quote(tab);
            script = "(()=>{document.querySelector('.tab[data-tab='+" + quoted + "+']')?.click();"
                    + "return " + snapshotScript().substring(4) + ";})()";
        } else if ("export".equals(op)) {
            script = "(()=>{document.querySelector('#export')?.click();return 'EXPORT_REQUESTED';})()";
        } else if ("reset".equals(op)) {
            script = "(()=>{document.querySelector('#reset')?.click();return 'RESET_REQUESTED';})()";
        } else {
            writeDebugResult("INVALID_OPERATION");
            return;
        }
        webView.evaluateJavascript(script, this::writeDebugResult);
    }

    private void writeDebugResult(String result) {
        if (!isDebuggable()) {
            return;
        }
        try (FileOutputStream output = openFileOutput(DEBUG_RESULT_FILE, MODE_PRIVATE)) {
            output.write((result == null ? "null" : result).getBytes(StandardCharsets.UTF_8));
            output.flush();
        } catch (Exception ignored) {
            // Debug-test evidence must never change production app behavior.
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != CREATE_EVIDENCE_DOCUMENT) {
            return;
        }
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            pendingEvidenceJson = null;
            return;
        }
        Uri uri = data.getData();
        String json = pendingEvidenceJson;
        pendingEvidenceJson = null;
        if (json == null) {
            return;
        }
        try (OutputStream output = getContentResolver().openOutputStream(uri, "wt")) {
            if (output == null) {
                throw new IllegalStateException("Unable to open export destination");
            }
            output.write(json.getBytes(StandardCharsets.UTF_8));
            output.flush();
            Toast.makeText(this, "Evidence exported", Toast.LENGTH_SHORT).show();
        } catch (Exception error) {
            Toast.makeText(this, "Evidence export failed", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (debugReceiver != null) {
            unregisterReceiver(debugReceiver);
            debugReceiver = null;
        }
        if (webView != null) {
            webView.removeJavascriptInterface("FrostAndroid");
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
