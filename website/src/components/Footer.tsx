import Link from "next/link";
import Logo from "@/components/Logo";
import { site } from "@/lib/site";

const columns = [
  {
    title: "ByteKeys",
    links: [
      { href: "/download", label: "Download" },
      { href: "/hardware", label: "Supported hardware" },
      { href: "/guide", label: "Guide" },
      { href: "/guide#cli", label: "Command line" },
    ],
  },
  {
    title: "Project",
    links: [
      { href: site.repo, label: "Source on GitHub" },
      { href: site.releases, label: "Releases" },
      { href: site.changelog, label: "Changelog" },
      { href: site.issues, label: "Issues" },
    ],
  },
  {
    title: "Contribute",
    links: [
      { href: site.deviceIssue, label: "Report a keyboard" },
      { href: site.docs.addingDevices, label: "Add a driver" },
      { href: site.docs.contributing, label: "Contributing guide" },
      { href: site.docs.security, label: "Security policy" },
    ],
  },
] as const;

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="container-x grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <Logo />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-dim">{site.tagline}.</p>
          <p className="mt-4 text-sm text-dim">
            Free software under the{" "}
            <a href={site.license.url} className="text-ink underline decoration-line underline-offset-4 hover:decoration-accent">
              GPL-3.0-or-later
            </a>
            .
          </p>
        </div>
        {columns.map((col) => (
          <div key={col.title}>
            <h2 className="text-sm font-semibold text-ink">{col.title}</h2>
            <ul className="mt-4 space-y-2.5">
              {col.links.map((l) => (
                <li key={l.href}>
                  {l.href.startsWith("/") ? (
                    <Link href={l.href} className="text-sm text-dim transition-colors hover:text-ink">
                      {l.label}
                    </Link>
                  ) : (
                    <a href={l.href} className="text-sm text-dim transition-colors hover:text-ink">
                      {l.label}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-line">
        <div className="container-x flex flex-col gap-2 py-6 text-xs text-faint sm:flex-row sm:items-center sm:justify-between">
          <p>
            An open-source project by{" "}
            <a href={site.company.url} className="text-dim underline decoration-line-hi underline-offset-2 hover:text-ink">
              {site.company.name}
            </a>{" "}
            and the ByteKeys contributors.
          </p>
          <p className="flex gap-4">
            <Link href="/privacy" className="hover:text-ink">
              Privacy
            </Link>
            <a href={site.license.url} className="hover:text-ink">
              License
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
