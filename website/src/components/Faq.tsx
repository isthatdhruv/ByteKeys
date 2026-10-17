import { ChevronDown } from "lucide-react";

export default function Faq({ items }: { items: readonly { q: string; a: string }[] }) {
  return (
    <div className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
      {items.map((item) => (
        <details key={item.q} className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-left font-medium text-ink [&::-webkit-details-marker]:hidden">
            <h3 className="text-[15px]">{item.q}</h3>
            <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-dim transition-transform group-open:rotate-180" />
          </summary>
          <p className="px-5 pb-5 text-[15px] leading-relaxed text-dim">{item.a}</p>
        </details>
      ))}
    </div>
  );
}
