"use client";

import { Suspense, useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { capture, startAnalytics } from "@/lib/analytics";

const enabled = Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY);

function PageView() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!pathname) return;
    const query = searchParams.toString();
    capture("$pageview", { $current_url: window.location.origin + pathname + (query ? `?${query}` : "") });
  }, [pathname, searchParams]);

  return null;
}

/** Page views for PostHog. Renders nothing, and does nothing without NEXT_PUBLIC_POSTHOG_KEY. */
export default function Analytics() {
  useEffect(() => startAnalytics(), []);
  if (!enabled) return null;
  return (
    <Suspense fallback={null}>
      <PageView />
    </Suspense>
  );
}
