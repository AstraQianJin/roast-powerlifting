/**
 * tmpclean.js — 回归脚本共用的 Chrome 临时目录回收。
 *
 * 每套无头回归都用 `--user-data-dir` 起一份一次性 Chrome profile。Windows 上 Chrome
 * 进程没真正退出之前，那份目录是被锁住的，此时 `fs.rmSync` 直接 EBUSY/EPERM；过去
 * 四套脚本都是「删失败就算了」，于是 %TEMP% 里积下两百多份、约 2.6 GB 没人认领的目录
 * （xlsxv 更狠：profile 之外还装着 fixture 与 App 写出的工作簿，单份 15–20 MB）。
 *
 * 用法：spawn 之后把 chrome 句柄和目录交给 close()，并在 process.exit 之前 await 它。
 * close() 只等 Chrome 退出、只重试删除，任何一步失败都不抛错、不影响判定。
 */
const fs = require('fs');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function alive(chrome) {
  return chrome && chrome.exitCode === null && chrome.signalCode === null;
}

/* keep=true：红了留现场（xlsxv 的既有约定），什么都不删，直接返回 false。 */
async function close(chrome, dir, keep) {
  if (keep || !dir) return false;
  if (alive(chrome)) {
    try { chrome.kill(); } catch (e) {}
    for (let i = 0; i < 20 && alive(chrome); i++) await sleep(100);
  }
  for (let i = 0; i < 10; i++) {
    try { fs.rmSync(dir, { recursive: true, force: true }); return true; }
    catch (e) { await sleep(200); }
  }
  return false;
}

module.exports = { close };
