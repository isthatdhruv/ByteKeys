import type { Metadata } from "next";
import { site, softwareId, websiteId } from "@/lib/site";

/** Per-page metadata. Next.js replaces openGraph and twitter wholesale, so each page restates them. */
export function pageMetadata({ title, description, path }: { title: string; description: string; path: string }): Metadata {
  const full = `${title} · ByteKeys`;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { type: "website", siteName: site.name, locale: "en_US", title: full, description, url: path },
    twitter: { card: "summary_large_image", title: full, description },
  };
}

export function breadcrumbLd(trail: readonly [name: string, path: string][]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "ByteKeys", item: site.url },
      ...trail.map(([name, path], i) => ({ "@type": "ListItem", position: i + 2, name, item: `${site.url}${path}` })),
    ],
  };
}

export function faqLd(items: readonly { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
  };
}

export function webPageLd({ path, name, description, type = "WebPage" }: { path: string; name: string; description: string; type?: string }) {
  return {
    "@context": "https://schema.org",
    "@type": type,
    "@id": `${site.url}${path}#webpage`,
    url: `${site.url}${path}`,
    name,
    description,
    isPartOf: { "@id": websiteId },
    about: { "@id": softwareId },
    dateModified: site.lastReviewed,
    inLanguage: "en",
  };
}
