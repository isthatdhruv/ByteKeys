# ByteKeys website

The project site at [bytekeys.byteknotlabs.com](https://bytekeys.byteknotlabs.com): Next.js (App Router), TypeScript and
Tailwind CSS 4, deployed on Vercel from this folder.

## Run

```bash
cd website
npm install
npm run dev        # http://localhost:3000
npm run check      # typecheck, lint and production build
```

## Where things come from

| What | Source |
| --- | --- |
| Version, download links, sizes, SHA-256 | The latest GitHub release's `SHA256SUMS`, read at request time and cached for an hour (`src/lib/release.ts`). A new release appears without a deploy. |
| Release date and "What's in" notes | `CHANGELOG.md` on `main`, the section for the released version. |
| Features, pages, hardware, fans, launch keys, automations, commands, FAQ | `src/lib/content.ts`, written from `README.md`, `docs/` and the code. Update it when those change. |
| Screenshots, icons, social image | `docs/screenshots/` and `data/branding/`, copied and converted by `npm run assets`. Run it after they change and commit the result. |

The site never reads files outside `website/` while building, so Vercel only needs this folder. Fonts (Inter and JetBrains Mono) come
through `next/font`, which downloads them once at build time and serves them from the site.

## Deploy on Vercel

1. Vercel → Add New → Project → import `isthatdhruv/ByteKeys`.
2. Root Directory: `website`. Framework: Next.js (detected). Leave the build settings as they are.
3. Environment variables (all optional):

   | Variable | Purpose |
   | --- | --- |
   | `NEXT_PUBLIC_SITE_URL` | Defaults to `https://bytekeys.byteknotlabs.com`. Drives canonical URLs, the sitemap and Open Graph. |
   | `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST` | Cookieless page-view and download counts. Off when the key is empty. |
   | `GOOGLE_SITE_VERIFICATION`, `BING_SITE_VERIFICATION` | Search Console and Bing Webmaster meta tags. |

4. Settings → Domains → add `bytekeys.byteknotlabs.com`, then add the DNS record Vercel shows (a `CNAME` for `bytekeys`) at
   the DNS provider.

Every push to `main` redeploys the site; release data refreshes on its own every hour.
