"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { capture } from "@/lib/analytics";

/** Shell commands with a copy button. Lines starting with "#" are shown as comments. */
export default function CodeBlock({ code, id, label }: { code: string; id: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const commands = code
    .split("\n")
    .filter((l) => l.trim() && !l.trim().startsWith("#"))
    .map((l) => l.replace(/\s+#.*$/, ""))
    .join("\n");

  async function copy() {
    try {
      await navigator.clipboard.writeText(commands);
      setCopied(true);
      capture("command_copied", { id });
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard blocked: the text is still selectable.
    }
  }

  return (
    <div className="group relative overflow-hidden rounded-xl border border-line bg-code text-[13px] leading-6 text-[#ececf0]">
      {label && <div className="border-b border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-[#9d9da7]">{label}</div>}
      <pre className="overflow-x-auto px-4 py-3.5 pr-14 font-mono">
        <code>
          {code.split("\n").map((line, i) => {
            const comment = line.match(/^(.*?)(\s+#.*)$/);
            if (line.trim().startsWith("#")) return <span key={i} className="block text-[#8a8a94]">{line}</span>;
            return (
              <span key={i} className="block">
                <span aria-hidden="true" className="select-none text-[#ffd49a]">$ </span>
                {comment ? comment[1] : line}
                {comment && <span className="text-[#8a8a94]">{comment[2]}</span>}
              </span>
            );
          })}
        </code>
      </pre>
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Copied" : "Copy commands"}
        className="absolute right-2.5 top-2.5 rounded-lg border border-white/10 bg-code p-1.5 text-[#d6d6dc] shadow-[0_0_0_6px_var(--code-bg)] transition-colors hover:border-white/25 focus-visible:outline-2 focus-visible:outline-accent"
        style={label ? { top: "2.6rem" } : undefined}
      >
        {copied ? <Check aria-hidden="true" className="h-4 w-4" /> : <Copy aria-hidden="true" className="h-4 w-4" />}
      </button>
    </div>
  );
}
