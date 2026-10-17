"use client";

import { useState } from "react";
import Screenshot from "@/components/Screenshot";
import { panelPages } from "@/lib/content";

/** The control panel's pages as tabs, each with its screenshot and what it does. */
export default function PanelTour() {
  const [active, setActive] = useState(0);
  const page = panelPages[active];

  return (
    <div>
      <div role="tablist" aria-label="Control panel pages" className="flex flex-wrap gap-2">
        {panelPages.map((p, i) => (
          <button
            key={p.id}
            id={`tab-${p.id}`}
            role="tab"
            type="button"
            aria-selected={i === active}
            aria-controls={`panel-${p.id}`}
            tabIndex={i === active ? 0 : -1}
            onClick={() => setActive(i)}
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              const next = (active + (e.key === "ArrowRight" ? 1 : panelPages.length - 1)) % panelPages.length;
              setActive(next);
              document.getElementById(`tab-${panelPages[next].id}`)?.focus();
            }}
            className={`rounded-full border px-4 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
              i === active ? "border-accent/70 bg-accent/15 text-ink" : "border-line text-dim hover:text-ink"
            }`}
          >
            {p.name}
          </button>
        ))}
      </div>
      <div id={`panel-${page.id}`} role="tabpanel" aria-labelledby={`tab-${page.id}`} className="mt-6">
        <p className="max-w-2xl text-[15px] leading-relaxed text-dim">{page.body}</p>
        <div className="mt-6 overflow-hidden rounded-2xl border border-line shadow-[0_30px_80px_-40px_var(--glow)]">
          <Screenshot name={page.shot} alt={`ByteKeys ${page.name} page`} />
        </div>
      </div>
    </div>
  );
}
