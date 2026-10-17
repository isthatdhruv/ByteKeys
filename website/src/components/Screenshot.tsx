/**
 * A control panel screenshot in the visitor's color scheme: the dark capture by default, the light
 * one when the system prefers light. Files come from docs/screenshots (npm run assets).
 */
export default function Screenshot({
  name,
  alt,
  priority = false,
  className = "",
}: {
  name: string;
  alt: string;
  priority?: boolean;
  className?: string;
}) {
  const set = (theme: string) => `/screenshots/${name}-${theme}-640.webp 640w, /screenshots/${name}-${theme}-1180.webp 1180w`;
  const sizes = "(min-width: 1180px) 1180px, 100vw";
  return (
    <picture>
      <source media="(prefers-color-scheme: light)" srcSet={set("light")} sizes={sizes} />
      <img
        src={`/screenshots/${name}-dark-1180.webp`}
        srcSet={set("dark")}
        sizes={sizes}
        alt={alt}
        width={1180}
        height={820}
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : "auto"}
        decoding="async"
        className={`h-auto w-full ${className}`}
      />
    </picture>
  );
}
