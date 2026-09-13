// Render the site icon set from site/app/icon.svg (the single source).
// Writes site/app/apple-icon.png (180 px, full-bleed square: iOS applies its own rounding) and a 256 px PNG that
// scripts/make_favicon.py turns into site/app/favicon.ico. Optional: node scripts/make_icons.mjs --sheet <out.png> [extra.svg]
// Usage: PLAYWRIGHT_DIR=<node_modules containing playwright> node scripts/make_icons.mjs
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const pw = process.env.PLAYWRIGHT_DIR ? require(path.join(process.env.PLAYWRIGHT_DIR, "playwright")) : require("playwright");
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const app = path.join(root, "site", "app");
const svg = fs.readFileSync(path.join(app, "icon.svg"), "utf-8");
const fullBleed = svg.replace(/<rect ([^>]*?)rx="[^"]*"/, "<rect $1");
const sized = (s, n) => s.replace("<svg ", `<svg width="${n}" height="${n}" `);

const browser = await pw.chromium.launch();
async function render(source, size, out) {
  const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
  await page.setContent(`<html><body style="margin:0;background:transparent">${sized(source, size)}</body></html>`);
  await page.screenshot({ path: out, omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
  await page.close();
}
await render(fullBleed, 180, path.join(app, "apple-icon.png"));
const tmp = path.join(root, "site", ".icon-256.png");
await render(svg, 256, tmp);

const i = process.argv.indexOf("--sheet");
if (i > -1) {
  const out = process.argv[i + 1];
  const variants = [["A (site/app/icon.svg)", svg], ...process.argv.slice(i + 2).map((f) => [path.basename(f), fs.readFileSync(f, "utf-8")])];
  const cells = [];
  for (const [name, s] of variants) {
    const p16 = path.join(path.dirname(out), `${name.replace(/\W+/g, "_")}_16.png`);
    await render(s, 16, p16);
    const b64 = fs.readFileSync(p16).toString("base64");
    const uri = `data:image/svg+xml;base64,${Buffer.from(s).toString("base64")}`;
    for (const [bg, fg] of [["#f9f9f7", "#0b0b0b"], ["#0d0d0d", "#fff"]]) {
      cells.push(`<div style="background:${bg};color:${fg};padding:14px;display:flex;align-items:center;gap:18px;font:12px system-ui">
        <span style="width:150px">${name}</span>
        <img src="data:image/png;base64,${b64}" width="16" height="16">
        <img src="${uri}" width="32" height="32">
        <img src="data:image/png;base64,${b64}" width="64" height="64" style="image-rendering:pixelated" title="16px, enlarged">
        <img src="${uri}" width="96" height="96">
        <span style="opacity:.7">16px · 32px · 16px×4 · 96px</span></div>`);
    }
  }
  const page = await browser.newPage({ viewport: { width: 640, height: 140 * cells.length / 2 }, deviceScaleFactor: 2 });
  await page.setContent(`<html><body style="margin:0">${cells.join("")}</body></html>`);
  await page.screenshot({ path: out, fullPage: true });
  await page.close();
}
await browser.close();
console.log("rendered apple-icon.png (180) and .icon-256.png");
