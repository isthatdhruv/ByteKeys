import sizes from "@/lib/screenshots.json";

type Shot = keyof typeof sizes extends `${infer N}-${"dark" | "light"}` ? N : never;

/**
 * A control center screenshot in the visitor's color scheme: the dark capture by default, the light one
 * when the system prefers light. Files and sizes come from docs/screenshots (npm run assets).
 */
export default function Screenshot({
  name,
  alt,
  priority = false,
  className = "",
}: {
  name: Shot;
  alt: string;
  priority?: boolean;
  className?: string;
}) {
  const { width, height } = sizes[`${name}-dark`];
  const set = (theme: string) => `/screenshots/${name}-${theme}-640.webp 640w, /screenshots/${name}-${theme}-full.webp ${width}w`;
  const media = `(min-width: ${width}px) ${width}px, 100vw`;
  return (
    <picture>
      <source media="(prefers-color-scheme: light)" srcSet={set("light")} sizes={media} />
      <img
        src={`/screenshots/${name}-dark-full.webp`}
        srcSet={set("dark")}
        sizes={media}
        alt={alt}
        width={width}
        height={height}
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : "auto"}
        decoding="async"
        className={`h-auto w-full ${className}`}
      />
    </picture>
  );
}
