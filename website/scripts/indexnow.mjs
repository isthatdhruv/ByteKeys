// Tells Bing and the other IndexNow search engines (Yandex, Seznam, Naver) which pages changed, so they
// recrawl them within hours. Bing's index also feeds ChatGPT search, Copilot and DuckDuckGo. Google
// doesn't use IndexNow; it reads the sitemap. Run after a deploy that changes content:
//   npm run indexnow                        every page in the live sitemap
//   npm run indexnow -- /download /hardware only these pages
// The key is public by design: search engines check it against public/<key>.txt on the site.
const KEY = "6dc12880d3431d1330ecdabaa378741d";
const site = (process.env.NEXT_PUBLIC_SITE_URL?.trim() || "https://bytekeys.byteknotlabs.com").replace(/\/$/, "");

const paths = process.argv.slice(2);
let urls;
if (paths.length) {
  urls = paths.map((p) => new URL(p, site).href);
} else {
  const res = await fetch(`${site}/sitemap.xml`);
  if (!res.ok) throw new Error(`Couldn't read ${site}/sitemap.xml: ${res.status}`);
  urls = [...(await res.text()).matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
}

const res = await fetch("https://api.indexnow.org/indexnow", {
  method: "POST",
  headers: { "content-type": "application/json; charset=utf-8" },
  body: JSON.stringify({ host: new URL(site).host, key: KEY, keyLocation: `${site}/${KEY}.txt`, urlList: urls }),
});
console.log(`IndexNow: ${res.status} ${res.statusText} for ${urls.length} URLs`);
if (res.status !== 200 && res.status !== 202) process.exit(1);
