import Link from "next/link";
import { Menu } from "lucide-react";
import GithubMark from "@/components/GithubMark";
import Logo from "@/components/Logo";
import { nav, site } from "@/lib/site";

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-bg/80 backdrop-blur-md">
      <div className="container-x flex h-16 items-center justify-between gap-4">
        <Link href="/" aria-label="ByteKeys home" className="rounded-lg focus-visible:outline-2 focus-visible:outline-accent">
          <Logo />
        </Link>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {nav.map((item) => (
            <Link key={item.href} href={item.href} className="rounded-lg px-3 py-2 text-sm text-dim transition-colors hover:text-ink">
              {item.label}
            </Link>
          ))}
          <a
            href={site.repo}
            className="ml-2 inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-ink transition-colors hover:border-accent/60"
          >
            <GithubMark className="h-4 w-4" /> GitHub
          </a>
        </nav>
        <details className="group relative md:hidden">
          <summary className="flex cursor-pointer list-none items-center rounded-lg border border-line p-2 text-ink [&::-webkit-details-marker]:hidden">
            <Menu aria-hidden="true" className="h-5 w-5" />
            <span className="sr-only">Menu</span>
          </summary>
          <nav aria-label="Main" className="card absolute right-0 mt-2 flex w-56 flex-col p-2 shadow-2xl">
            {nav.map((item) => (
              <Link key={item.href} href={item.href} className="rounded-lg px-3 py-2.5 text-sm text-ink hover:bg-surface-2">
                {item.label}
              </Link>
            ))}
            <a href={site.repo} className="rounded-lg px-3 py-2.5 text-sm text-ink hover:bg-surface-2">
              GitHub
            </a>
          </nav>
        </details>
      </div>
    </header>
  );
}
