import type { Metadata } from "next";
import JsonLd from "@/components/JsonLd";
import { breadcrumbLd, pageMetadata, webPageLd } from "@/lib/seo";
import { site } from "@/lib/site";

const title = "Privacy";
const description = "What the ByteKeys website and the ByteKeys app collect: the app sends nothing, and the website counts visits without cookies.";

export const metadata: Metadata = pageMetadata({ title, description, path: "/privacy" });

const analytics = Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY);

export default function PrivacyPage() {
  return (
    <>
      <JsonLd data={[webPageLd({ path: "/privacy", name: `${title} · ByteKeys`, description }), breadcrumbLd([["Privacy", "/privacy"]])]} />
      <section className="container-x pt-14 sm:pt-20">
        <p className="eyebrow">Privacy</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">Privacy</h1>
        <article className="prose-bk mt-8 max-w-3xl">
          <h2 className="!mt-0">The ByteKeys app</h2>
          <p>
            ByteKeys has no accounts, no telemetry and no update checks. It makes no network connections of its own; the only one
            is to an OpenRGB SDK server, which runs on your own computer unless you configure another address.
          </p>
          <p>
            To detect idle time and run the Reactive effect, the service notes when an input event happened, never which key it
            was. Key codes are never stored or logged. Your lighting, profiles and rules are saved on your computer in{" "}
            <code>/var/lib/bytekeys</code>, or <code>~/.local/state/bytekeys</code> in portable mode.
          </p>
          <p>
            The diagnostic report (<code>bytekeys report</code>) lists your hardware and kernel modules. It stays on your computer
            unless you choose to paste it into an issue.
          </p>

          <h2>This website</h2>
          <p>The site is hosted on Vercel, which keeps standard server logs, such as IP addresses, to run and protect the service.</p>
          {analytics ? (
            <p>
              We count page views and downloads with PostHog, without cookies or local storage: the anonymous visitor id lives in
              memory and is gone when you close or reload the page. We use the numbers to see which pages and packages people
              use.
            </p>
          ) : (
            <p>The site sets no cookies and runs no analytics.</p>
          )}
          <p>
            Downloads come from GitHub Releases, so GitHub&apos;s privacy statement applies to the files themselves.
          </p>

          <h2>Contact</h2>
          <p>
            ByteKeys is an open-source project by <a href={site.company.url}>{site.company.name}</a> and its contributors. For
            privacy questions, open an issue on <a href={site.issues}>GitHub</a>.
          </p>
          <p className="text-sm text-faint">Last updated {site.lastReviewed}.</p>
        </article>
      </section>
    </>
  );
}
