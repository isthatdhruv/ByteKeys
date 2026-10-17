import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

// Search engines and AI crawlers are welcome: being found and cited is how people discover the project.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: `${site.url}/sitemap.xml`,
  };
}
