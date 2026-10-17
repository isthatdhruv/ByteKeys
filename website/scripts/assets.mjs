// Copies the app's screenshots and branding from the repository into the site.
//
//   npm run assets
//
// Run it after the screenshots in docs/screenshots or the files in data/branding change, and commit
// the output. The site never reads outside website/ at build time, so Vercel only needs this folder.
import { copyFile, mkdir, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(site, "..");
const shots = path.join(repo, "docs/screenshots");
const branding = path.join(repo, "data/branding");

// Screenshots: WebP at the native width and at 640 px for phones. Old files are removed first, so a
// screenshot deleted from the repository disappears from the site too.
const out = path.join(site, "public/screenshots");
await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });
const sizes = {};
for (const file of (await readdir(shots)).filter((f) => f.endsWith(".png")).sort()) {
  const name = file.replace(/\.png$/, "");
  const { width, height } = await sharp(path.join(shots, file)).metadata();
  sizes[name] = { width, height };
  for (const w of [width, 640]) {
    await sharp(path.join(shots, file))
      .resize({ width: w, withoutEnlargement: true })
      .webp({ quality: 86, effort: 6 })
      .toFile(path.join(out, `${name}-${w === width ? "full" : "640"}.webp`));
  }
  console.log("screenshot", name, `${width}x${height}`);
}
await writeFile(path.join(site, "src/lib/screenshots.json"), JSON.stringify(sizes, null, 2) + "\n");

// Favicons and touch icons, using Next.js file conventions where there is one.
const copies = [
  ["web/favicon.ico", "src/app/favicon.ico"],
  ["web/favicon.svg", "src/app/icon.svg"],
  ["web/apple-touch-icon.png", "src/app/apple-icon.png"],
  ["web/icon-192.png", "public/brand/icon-192.png"],
  ["web/icon-512.png", "public/brand/icon-512.png"],
  ["web/favicon.svg", "public/brand/bytekeys-icon.svg"],
  ["social-preview.png", "src/app/opengraph-image.png"],
  ["social-preview.png", "src/app/twitter-image.png"],
];
await mkdir(path.join(site, "public/brand"), { recursive: true });
for (const [from, to] of copies) {
  await copyFile(path.join(branding, from), path.join(site, to));
  console.log("brand", to);
}
