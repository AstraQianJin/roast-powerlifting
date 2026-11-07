package com.roast.exdark;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * RPL ExDark · Pocket HUD
 *
 * 纯 Java WebView，零第三方依赖，无联网权限。
 * 单文件 HTML 全部打进 assets，训练数据只写本机 localStorage。
 */
public class MainActivity extends Activity {

    private WebView webView;
    private StoreBridge storeBridge;
    private static final int REQ_EXPORT_CSV = 1001;
    private static final int REQ_IMPORT_CSV = 1002;
    private static final int REQ_EXPORT_XLSX = 1003;
    private static final int REQ_EXPORT_DOC = 1004;
    private static final int REQ_GEAR_PHOTO = 1005;
    private ValueCallback<Uri[]> fileChooserCallback;
    private File pendingCsvFile;
    private String pendingPhotoKey;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        // targetSdk 35+ 起窗口强制边到边；但 decor 默认仍会把内容框内缩到系统栏以内，
        // 结果状态栏那条永远是窗口底色。关掉它，让网页自己铺满并按 --safe-t 让位。
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
        }

        // 首帧前预读已存主题，避免亮色主题冷启动出现“黑底→白底”闪屏
        if (readSavedThemeIsLight()) {
            chromeBg = 0xFFF2F5F8;
            chromeLight = true;
        }
        computeInsets();
        applyChromeColors();   // 窗口/根布局/系统栏在 WebView 加载前即落色

        webView = findViewById(R.id.webview);

        if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowFileAccessFromFileURLs(false);
        ws.setAllowUniversalAccessFromFileURLs(false);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        ws.setUseWideViewPort(true);
        ws.setLoadWithOverviewMode(true);
        ws.setBuiltInZoomControls(false);
        ws.setDisplayZoomControls(false);
        ws.setSupportZoom(false);
        ws.setDefaultTextEncodingName("UTF-8");
        ws.setTextZoom(100);
        ws.setCacheMode(WebSettings.LOAD_NO_CACHE);

        webView.setBackgroundColor(chromeBg);
        storeBridge = new StoreBridge();
        webView.addJavascriptInterface(storeBridge, "AndroidBridge");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                pushInsets();
                applyChromeColors();
            }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage cm) {
                android.util.Log.e("REXJS", cm.message() + " @" + cm.lineNumber());
                return true;
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> filePathCallback,
                                             FileChooserParams params) {
                fileChooserCallback = filePathCallback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES, chooserMimes(params));
                try {
                    startActivityForResult(intent, REQ_IMPORT_CSV);
                } catch (Throwable t) {
                    fileChooserCallback = null;
                    return false;
                }
                return true;
            }
        });

        webView.loadUrl("file:///android_asset/index.html");
    }

    /** 选择器的 MIME 过滤跟着 &lt;input accept&gt; 走：写死 text/* 会让 .xlsx 在系统选择器里灰掉选不动。 */
    private static String[] chooserMimes(WebChromeClient.FileChooserParams params) {
        java.util.ArrayList<String> out = new java.util.ArrayList<String>();
        String[] accept = params == null ? null : params.getAcceptTypes();
        if (accept != null) {
            for (String a : accept) {
                if (a == null) continue;
                String t = a.trim().toLowerCase();
                if (t.indexOf('/') > 0) out.add(t);
                else if (t.equals(".csv")) {
                    out.add("text/csv");
                    out.add("text/plain");
                    out.add("text/comma-separated-values");
                } else if (t.equals(".xlsx")) {
                    out.add("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                } else if (t.equals(".json")) {
                    out.add("application/json");
                }
            }
        }
        if (out.isEmpty()) out.add("*/*");
        return out.toArray(new String[0]);
    }

    /** API 30+ 的系统栏图标明暗。单独成方法，避免旧系统校验到新类。 */
    private void applyBarsApi30(boolean isLight) {
        try {
            android.view.WindowInsetsController ic = getWindow().getInsetsController();
            if (ic == null) return;
            int mask = android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                    | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
            ic.setSystemBarsAppearance(isLight ? mask : 0, mask);
        } catch (Throwable ignored) {
        }
    }

    // 最近一次主题色，页面重载后要重放（否则亮色主题会闪回深色状态栏）
    private int chromeBg = 0xFF07090D;
    private boolean chromeLight = false;
    private float insetTopDp = 0;
    private float insetBotDp = 0;

    /** 首帧前读取已存主题是否为亮色（读前 4KB 足够命中 theme 字段） */
    private boolean readSavedThemeIsLight() {
        try {
            File f = new File(getFilesDir(), "roast_state.json");
            if (!f.exists() || f.length() == 0) return false;
            FileInputStream in = new FileInputStream(f);
            byte[] buf = new byte[4096];
            int n = in.read(buf);
            in.close();
            return new String(buf, 0, n, "UTF-8").contains("\"theme\":\"light\"");
        } catch (Exception e) {
            return false;
        }
    }

    private void applyChromeColors(String bgHex, boolean isLight) {
        try {
            chromeBg = Color.parseColor(bgHex);
            chromeLight = isLight;
            applyChromeColors();
        } catch (Exception ignored) {
        }
    }

    private void applyChromeColors() {
        try {
            int c = chromeBg;
            getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(c));
            getWindow().addFlags(
                    android.view.WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
            getWindow().setStatusBarColor(c);
            getWindow().setNavigationBarColor(c);
            View root = findViewById(R.id.root);
            if (root != null) root.setBackgroundColor(c);
            if (webView != null) webView.setBackgroundColor(c);
            if (android.os.Build.VERSION.SDK_INT >= 30) applyBarsApi30(chromeLight);
        } catch (Throwable ignored) {
        }
    }

    /** 边到边之后，状态栏 / 手势条的高度改由网页自己让位（CSS 变量 --safe-t / --safe-b）。 */
    private void computeInsets() {
        int topPx = 0, botPx = 0;
        try {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.view.WindowInsets wi =
                        getWindow().getDecorView().getRootWindowInsets();
                if (wi != null) {
                    android.graphics.Insets i = wi.getInsets(
                            android.view.WindowInsets.Type.systemBars()
                                    | android.view.WindowInsets.Type.displayCutout());
                    topPx = i.top;
                    botPx = i.bottom;
                }
            }
        } catch (Throwable ignored) {
        }
        if (topPx == 0) {
            int rid = getResources().getIdentifier("status_bar_height", "dimen", "android");
            if (rid > 0) topPx = getResources().getDimensionPixelSize(rid);
        }
        float d = getResources().getDisplayMetrics().density;
        insetTopDp = topPx / d;
        insetBotDp = botPx / d;
    }

    private void pushInsets() {
        if (webView == null) return;
        computeInsets();
        String js = "document.documentElement.style.setProperty('--safe-t','" + insetTopDp + "px');"
                + "document.documentElement.style.setProperty('--safe-b','" + insetBotDp + "px');";
        webView.evaluateJavascript(js, null);
    }

    /**
     * 本地存档桥：WebView 的 localStorage 是异步落盘的，进程被强杀会丢数据。
     * 训练日志不能丢，所以主存档写应用私有目录（同步写 + 临时文件替换）。
     */
    private class StoreBridge {
        /**
         * 主题联动：网页切亮/暗时把窗口底色、状态栏、导航栏一起换掉，
         * 否则亮色主题下会留一条深色状态栏。light="1" 时状态栏图标转深色。
         */
        @JavascriptInterface
        public void setChrome(final String bgHex, final String light) {
            runOnUiThread(new Runnable() {
                public void run() {
                    applyChromeColors(bgHex, "1".equals(light));
                }
            });
        }

        /** 同步返回安全区（dp），供 <head> 阻塞脚本首帧前设置 --safe-t / --safe-b。 */
        @JavascriptInterface
        public String getInsetsJson() {
            computeInsets();
            return "{\"t\":" + insetTopDp + ",\"b\":" + insetBotDp + "}";
        }

        /** 导出 CSV：先写私有缓存，再走系统 ACTION_CREATE_DOCUMENT 保存到用户选择的位置。 */
        @JavascriptInterface
        public void exportCsv(final String filename, final String csvContent) {
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        File f = new File(getFilesDir(), filename);
                        FileOutputStream out = new FileOutputStream(f);
                        out.write(csvContent.getBytes("UTF-8"));
                        out.flush();
                        out.close();
                        pendingCsvFile = f;
                        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                        intent.addCategory(Intent.CATEGORY_OPENABLE);
                        intent.setType("text/csv");
                        intent.putExtra(Intent.EXTRA_TITLE, filename);
                        startActivityForResult(intent, REQ_EXPORT_CSV);
                    } catch (Exception e) {
                        if (webView != null) webView.evaluateJavascript("toast('CSV export failed')", null);
                    }
                }
            });
        }

        /** 导出计划工作簿：base64 解码后走与 CSV 同一条 CREATE_DOCUMENT 通道（复用 pendingCsvFile，导出永不并发）。 */
        @JavascriptInterface
        public void exportPlanXlsx(final String filename, final String b64) {
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        File f = new File(getFilesDir(), filename);
                        FileOutputStream out = new FileOutputStream(f);
                        out.write(android.util.Base64.decode(b64, android.util.Base64.DEFAULT));
                        out.flush();
                        out.close();
                        pendingCsvFile = f;
                        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                        intent.addCategory(Intent.CATEGORY_OPENABLE);
                        intent.setType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
                        intent.putExtra(Intent.EXTRA_TITLE, filename);
                        startActivityForResult(intent, REQ_EXPORT_XLSX);
                    } catch (Exception e) {
                        if (webView != null) webView.evaluateJavascript("toast('plan export failed')", null);
                    }
                }
            });
        }

        /** 通用文档导出（JSON 信封等文本载体）：base64 解码 → 私有缓存 → CREATE_DOCUMENT，MIME 由前端契约给定。 */
        @JavascriptInterface
        public void exportDoc(final String filename, final String mime, final String b64) {
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        File f = new File(getFilesDir(), filename);
                        FileOutputStream out = new FileOutputStream(f);
                        out.write(android.util.Base64.decode(b64, android.util.Base64.DEFAULT));
                        out.flush();
                        out.close();
                        pendingCsvFile = f;
                        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                        intent.addCategory(Intent.CATEGORY_OPENABLE);
                        intent.setType(mime != null && !mime.isEmpty() ? mime : "application/octet-stream");
                        intent.putExtra(Intent.EXTRA_TITLE, filename);
                        startActivityForResult(intent, REQ_EXPORT_DOC);
                    } catch (Exception e) {
                        if (webView != null) webView.evaluateJavascript("toast('export failed')", null);
                    }
                }
            });
        }

        /* 装备照片三桥（v0.43）：pick=系统选择器→压缩落应用私有目录；data=同步回 JPEG base64（空串=无图）；
           del=删文件。照片只存私有文件，永不进任何 JSON 分片——导入导出、四路分片与它完全无关。 */
        @JavascriptInterface
        public void gearPickPhoto(final String gearId) {
            final String key = photoKey(gearId);
            if (key == null) return;
            runOnUiThread(new Runnable() {
                public void run() {
                    try {
                        pendingPhotoKey = key;
                        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                        intent.addCategory(Intent.CATEGORY_OPENABLE);
                        intent.setType("image/*");
                        startActivityForResult(intent, REQ_GEAR_PHOTO);
                    } catch (Throwable t) {
                        pendingPhotoKey = null;
                        if (webView != null) webView.evaluateJavascript("toast('photo picker failed')", null);
                    }
                }
            });
        }

        /** 同步读图：返回 JPEG 的 base64（无图为空串）。文件不存在或超 PHOTO_MAX_BYTES 都按无图处理。 */
        @JavascriptInterface
        public String gearPhotoData(String gearId) {
            String key = photoKey(gearId);
            if (key == null) return "";
            try {
                File f = new File(getFilesDir(), "gearphoto_" + key + ".jpg");
                if (!f.exists() || f.length() == 0 || f.length() > PHOTO_MAX_BYTES) return "";
                FileInputStream in = new FileInputStream(f);
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) != -1) bos.write(buf, 0, n);
                in.close();
                return android.util.Base64.encodeToString(bos.toByteArray(), android.util.Base64.NO_WRAP);
            } catch (Exception e) {
                return "";
            }
        }

        @JavascriptInterface
        public void gearDelPhoto(String gearId) {
            String key = photoKey(gearId);
            if (key == null) return;
            try {
                new File(getFilesDir(), "gearphoto_" + key + ".jpg").delete();
            } catch (Exception ignored) {
            }
        }

        /* 四路分片：轻量偏好 / 动作库增量 / 训练账本 / 归档计划原文。旧单文件仅用于一次性迁移。 */
        private static final String F_LEGACY = "roast_state.json";
        private static final String F_PREFS  = "roast_prefs.json";
        private static final String F_WORK   = "roast_workout.json";
        private static final String F_LIB    = "roast_lib_diff.json";
        private static final String F_ARCHIVE = "roast_plan_archive.json";

        @JavascriptInterface public String loadStore()   { return readStore(F_LEGACY); }
        @JavascriptInterface public String loadPrefs()   { return readStore(F_PREFS); }
        @JavascriptInterface public String loadWorkout() { return readStore(F_WORK); }
        @JavascriptInterface public String loadLibDiff() { return readStore(F_LIB); }
        @JavascriptInterface public String loadPlanArchive() { return readStore(F_ARCHIVE); }

        /* 磁盘探针：把每个分片「实际有多少字节」报给前端。
           readStore() 对「文件不存在」和「读挂了」都返回空串，前端分不出来；
           而「磁盘上有账、读出来是空」恰恰是必须停在只读、绝不能拿默认空账本覆盖的场景。
           值：-1 = 文件不在；>=0 = 文件字节数。手拼 JSON，不引 org.json 依赖。 */
        @JavascriptInterface public String storeProbe() {
            String[] names = {F_LEGACY, F_PREFS, F_WORK, F_LIB, F_ARCHIVE};
            StringBuilder sb = new StringBuilder("{");
            for (int i = 0; i < names.length; i++) {
                long len = -1;
                try {
                    File f = new File(getFilesDir(), names[i]);
                    if (f.exists()) len = f.length();
                } catch (Exception e) { len = -1; }
                if (i > 0) sb.append(',');
                sb.append('"').append(names[i]).append("\":").append(len);
            }
            sb.append('}');
            return sb.toString();
        }

        @JavascriptInterface public void savePrefs(String json)   { enqueue(F_PREFS, json); }
        @JavascriptInterface public void saveWorkout(String json) { enqueue(F_WORK, json); }
        @JavascriptInterface public void saveLibDiff(String json) { enqueue(F_LIB, json); }
        @JavascriptInterface public void savePlanArchive(String json) { enqueue(F_ARCHIVE, json); }
        @JavascriptInterface public void saveStore(String json)   { enqueue(F_LEGACY, json); }

        private String readStore(String name) {
            try {
                File f = new File(getFilesDir(), name);
                if (!f.exists() || f.length() == 0) return "";
                FileInputStream in = new FileInputStream(f);
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) != -1) bos.write(buf, 0, n);
                in.close();
                return new String(bos.toByteArray(), "UTF-8");
            } catch (Exception e) {
                return "";
            }
        }

        /* 单线程串行写盘：主线程只做一次入队；同名文件 latest-wins 合并，跨文件保持先后顺序。 */
        private final ExecutorService storeExec = Executors.newSingleThreadExecutor();
        private final java.util.LinkedHashMap<String, String> pending = new java.util.LinkedHashMap<>();
        private final Object storeLock = new Object();
        private volatile boolean storeBusy = false;

        /* 写盘失败绝不静默：记下「文件名: 原因」，同名文件后续写成功时清除；
           失败的那一笔回队重试（最多 3 次），超限则保留错误串交给前端提示。 */
        private volatile String lastError = "";
        private final java.util.HashMap<String, Integer> failedTimes = new java.util.HashMap<>();

        @JavascriptInterface
        public String lastStoreError() { return lastError; }

        private void enqueue(String name, String json) {
            synchronized (storeLock) {
                pending.put(name, json);          // 同名覆盖 = 只留最新
                if (storeBusy) return;
                storeBusy = true;
            }
            storeExec.execute(new Runnable() {
                @Override public void run() {
                    while (true) {
                        String name, payload;
                        synchronized (storeLock) {
                            if (pending.isEmpty()) { storeBusy = false; return; }
                            java.util.Iterator<java.util.Map.Entry<String, String>> it = pending.entrySet().iterator();
                            java.util.Map.Entry<String, String> e = it.next();
                            name = e.getKey(); payload = e.getValue();
                            it.remove();
                        }
                        if (writeStoreAtomically(name, payload)) {
                            synchronized (storeLock) { failedTimes.remove(name); }
                            continue;
                        }
                        /* 失败的那一笔回队，最多连续 3 次；放弃后循环继续处理其余分片，
                           绝不让 storeBusy 卡在 true（否则后续入队再也无人消费）。 */
                        synchronized (storeLock) {
                            int n = failedTimes.containsKey(name) ? failedTimes.get(name) + 1 : 1;
                            failedTimes.put(name, n);
                            if (n < 3 && !pending.containsKey(name)) pending.put(name, payload);
                            else failedTimes.remove(name);  // 磁盘旧内容仍在，下次入队重新计次
                        }
                    }
                }
            });
        }

        /* 切后台/锁屏时等待队列写完（最多 400ms），确保最后一笔不丢 */
        void flush() {
            long end = System.currentTimeMillis() + 400;
            while (storeBusy && System.currentTimeMillis() < end) {
                try { Thread.sleep(10); } catch (InterruptedException e) { break; }
            }
        }

        /* 退出时把队列里最后一笔写完再收线程池 */
        void flushAndShutdown() {
            flush();
            storeExec.shutdown();
            try { storeExec.awaitTermination(800, TimeUnit.MILLISECONDS); } catch (InterruptedException e) { }
        }

        /* POSIX rename 会直接覆盖同名目标，所以先试一步替换；只有个别机型对已存在目标
           返回 false，那时才走 .bak 过渡——保证任何时刻磁盘上至少留得下一份完整存档。 */
        private boolean writeStoreAtomically(String name, String json) {
            File dir = getFilesDir();
            File tmp = new File(dir, name + ".tmp");
            File dst = new File(dir, name);
            try {
                FileOutputStream out = new FileOutputStream(tmp);
                out.write(json.getBytes("UTF-8"));
                out.flush();
                out.close();
                if (tmp.renameTo(dst)) { clearError(name); return true; }
                if (!dst.exists()) { fail(name, "改名失败且目标存档不存在"); return false; }
                File bak = new File(dir, name + ".bak");
                if (!dst.renameTo(bak)) { fail(name, "旧存档改名失败"); return false; }
                if (!tmp.renameTo(dst)) {
                    if (bak.renameTo(dst)) fail(name, "新内容改名失败（旧存档已回滚）");
                    else fail(name, "旧存档回滚失败，请从 " + name + ".bak 手动恢复");
                    return false;
                }
                bak.delete();
                clearError(name);
                return true;
            } catch (Exception e) {
                fail(name, e.getClass().getSimpleName() + ": " + e.getMessage());
                return false;
            }
        }

        private void clearError(String name) {
            if (lastError.startsWith(name + ":")) lastError = "";
        }

        private void fail(String name, String why) {
            lastError = name + ": " + why;
            android.util.Log.e("REXSTORE", lastError);
        }
    }

    @Override
    public void onBackPressed() {
        if (webView == null) {
            super.onBackPressed();
            return;
        }
        webView.evaluateJavascript(
                "(function(){try{return (window.__handleBack&&window.__handleBack())?'true':'false'}catch(e){return 'false'}})()",
                value -> {
                    if (value != null && value.contains("true")) return;
                    if (webView.canGoBack()) {
                        webView.goBack();
                    } else {
                        finish();
                    }
                });
    }

    @Override
    protected void onPause() {
        /* 切后台/锁屏：先等四分片队列写完，再暂停 WebView */
        if (storeBridge != null) storeBridge.flush();
        if (webView != null) webView.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }

    @Override
    protected void onDestroy() {
        if (storeBridge != null) storeBridge.flushAndShutdown();
        if (webView != null) {
            ViewGroup parent = (ViewGroup) webView.getParent();
            if (parent != null) parent.removeView(webView);
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }

    /* 照片大小三限：源文件超 PHOTO_SRC_MAX_BYTES 拒收（个别云相册 provider 报不出长度，也一并拒收）；
       成品最长边压到 PHOTO_EDGE_MAX、JPEG 重编码超 PHOTO_MAX_BYTES 时逐级降质量（80→60→40），都不行按失败处理。 */
    private static final long PHOTO_SRC_MAX_BYTES = 10L * 1024 * 1024;
    private static final long PHOTO_MAX_BYTES = 200L * 1024;
    private static final int PHOTO_EDGE_MAX = 512;

    /** 文件名只认 id 的安全子集（gearKit 的 id 形如 g<base36>-<n>），杜绝路径拼注。 */
    private static String photoKey(String raw) {
        if (raw == null) return null;
        String k = raw.replaceAll("[^A-Za-z0-9-]", "");
        return (k.length() > 0 && k.length() <= 64) ? k : null;
    }

    private boolean saveGearPhoto(Uri uri, String key) {
        try {
            android.content.ContentResolver cr = getContentResolver();
            android.content.res.AssetFileDescriptor fd = cr.openAssetFileDescriptor(uri, "r");
            long srcLen = fd == null ? -1 : fd.getLength();
            if (fd != null) fd.close();
            if (srcLen <= 0 || srcLen > PHOTO_SRC_MAX_BYTES) return false;
            android.graphics.BitmapFactory.Options b = new android.graphics.BitmapFactory.Options();
            b.inJustDecodeBounds = true;
            java.io.InputStream pin = cr.openInputStream(uri);
            android.graphics.BitmapFactory.decodeStream(pin, null, b);
            pin.close();
            if (b.outWidth <= 0 || b.outHeight <= 0) return false;
            int sample = 1;
            while ((b.outWidth / sample) > PHOTO_EDGE_MAX * 2 || (b.outHeight / sample) > PHOTO_EDGE_MAX * 2) sample *= 2;
            android.graphics.BitmapFactory.Options d = new android.graphics.BitmapFactory.Options();
            d.inSampleSize = sample;
            java.io.InputStream din = cr.openInputStream(uri);
            android.graphics.Bitmap bmp = android.graphics.BitmapFactory.decodeStream(din, null, d);
            din.close();
            if (bmp == null) return false;
            int w = bmp.getWidth(), h = bmp.getHeight(), edge = Math.max(w, h);
            if (edge > PHOTO_EDGE_MAX) {
                float kk = PHOTO_EDGE_MAX / (float) edge;
                bmp = android.graphics.Bitmap.createScaledBitmap(bmp,
                        Math.max(1, Math.round(w * kk)), Math.max(1, Math.round(h * kk)), true);
            }
            int[] qs = {80, 60, 40};
            for (int i = 0; i < qs.length; i++) {
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                if (bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG, qs[i], bos)
                        && bos.size() <= PHOTO_MAX_BYTES) {
                    FileOutputStream out = new FileOutputStream(new File(getFilesDir(), "gearphoto_" + key + ".jpg"));
                    out.write(bos.toByteArray());
                    out.flush();
                    out.close();
                    return true;
                }
            }
            return false;
        } catch (Throwable t) {
            return false;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        // CSV / 计划工作簿（xlsx）/ 通用文档（JSON 信封等）共用同一条落盘→SAF→流拷贝链；导出不会并发，pendingCsvFile 复用安全
        if (requestCode == REQ_EXPORT_CSV || requestCode == REQ_EXPORT_XLSX || requestCode == REQ_EXPORT_DOC) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingCsvFile != null) {
                try {
                    Uri uri = data.getData();
                    FileInputStream in = new FileInputStream(pendingCsvFile);
                    android.content.ContentResolver cr = getContentResolver();
                    java.io.OutputStream out = cr.openOutputStream(uri);
                    if (out != null) {
                        byte[] buf = new byte[8192];
                        int n;
                        while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
                        out.flush();
                        out.close();
                    }
                    in.close();
                    // N04：导出成功提示统一由前端弹出，此处不再重复 Toast（避免双弹）
                } catch (Exception e) {
                    if (webView != null) webView.evaluateJavascript("toast('export failed')", null);
                }
            }
            pendingCsvFile = null;
        } else if (requestCode == REQ_IMPORT_CSV) {
            if (fileChooserCallback != null) {
                Uri[] uris = (resultCode == RESULT_OK && data != null && data.getData() != null)
                        ? new Uri[]{ data.getData() } : null;
                fileChooserCallback.onReceiveValue(uris);
                fileChooserCallback = null;
            }
        } else if (requestCode == REQ_GEAR_PHOTO) {
            String key = pendingPhotoKey;
            pendingPhotoKey = null;
            if (key != null && webView != null) {
                boolean ok = false;
                if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                    ok = saveGearPhoto(data.getData(), key);
                }
                if (!ok) {
                    // 失败不留半张：旧图一并清掉（语义=这次没选成，缩略位回到占位）
                    new File(getFilesDir(), "gearphoto_" + key + ".jpg").delete();
                    webView.evaluateJavascript("toast('photo failed')", null);
                }
                webView.evaluateJavascript("try{kitPhotoDone('" + key + "')}catch(e){}", null);
            }
        }
    }
}
