// PostHog, only when NEXT_PUBLIC_POSTHOG_KEY is set, loaded after the page when the browser is idle.
// posthog-js-lite keeps its id in memory, so there are no cookies and no local storage: a full page
// load starts a new anonymous visitor. Events captured before it loads wait in a queue.
import type { PostHog } from "posthog-js-lite";

type Queued = { event: string; props?: Record<string, string | number | boolean> };

const enabled = Boolean(process.env.NEXT_PUBLIC_POSTHOG_KEY);
const queue: Queued[] = [];
let client: PostHog | null = null;
let started = false;

async function load() {
  // Read the env var inline so the bundler drops the import when no key is set.
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return;
  try {
    const { PostHog } = await import("posthog-js-lite");
    client = new PostHog(key, {
      host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
      persistence: "memory",
      captureHistoryEvents: false,
    });
    for (const q of queue.splice(0)) client.capture(q.event, q.props);
  } catch {
    // Blocked or offline: no analytics for this visit.
  }
}

export function startAnalytics() {
  if (!enabled || started || typeof window === "undefined") return;
  started = true;
  const whenIdle = () => {
    if ("requestIdleCallback" in window) window.requestIdleCallback(() => void load(), { timeout: 4000 });
    else setTimeout(() => void load(), 2000);
  };
  if (document.readyState === "complete") whenIdle();
  else window.addEventListener("load", whenIdle, { once: true });
}

export function capture(event: string, props?: Record<string, string | number | boolean>) {
  if (!enabled) return;
  if (client) client.capture(event, props);
  else queue.push({ event, props });
}
