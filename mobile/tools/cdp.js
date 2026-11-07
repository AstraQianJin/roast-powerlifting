// cdp.js — 通过 Chrome DevTools Protocol 直连设备上的 FitX WebView
// 前置：debug 构建已开启 WebView.setWebContentsDebuggingEnabled
// 用法：
//   node Tools/cdp.js eval "1+1"
//   node Tools/cdp.js text            // 打印当前页面可见文本（前 N 字符）
//   node Tools/cdp.js tap 300 500     // 派发一次点击
const { execFileSync } = require("child_process");

const ADB = process.env.ADB || "C:/Users/Astra/AppData/Local/Android/Sdk/platform-tools/adb.exe";
const PORT = 9222;

function sh(args) {
  return execFileSync(ADB, args, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}

async function main() {
  const mode = process.argv[2] || "eval";
  const arg = process.argv.slice(3).join(" ");

  let pid = "";
  try { pid = (sh(["shell", "pidof", "com.roast.exdark"]) || "").trim().split(/\s+/)[0] } catch (e) { }
  if (!pid) { console.error("!! 应用未运行"); process.exit(1) }
  sh(["forward", "tcp:" + PORT, "localabstract:webview_devtools_remote_" + pid]);

  const list = await (await fetch("http://127.0.0.1:" + PORT + "/json/list")).json();
  const page = list.find(x => x.type === "page") || list[0];
  if (!page) { console.error("!! 无可用页面"); process.exit(1) }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id) }
  };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(res => {
    const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params: params || {} }));
  });

  if (mode === "tapcss" || mode === "tapel") {
    const st = await send("Runtime.evaluate", {
      expression: "JSON.stringify({dpr:devicePixelRatio,sb:24*devicePixelRatio})", returnByValue: true
    });
    const { dpr, sb } = JSON.parse(st.result.result.value);
    let cx, cy;
    if (mode === "tapcss") {
      const [x, y] = arg.split(/\s+/).map(Number); cx = x; cy = y;
    } else {
      const r = await send("Runtime.evaluate", {
        expression: "(function(){var e=document.querySelector(" + JSON.stringify(arg) + ");if(!e)return 'null';e.scrollIntoView({block:'center'});var b=e.getBoundingClientRect();return JSON.stringify({x:b.x+b.width/2,y:b.y+b.height/2})})()",
        returnByValue: true
      });
      const v = JSON.parse(r.result.result.value);
      if (v === "null") { console.error("!! 元素未找到:", arg); process.exit(1) }
      cx = v.x; cy = v.y;
    }
    await new Promise(r => setTimeout(r, 400));
    const dx = Math.round(cx * dpr), dy = Math.round(cy * dpr + sb);
    sh(["shell", "input", "touchscreen", "tap", String(dx), String(dy)]);
    await new Promise(r => setTimeout(r, 1200));
    console.log("tapped", arg, "=> device", dx, dy);
  } else if (mode === "tap") {
    const [x, y] = arg.split(/\s+/).map(Number);
    await send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y }] });
    await send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await new Promise(r => setTimeout(r, 900));
    console.log("tapped", x, y);
  } else {
    const expr = mode === "text"
      ? "document.body.innerText.slice(0, 4000)"
      : arg;
    const r = await send("Runtime.evaluate", {
      expression: expr, awaitPromise: true, returnByValue: true, userGesture: true
    });
    if (r.result && r.result.exceptionDetails) {
      console.error("EXC:", JSON.stringify(r.result.exceptionDetails.exception && r.result.exceptionDetails.exception.description || r.result.exceptionDetails));
      process.exit(1);
    }
    const v = r.result && r.result.result && r.result.result.value;
    console.log(typeof v === "string" ? v : JSON.stringify(v));
  }
  ws.close();
}
main().catch(e => { console.error("!!", e.message); process.exit(1) });
