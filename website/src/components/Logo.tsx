/** The ByteKeys icon and wordmark. The icon comes from data/branding (npm run assets). */
export default function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element -- small SVG, no optimisation needed */}
      <img src="/brand/bytekeys-icon.svg" alt="" width={32} height={32} className="h-8 w-8" />
      <span className="text-[17px] font-bold tracking-tight">
        Byte<span className="text-silver">Keys</span>
      </span>
    </span>
  );
}
