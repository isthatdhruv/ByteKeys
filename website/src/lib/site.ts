const env = (value: string | undefined, fallback: string) => (value?.trim() ? value.trim() : fallback);

const repo = "https://github.com/isthatdhruv/ByteKeys";
const blob = `${repo}/blob/main`;

export const site = {
  name: "ByteKeys",
  url: env(process.env.NEXT_PUBLIC_SITE_URL, "https://bytekeys.byteknotlabs.com").replace(/\/+$/, ""),
  /** The README's one-line description. */
  tagline: "Keyboard backlight and RGB lighting control for Linux laptops",
  /** Under 160 characters, for meta descriptions. */
  description:
    "Free, open-source keyboard backlight and RGB control for Linux laptops: white, zone and per-key RGB keyboards, effects, rules and profiles. Detected automatically.",
  appId: "io.github.isthatdhruv.ByteKeys",
  repo,
  releases: `${repo}/releases`,
  latestRelease: `${repo}/releases/latest`,
  /** The latest release's checksum file. Its file names give the version and the download names. */
  checksums: `${repo}/releases/latest/download/SHA256SUMS`,
  changelog: `${blob}/CHANGELOG.md`,
  changelogRaw: "https://raw.githubusercontent.com/isthatdhruv/ByteKeys/main/CHANGELOG.md",
  issues: `${repo}/issues`,
  deviceIssue: `${repo}/issues/new?template=device_support.yml`,
  bugIssue: `${repo}/issues/new?template=bug_report.yml`,
  docs: {
    supportedHardware: `${blob}/docs/SUPPORTED_HARDWARE.md`,
    addingDevices: `${blob}/docs/ADDING_DEVICES.md`,
    architecture: `${blob}/docs/ARCHITECTURE.md`,
    contributing: `${blob}/CONTRIBUTING.md`,
    security: `${blob}/SECURITY.md`,
  },
  license: { id: "GPL-3.0-or-later", name: "GNU General Public License v3.0 or later", url: `${blob}/LICENSE` },
  company: { name: "ByteKnot Labs", url: env(process.env.NEXT_PUBLIC_COMPANY_URL, "https://byteknotlabs.com").replace(/\/+$/, "") },
  /** ISO date of the last content review, for the sitemap and dateModified. */
  lastReviewed: "2026-10-17",
} as const;

/** Same @id as the Organization on byteknotlabs.com, so search engines join the two. */
export const organizationId = `${site.company.url}/#organization`;
export const websiteId = `${site.url}/#website`;
export const softwareId = `${site.url}/#software`;

export const nav = [
  { href: "/#features", label: "Features" },
  { href: "/hardware", label: "Hardware" },
  { href: "/guide", label: "Guide" },
  { href: "/download", label: "Download" },
] as const;
