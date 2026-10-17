import type { HardwareStatus } from "@/lib/content";

export default function StatusBadge({ status }: { status: HardwareStatus }) {
  const styles = {
    Tested: "border-good/40 bg-good/10 text-good",
    Supported: "border-line-hi bg-surface-2 text-ink",
    Experimental: "border-warn/40 bg-warn/10 text-warn",
  } as const;
  return <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}>{status}</span>;
}
