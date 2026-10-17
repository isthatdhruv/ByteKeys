"use client";

import type { AnchorHTMLAttributes } from "react";
import { capture } from "@/lib/analytics";

/** An external link that records a click event, e.g. a download. */
export default function TrackedLink({
  event,
  props,
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement> & { event: string; props?: Record<string, string> }) {
  return <a {...rest} onClick={() => capture(event, props)} />;
}
