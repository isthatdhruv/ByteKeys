import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date(site.lastReviewed);
  return [
    { url: `${site.url}/`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${site.url}/download`, lastModified, changeFrequency: "weekly", priority: 0.9 },
    { url: `${site.url}/hardware`, lastModified, changeFrequency: "monthly", priority: 0.8 },
    { url: `${site.url}/guide`, lastModified, changeFrequency: "monthly", priority: 0.7 },
    { url: `${site.url}/privacy`, lastModified, changeFrequency: "yearly", priority: 0.2 },
  ];
}
