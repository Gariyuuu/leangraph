// Browser smoke test of the built site: every route, desktop + phone, console errors, overflow, screenshots.
// Usage: node scripts/site_smoke.mjs [outDir]   (run `cd site && npm run build` first)
// Playwright is resolved from PLAYWRIGHT_DIR (a node_modules dir containing `playwright`) or normal resolution.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import net from "node:net";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const pw = process.env.PLAYWRIGHT_DIR ? require(path.join(process.env.PLAYWRIGHT_DIR, "playwright")) : require("playwright");
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const outDir = path.resolve(process.argv[2] ?? path.join(root, "results", "site_smoke"));
fs.mkdirSync(outDir, { recursive: true });

const freePort = () => new Promise((res) => { const s = net.createServer(); s.listen(0, () => { const p = s.address().port; s.close(() => res(p)); }); });
const port = await freePort();
const server = spawn("npx", ["next", "start", "-p", String(port)], { cwd: path.join(root, "site"), stdio: ["ignore", "pipe", "pipe"] });
const base = `http://127.0.0.1:${port}`;
let ready = false;
for (let i = 0; i < 90 && !ready; i++) {
  try { ready = (await fetch(base + "/")).ok; } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 1000));
}
if (!ready) { server.kill(); console.error(`site did not start on ${base} within 90 s`); process.exit(2); }

const theorems = JSON.parse(fs.readFileSync(path.join(root, "site", "data", "theorems.json"), "utf-8"));
const solved = theorems.find((t) => t.solved_by && t.solved_by.length) ?? theorems[0];
const routes = ["/", "/benchmark", "/theorems", `/theorem/${solved.id}`, "/retrieval", "/repair", "/errors", "/cost", "/methods", "/paper"];
const browser = await pw.chromium.launch();
const report = [];
try {
for (const [vw, vh, tag] of [[1280, 900, "desktop"], [390, 844, "phone"]]) {
  const page = await browser.newPage({ viewport: { width: vw, height: vh } });
  for (const route of routes) {
    const errors = [];
    page.removeAllListeners("console"); page.removeAllListeners("pageerror");
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 200)); });
    page.on("pageerror", (e) => errors.push("pageerror: " + String(e).slice(0, 200)));
    page.removeAllListeners("response"); page.removeAllListeners("requestfailed");
    page.on("response", (r) => { if (r.status() >= 400) errors.push(`HTTP ${r.status()} ${r.url().replace(base, "")}`); });
    page.on("requestfailed", (r) => errors.push(`request failed ${r.url().replace(base, "")}: ${r.failure()?.errorText}`));
    const resp = await page.goto(base + route, { waitUntil: "networkidle" });
    const info = await page.evaluate(() => ({
      title: document.title,
      h1: document.querySelector("h1")?.textContent?.trim().slice(0, 80) ?? null,
      overflowX: document.documentElement.scrollWidth - window.innerWidth,
      text: document.body.innerText.length,
    }));
    const shot = path.join(outDir, `${tag}${route === "/" ? "_root" : route.replace(/\//g, "_")}.png`);
    await page.screenshot({ path: shot, fullPage: false });
    report.push({ viewport: tag, route, status: resp?.status(), ...info, errors, screenshot: path.basename(shot) });
  }
  await page.close();
}
} catch (e) {
  console.error("smoke test crashed:", e?.stack ?? e);
  await browser.close().catch(() => {});
  server.kill();
  process.exit(3);
}
await browser.close();
server.kill();
fs.writeFileSync(path.join(outDir, "report.json"), JSON.stringify(report, null, 1));
const bad = report.filter((r) => r.status !== 200 || r.errors.length || !r.title.includes("LeanGraph") || r.overflowX > 1 || !r.h1);
for (const r of report) console.log(`${r.viewport.padEnd(7)} ${String(r.status).padEnd(4)} ${r.route.padEnd(28)} h1=${JSON.stringify(r.h1)} overflowX=${r.overflowX} errors=${r.errors.length}`);
console.log(bad.length ? `PROBLEMS on ${bad.length} page views` : "all page views OK");
process.exit(bad.length ? 1 : 0);
