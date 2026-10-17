import Link from "next/link";
import {
  ArrowRight,
  BatteryCharging,
  Download,
  Fan,
  Gauge,
  Grid3x3,
  Keyboard,
  Rocket,
  ShieldCheck,
  Sparkles,
  Workflow,
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
  launchKeys,
  performanceFeatures,
  readyRules,
  ruleActions,
  ruleTriggers,
  softwareEffects,
  usbControllers,
  vendorApps,
} from "@/lib/content";
import { formatDate, getLatestRelease } from "@/lib/release";
import { faqLd } from "@/lib/seo";
import { organizationId, site, softwareId } from "@/lib/site";

export const revalidate = 3600;

const icons = {
  center: Gauge,
  lighting: Keyboard,
  performance: Fan,
  battery: BatteryCharging,
  launch: Rocket,
  effects: Sparkles,
  zones: Grid3x3,
  automations: Workflow,
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
    applicationSubCategory: "Laptop control center",
    operatingSystem: "Linux",
    isAccessibleForFree: true,
    license: "https://www.gnu.org/licenses/gpl-3.0.html",
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
    screenshot: `${site.url}/screenshots/home-dark-full.webp`,
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
          className="glow-pulse pointer-events-none absolute left-1/2 top-[-14rem] h-[36rem] w-[68rem] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,var(--glow),transparent)]"
        />
        <div className="container-x relative pt-16 text-center sm:pt-24">
          <p className="eyebrow">Free and open source · Linux</p>
          <h1 className="mx-auto mt-5 max-w-4xl text-balance text-4xl font-bold leading-[1.08] tracking-tight sm:text-6xl">
            Keyboard lighting, fans and <span className="text-gradient">performance modes</span> for Linux laptops
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-dim">
            The control center your laptop&apos;s vendor app never shipped for Linux. Detected and configured automatically.
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
            <Screenshot
              name="home"
              alt="The ByteKeys control center: CPU and GPU temperatures, fan speeds, performance modes, keyboard controls and the battery charge limit"
              priority
            />
          </div>
        </div>
      </section>

      {/* Vendor apps */}
      <section aria-labelledby="vendor-heading" className="container-x mt-20 text-center">
        <h2 id="vendor-heading" className="text-sm font-medium text-dim">
          For laptops whose lighting, fans and performance modes live in a Windows-only app
        </h2>
        <ul className="mx-auto mt-5 flex max-w-3xl flex-wrap justify-center gap-x-6 gap-y-2 text-[15px] font-medium text-ink/80">
          {vendorApps.map((app) => (
            <li key={app}>{app}</li>
          ))}
        </ul>
      </section>

      {/* Features */}
      <section id="features" aria-labelledby="features-heading" className="container-x mt-24 scroll-mt-24">
        <p className="eyebrow">What it does</p>
        <h2 id="features-heading" className="mt-3 max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
          The whole laptop, one control center.
        </h2>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => {
            const Icon = icons[f.id];
            return (
              <div key={f.id} className="card p-6">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface-2 text-accent-ink">
                  <Icon aria-hidden="true" className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-[17px] font-semibold text-ink">{f.title}</h3>
                <p className="mt-2 text-[15px] leading-relaxed text-dim">{f.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Control center tour */}
      <section aria-labelledby="tour-heading" className="container-x mt-28">
        <p className="eyebrow">The control center</p>
        <h2 id="tour-heading" className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
          Six pages. Dark and light.
        </h2>
        <div className="mt-8">
          <PanelTour />
        </div>
      </section>

      {/* Performance and fans */}
      <section id="performance" aria-labelledby="perf-heading" className="container-x mt-28 scroll-mt-24">
        <div className="grid items-start gap-10 lg:grid-cols-[1fr_1.15fr]">
          <div className="min-w-0">
            <p className="eyebrow">Performance and fans</p>
            <h2 id="perf-heading" className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              Quiet when you work. Full power when you play.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-dim">
              Switch Silent, Balanced and Performance in sync with your desktop&apos;s power settings. On ASUS laptops, draw a
              fan curve for each fan and each mode, or run the fans at full speed. Set a battery charge limit so a laptop that
              lives on its charger lasts longer.
            </p>
            <div className="mt-6 rounded-2xl border border-line bg-surface-2 p-5 text-[15px] leading-relaxed text-dim">
              <strong className="block text-ink">The firmware runs the fans, never ByteKeys</strong>
              ByteKeys only uses controls the laptop&apos;s firmware runs itself and never drives fan speeds directly, so a crash or
              a stopped service can&apos;t leave a fan off. Curves must keep the fans at 50% or more from 80 °C and end at 70% or
              more. The kernel forgets custom curves on mode changes, at boot and after sleep; the service keeps them active.
            </div>
          </div>
          <div className="min-w-0 overflow-hidden rounded-2xl border border-line">
            <Screenshot name="performance" alt="The ByteKeys Performance page: performance modes, a fan curve editor, fan speeds and battery care" />
          </div>
        </div>
        <div className="mt-8 overflow-x-auto rounded-2xl border border-line">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Feature</th>
                <th scope="col" className="px-4 py-3 font-medium">Works on</th>
                <th scope="col" className="px-4 py-3 font-medium">Through</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {performanceFeatures.map((f) => (
                <tr key={f.feature} className="align-top">
                  <td className="px-4 py-3 font-medium text-ink">{f.feature}</td>
                  <td className="px-4 py-3 text-dim">{f.worksOn}</td>
                  <td className="px-4 py-3 font-mono text-xs text-dim">{f.through}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Launch key */}
      <section aria-labelledby="launch-heading" className="container-x mt-28 grid gap-10 lg:grid-cols-[1fr_1.2fr]">
        <div className="min-w-0">
          <p className="eyebrow">Launch key</p>
          <h2 id="launch-heading" className="mt-3 text-3xl font-bold tracking-tight">
            The Armoury Crate key opens ByteKeys.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            ByteKeys knows the key of your laptop and can learn any other special key in Settings. With the service running, the
            key brings ByteKeys to the front from anywhere. On GNOME and KDE Plasma it also adds a desktop shortcut, so the key
            starts ByteKeys when it is closed. The service watches only that one key.
          </p>
        </div>
        <div className="min-w-0 overflow-x-auto rounded-2xl border border-line">
          <table className="w-full min-w-[30rem] text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Laptop</th>
                <th scope="col" className="px-4 py-3 font-medium">Key</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {launchKeys.map((k) => (
                <tr key={k.laptop}>
                  <td className="px-4 py-2.5 text-ink">{k.laptop}</td>
                  <td className="px-4 py-2.5 text-dim">{k.key}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Lighting and automations */}
      <section aria-labelledby="rules-heading" className="container-x mt-28 grid gap-10 lg:grid-cols-2">
        <div className="min-w-0">
          <p className="eyebrow">Keyboard lighting</p>
          <h2 className="mt-3 text-3xl font-bold tracking-tight">Effects on every keyboard.</h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            One-click modes for the everyday looks: Static, Breathing, Color cycle, Wave and Strobe, with animated previews. Your
            keyboard&apos;s own hardware modes are used when it has them, and these software effects work on every keyboard, even
            plain white ones:
          </p>
          <ul className="mt-5 flex flex-wrap gap-2">
            {softwareEffects.map((e) => (
              <li key={e} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm text-ink">
                {e}
              </li>
            ))}
          </ul>
          <div className="mt-8 overflow-hidden rounded-2xl border border-line">
            <Screenshot name="lighting-zones" alt="ByteKeys Lighting page with a 4-zone keyboard" />
          </div>
        </div>
        <div className="min-w-0">
          <p className="eyebrow">Automation</p>
          <h2 id="rules-heading" className="mt-3 text-3xl font-bold tracking-tight">
            When this happens, do that.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            Automations apply top to bottom, and a manual change wins until the automation stops applying. Ready-made ones come
            with ByteKeys, all off until you turn them on:
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
        <div className="min-w-0">
          <p className="eyebrow">Command line</p>
          <h2 id="cli-heading" className="mt-3 text-3xl font-bold tracking-tight">
            Scripts and keyboard shortcuts.
          </h2>
          <p className="mt-4 text-[15px] leading-relaxed text-dim">
            Lighting, performance modes, fans and the charge limit are all one <code>bytekeys</code> command away. Bind{" "}
            <code>bytekeys brightness up</code>, <code>bytekeys brightness down</code> or <code>bytekeys toggle</code> to shortcuts
            for laptops whose Fn keys don&apos;t reach the backlight.
          </p>
          <Link href="/guide#cli" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-accent-ink hover:underline">
            Every command <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
        <div className="min-w-0">
          <CodeBlock id="home-cli" code={cliExamples.map((c) => (c.note ? `${c.cmd}  # ${c.note}` : c.cmd)).join("\n")} />
        </div>
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
              <li>Control center (bytekeys-gui)</li>
              <li>Command line (bytekeys)</li>
              <li>Tray icon</li>
            </ul>
          </div>
          <Arrow label="JSON over /run/bytekeys" />
          <div className="rounded-2xl border border-line-hi bg-surface-2 p-5">
            <h3 className="font-mono text-xs uppercase tracking-[0.14em] text-accent-ink">bytekeysd, as root</h3>
            <p className="mt-3 text-sm leading-relaxed text-ink">
              Applies lighting, renders effects, runs automations, switches performance modes, keeps fan curves and the charge
              limit active, and restores everything after boot and resume.
            </p>
          </div>
          <Arrow label="firmware and drivers" />
          <div className="card p-5">
            <h3 className="font-mono text-xs uppercase tracking-[0.14em] text-faint">Hardware</h3>
            <ul className="mt-3 space-y-2 text-sm text-ink">
              <li>Kernel LED drivers (/sys/class/leds, WMI zones)</li>
              <li>USB HID controllers (/dev/hidraw*)</li>
              <li>Platform profile, hwmon fan curves, battery</li>
              <li>OpenRGB SDK server (TCP 6742)</li>
            </ul>
          </div>
        </div>
        <ul className="mt-8 grid gap-4 text-[15px] leading-relaxed text-dim sm:grid-cols-3">
          <li className="card p-5">
            <strong className="block text-ink">Who may change things</strong>
            Anyone may read the service&apos;s state. Only root, the <code>bytekeys</code> group and the user at the active local
            session may change it.
          </li>
          <li className="card p-5">
            <strong className="block text-ink">No keylogging</strong>
            It notes when an input event happened, for idle automations and the Reactive effect. The only key it ever looks at is
            your launch key.
          </li>
          <li className="card p-5">
            <strong className="block text-ink">Portable mode</strong>
            Without the service, the control center and the command line run the same engine themselves, with whatever your user
            may access.
          </li>
        </ul>
      </section>

      {/* Keyboard lighting hardware */}
      <section aria-labelledby="hw-heading" className="container-x mt-28">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Supported keyboards</p>
            <h2 id="hw-heading" className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              From plain white backlights to per-key RGB.
            </h2>
          </div>
          <Link href="/hardware" className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-accent-ink hover:underline">
            Full hardware list <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </div>
        <p className="mt-4 max-w-3xl text-[15px] leading-relaxed text-dim">
          Keyboard lights the kernel exposes ({kernelBrands.join(", ")}), common USB controllers ({usbControllers.join(", ")}) and
          everything OpenRGB supports.
        </p>
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
          {hardware.length} keyboard families: {statusCounts.Tested ?? 0} tested, {statusCounts.Supported ?? 0} supported and{" "}
          {statusCounts.Experimental ?? 0} experimental.{" "}
          <Link href="/hardware" className="text-accent-ink underline decoration-accent/40 underline-offset-2 hover:decoration-accent">
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
            Free software. Help it reach your laptop.
          </h2>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-dim">
            ByteKeys is released under the GPL-3.0-or-later and written in Python: the standard library only, plus Qt for the
            control center. The most valuable help is a hardware report, especially for keyboards marked Experimental. Adding a
            keyboard is usually one small driver class.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <a href={site.deviceIssue} className="btn btn-primary">
              Report your laptop
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
          Take control of your laptop.
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
