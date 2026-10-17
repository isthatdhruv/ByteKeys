import Link from "next/link";
import {
  ArrowRight,
  Bookmark,
  Download,
  Grid3x3,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Terminal,
  Workflow,
  Wrench,
} from "lucide-react";
import CodeBlock from "@/components/CodeBlock";
import Faq from "@/components/Faq";
import GithubMark from "@/components/GithubMark";
import JsonLd from "@/components/JsonLd";
import PanelTour from "@/components/PanelTour";
import Screenshot from "@/components/Screenshot";
import StatusBadge from "@/components/StatusBadge";
import {
  cliExamples,
  features,
  hardware,
  homeFaq,
  kernelBrands,
  readyRules,
  ruleActions,
  ruleTriggers,
  softwareEffects,
  usbControllers,
} from "@/lib/content";
import { formatDate, getLatestRelease } from "@/lib/release";
import { faqLd } from "@/lib/seo";
import { organizationId, site, softwareId } from "@/lib/site";

export const revalidate = 3600;

const icons = {
  detect: ScanSearch,
  setup: Wrench,
  effects: Sparkles,
  zones: Grid3x3,
  rules: Workflow,
  profiles: Bookmark,
  restore: RefreshCw,
  cli: Terminal,
  safe: ShieldCheck,
} as const;

export default async function HomePage() {
  const release = await getLatestRelease();
  const statusCounts = hardware.reduce<Record<string, number>>((acc, h) => ({ ...acc, [h.status]: (acc[h.status] ?? 0) + 1 }), {});

  const softwareLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": softwareId,
    name: site.name,
    description: site.description,
    url: site.url,
    applicationCategory: "UtilitiesApplication",
    applicationSubCategory: "Keyboard lighting control",
    operatingSystem: "Linux",
    isAccessibleForFree: true,
    license: "https://www.gnu.org/licenses/gpl-3.0.html",
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    screenshot: `${site.url}/screenshots/lighting-dark-1180.webp`,
    featureList: features.map((f) => f.title),
    sameAs: site.repo,
    publisher: { "@id": organizationId },
    ...(release && {
      softwareVersion: release.version,
      ...(release.date && { datePublished: release.date }),
      downloadUrl: `${site.url}/download`,
      releaseNotes: release.pageUrl,
    }),
  };
  const sourceLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareSourceCode",
    name: "ByteKeys source code",
    codeRepository: site.repo,
    programmingLanguage: "Python",
    license: "https://www.gnu.org/licenses/gpl-3.0.html",
    targetProduct: { "@id": softwareId },
  };

  return (
    <>
      <JsonLd data={[softwareLd, sourceLd, faqLd(homeFaq)]} />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="glow-pulse pointer-events-none absolute left-1/2 top-[-12rem] h-[34rem] w-[64rem] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]"
        />
        <div className="container-x relative pt-16 text-center sm:pt-24">
          <p className="eyebrow">Free and open source · Linux</p>
          <h1 className="mx-auto mt-5 max-w-4xl text-balance text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl">
            Keyboard backlight and <span className="text-gradient">RGB lighting</span> control for Linux laptops
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-dim">
            White backlights, single-zone, multi-zone and per-key RGB. Detected and configured automatically.
          </p>
          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <Link href="/download" className="btn btn-primary">
              <Download aria-hidden="true" className="h-4 w-4" /> Download for Linux
            </Link>
            <a href={site.repo} className="btn btn-ghost">
              <GithubMark className="h-4 w-4" /> Source on GitHub
            </a>
          </div>
          <p className="mt-5 text-sm text-faint">
            {release ? (
              <>
                Version {release.version}
                {release.date && <> · {formatDate(release.date)}</>} ·{" "}
              </>
            ) : null}
            .deb and AppImage · {site.license.id}
          </p>
        </div>
        <div className="container-x relative mt-14 sm:mt-16">
          <div className="mx-auto max-w-5xl overflow-hidden rounded-2xl border border-line shadow-[0_40px_120px_-40px_var(--glow)]">
            <Screenshot name="lighting" alt="The ByteKeys control panel: a per-key keyboard preview, brightness, modes and colors" priority />
          </div>
        </div>
      </section>

      {/* Works with */}
      <section aria-labelledby="works-heading" className="container-x mt-20">
        <h2 id="works-heading" className="text-center text-sm font-medium text-dim">
          Works with the kernel&apos;s keyboard lights, common USB controllers and OpenRGB
        </h2>
        <ul className="mx-auto mt-6 flex max-w-4xl flex-wrap justify-center gap-2">
          {[...kernelBrands, ...usbControllers, "OpenRGB"].map((name) => (
            <li key={name} className="rounded-full border border-line bg-surface px-3 py-1 text-[13px] text-dim">
              {name}
            </li>
          ))}
        </ul>
      </section>

      {/* Features */}
      <section id="features" aria-labelledby="features-heading" className="container-x mt-28 scroll-mt-24">
        <p className="eyebrow">What it does</p>
        <h2 id="features-heading" className="mt-3 max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
          Every kind of keyboard light, one control panel.
        </h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => {
            const Icon = icons[f.id];
            return (
              <div key={f.id} className="card p-6">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent/12 text-accent">
                  <Icon aria-hidden="true" className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-[17px] font-semibold text-ink">{f.title}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-dim">{f.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Control panel tour */}
      <section aria-labelledby="tour-heading" className="container-x mt-28">
        <p className="eyebrow">The control panel</p>
        <h2 id="tour-heading" className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
          Five pages. Dark and light themes.
        </h2>
        <div className="mt-8">
          <PanelTour />
        </div>
      </section>

      {/* Effects and rules */}
      <section aria-labelledby="rules-heading" className="container-x mt-28 grid gap-10 lg:grid-cols-2">
        <div>
          <p className="eyebrow">Effects</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight">Effects on every keyboard.</h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            Your keyboard&apos;s own hardware modes are used when it has them. These software effects work on every keyboard, even
            plain white ones:
          </p>
          <ul className="mt-5 flex flex-wrap gap-2">
            {softwareEffects.map((e) => (
              <li key={e} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-ink">
                {e}
              </li>
            ))}
          </ul>
          <p className="mt-6 text-[15px] leading-relaxed text-dim">
            One-click modes cover the everyday looks: Static, Breathing, Color cycle, Wave and Strobe. The Effects page has
            everything your keyboard supports, with speed, direction and colors.
          </p>
        </div>
        <div>
          <p className="eyebrow">Rules</p>
          <h2 id="rules-heading" className="mt-3 text-3xl font-bold tracking-tight">
            When this happens, do that.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            Rules apply top to bottom. A manual change wins until the rule stops applying. Ready-made rules come with ByteKeys,
            all off until you turn them on:
          </p>
          <ul className="mt-5 space-y-2">
            {readyRules.map((r) => (
              <li key={r.id} className="flex items-baseline justify-between gap-4 rounded-lg border border-line bg-surface px-4 py-2.5 text-sm">
                <span className="font-medium text-ink">{r.name}</span>
                <span className="text-right text-dim">{r.detail}</span>
              </li>
            ))}
          </ul>
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-ink">When</h3>
              <ul className="mt-2 space-y-1.5 text-sm text-dim">
                {ruleTriggers.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink">Do</h3>
              <ul className="mt-2 space-y-1.5 text-sm text-dim">
                {ruleActions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Command line */}
      <section aria-labelledby="cli-heading" className="container-x mt-28 grid items-start gap-10 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <p className="eyebrow">Command line</p>
          <h2 id="cli-heading" className="mt-3 text-3xl font-bold tracking-tight">
            Scripts and keyboard shortcuts.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            Everything the control panel does, the <code>bytekeys</code> command does too. Bind{" "}
            <code>bytekeys brightness up</code>, <code>bytekeys brightness down</code> or <code>bytekeys toggle</code> to
            shortcuts in your desktop settings for laptops whose Fn keys don&apos;t reach the backlight.
          </p>
          <Link href="/guide#cli" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
            Every command <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
        <CodeBlock id="home-cli" code={cliExamples.map((c) => (c.note ? `${c.cmd}  # ${c.note}` : c.cmd)).join("\n")} />
      </section>

      {/* How it works */}
      <section aria-labelledby="how-heading" className="container-x mt-28">
        <p className="eyebrow">How it works</p>
        <h2 id="how-heading" className="mt-3 max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl">
          A small root service owns the hardware. Everything else runs as you.
        </h2>
        <div className="mt-10 grid items-center gap-4 lg:grid-cols-[1fr_auto_1.1fr_auto_1.3fr]">
          <div className="card p-5">
            <h3 className="font-mono text-xs uppercase tracking-[0.14em] text-faint">Clients, as your user</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink">
              <li>Control panel (bytekeys-gui)</li>
              <li>Command line (bytekeys)</li>
              <li>Tray icon</li>
            </ul>
          </div>
          <Arrow label="JSON over /run/bytekeys" />
          <div className="rounded-2xl border border-accent/50 bg-accent/10 p-5">
            <h3 className="font-mono text-xs uppercase tracking-[0.14em] text-accent">bytekeysd, as root</h3>
            <p className="mt-3 text-sm leading-relaxed text-ink">
              Applies lighting, renders effects, evaluates rules, restores your look after boot and resume, and watches for
              keyboards being added.
            </p>
          </div>
          <Arrow label="drivers" />
          <div className="card p-5">
            <h3 className="font-mono text-xs uppercase tracking-[0.14em] text-faint">Hardware</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink">
              <li>Kernel LED drivers (/sys/class/leds, WMI zones)</li>
              <li>USB HID controllers (/dev/hidraw*)</li>
              <li>OpenRGB SDK server (TCP 6742)</li>
            </ul>
          </div>
        </div>
        <ul className="mt-8 grid gap-4 text-[15px] leading-relaxed text-dim sm:grid-cols-3">
          <li className="card p-5">
            <strong className="block text-ink">Who may change the lighting</strong>
            Anyone may read the service&apos;s state. Only root, the <code>bytekeys</code> group and the user at the active local
            session may change it.
          </li>
          <li className="card p-5">
            <strong className="block text-ink">No keylogging</strong>
            For idle detection and the Reactive effect it notes when an input event happened, never which key it was.
          </li>
          <li className="card p-5">
            <strong className="block text-ink">Portable mode</strong>
            Without the service, the control panel and the command line run the same engine themselves, with whatever your user
            may access.
          </li>
        </ul>
      </section>

      {/* Hardware */}
      <section aria-labelledby="hw-heading" className="container-x mt-28">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Supported hardware</p>
            <h2 id="hw-heading" className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              From plain white backlights to per-key RGB.
            </h2>
          </div>
          <Link href="/hardware" className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-accent hover:underline">
            Full hardware list <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
        <ul className="mt-8 space-y-3 md:hidden">
          {hardware.slice(0, 7).map((h) => (
            <li key={h.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <span className="font-medium text-ink">{h.name}</span>
                <StatusBadge status={h.status} />
              </div>
              <p className="mt-2 text-sm text-dim">{h.lighting}</p>
            </li>
          ))}
        </ul>
        <div className="mt-8 hidden overflow-hidden rounded-2xl border border-line md:block">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Hardware</th>
                <th scope="col" className="px-4 py-3 font-medium">Lighting</th>
                <th scope="col" className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {hardware.slice(0, 7).map((h) => (
                <tr key={h.id}>
                  <td className="px-4 py-3 font-medium text-ink">{h.name}</td>
                  <td className="px-4 py-3 text-dim">{h.lighting}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={h.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-dim">
          {hardware.length} hardware families: {statusCounts.Tested ?? 0} tested, {statusCounts.Supported ?? 0} supported and{" "}
          {statusCounts.Experimental ?? 0} experimental.{" "}
          <Link href="/hardware" className="text-accent hover:underline">
            See all of them
          </Link>
          .
        </p>
      </section>

      {/* Open source */}
      <section aria-labelledby="oss-heading" className="container-x mt-28">
        <div className="card relative overflow-hidden p-8 sm:p-12">
          <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]" />
          <p className="eyebrow">Open source</p>
          <h2 id="oss-heading" className="mt-3 max-w-2xl text-3xl font-bold tracking-tight">
            Free software. Help it reach your keyboard.
          </h2>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-dim">
            ByteKeys is released under the GPL-3.0-or-later and written in Python: the standard library only, plus Qt for the
            control panel. The most valuable help is a hardware report, especially for keyboards marked Experimental. Adding a
            keyboard is usually one small driver class.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <a href={site.deviceIssue} className="btn btn-primary">
              Report your keyboard
            </a>
            <a href={site.docs.addingDevices} className="btn btn-ghost">
              Add a driver
            </a>
            <a href={site.repo} className="btn btn-ghost">
              <GithubMark className="h-4 w-4" /> Star on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section aria-labelledby="faq-heading" className="container-x mt-28 max-w-3xl">
        <p className="eyebrow">Questions</p>
        <h2 id="faq-heading" className="mt-3 text-3xl font-bold tracking-tight">
          Frequently asked
        </h2>
        <div className="mt-8">
          <Faq items={homeFaq} />
        </div>
      </section>

      {/* Download */}
      <section aria-labelledby="cta-heading" className="container-x mt-28 text-center">
        <h2 id="cta-heading" className="text-3xl font-bold tracking-tight sm:text-4xl">
          Light up your keyboard.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-dim">A .deb for Debian and Ubuntu, an AppImage for every other distribution.</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/download" className="btn btn-primary">
            <Download aria-hidden="true" className="h-4 w-4" /> Download ByteKeys
          </Link>
          <Link href="/guide" className="btn btn-ghost">
            Read the guide
          </Link>
        </div>
      </section>
    </>
  );
}

function Arrow({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-1 text-center text-[11px] text-faint lg:px-1">
      <ArrowRight aria-hidden="true" className="h-5 w-5 rotate-90 text-accent lg:rotate-0" />
      <span className="max-w-[9rem] font-mono">{label}</span>
    </div>
  );
}
