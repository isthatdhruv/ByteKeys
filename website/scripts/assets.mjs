// Copies the app's screenshots and branding from the repository into the site.
//
//   npm run assets
//
// Run it after the screenshots in docs/screenshots or the files in data/branding change, and commit
// the output. The site never reads outside website/ at build time, so Vercel only needs this folder.
import { copyFile, mkdir, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(site, "..");
const shots = path.join(repo, "docs/screenshots");
const branding = path.join(repo, "data/branding");

// Screenshots: WebP at the native width (1180 px) and a smaller one for phones.
const widths = [1180, 640];
await mkdir(path.join(site, "public/screenshots"), { recursive: true });
for (const file of (await readdir(shots)).filter((f) => f.endsWith(".png")).sort()) {
  const name = file.replace(/\.png$/, "");
  for (const width of widths) {
    const out = path.join(site, "public/screenshots", `${name}-${width}.webp`);
    await sharp(path.join(shots, file)).resize({ width, withoutEnlargement: true }).webp({ quality: 86, effort: 6 }).toFile(out);
  }
  console.log("screenshot", name);
}

// Favicons and touch icons, using Next.js file conventions where there is one.
const copies = [
  ["web/favicon.ico", "src/app/favicon.ico"],
  ["web/favicon.svg", "src/app/icon.svg"],
  ["web/apple-touch-icon.png", "src/app/apple-icon.png"],
  ["web/icon-192.png", "public/brand/icon-192.png"],
  ["web/icon-512.png", "public/brand/icon-512.png"],
  ["web/favicon.svg", "public/brand/bytekeys-icon.svg"],
  ["bytekeys-logo.svg", "public/brand/bytekeys-logo.svg"],
  ["bytekeys-banner.svg", "public/brand/bytekeys-banner.svg"],
  ["bytekeys-banner-light.svg", "public/brand/bytekeys-banner-light.svg"],
  ["social-preview.png", "src/app/opengraph-image.png"],
  ["social-preview.png", "src/app/twitter-image.png"],
];
await mkdir(path.join(site, "public/brand"), { recursive: true });
for (const [from, to] of copies) {
  await copyFile(path.join(branding, from), path.join(site, to));
  console.log("brand", to);
}
