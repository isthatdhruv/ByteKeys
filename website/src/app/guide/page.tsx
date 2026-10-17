import type { Metadata } from "next";
import Link from "next/link";
import CodeBlock from "@/components/CodeBlock";
import JsonLd from "@/components/JsonLd";
import { cliReference, modes, panelPages, readyRules, ruleActions, ruleTriggers, softwareEffects } from "@/lib/content";
import { breadcrumbLd, pageMetadata, webPageLd } from "@/lib/seo";
import { site } from "@/lib/site";

const title = "Guide: control your laptop keyboard lighting";
const description =
  "How to use ByteKeys on Linux: the service and portable mode, effects, rules, profiles, keyboard shortcuts, OpenRGB, every bytekeys command and troubleshooting.";

export const metadata: Metadata = pageMetadata({ title, description, path: "/guide" });

const toc = [
  ["start", "First start"],
  ["panel", "The control panel"],
  ["effects", "Modes and effects"],
  ["rules", "Rules"],
  ["profiles", "Profiles"],
  ["shortcuts", "Keyboard shortcuts"],
  ["cli", "Command line"],
  ["settings", "Settings"],
  ["openrgb", "OpenRGB"],
  ["troubleshooting", "Troubleshooting"],
  ["security", "Security and privacy"],
] as const;

// DEFAULT_SETTINGS in bytekeys/engine/state.py.
const settings = [
  ["restore_on_boot", "true", "Put your lighting back at boot."],
  ["save_to_firmware", "false", "Also save a settled look to keyboard memory, on keyboards that support it."],
  ["fps", "30", "Frame rate for software effects."],
  ["openrgb", "true", "Look for an OpenRGB SDK server."],
  ["openrgb_host", "127.0.0.1", "Where the OpenRGB SDK server runs."],
  ["openrgb_port", "6742", "Its port."],
  ["openrgb_all_devices", "false", "Use every OpenRGB device, not only keyboards."],
] as const;

export default function GuidePage() {
  const howTo = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: "Set up keyboard lighting control on a Linux laptop with ByteKeys",
    step: [
      { "@type": "HowToStep", name: "Install ByteKeys", text: "Install the .deb on Debian, Ubuntu, Linux Mint, Pop!_OS or Zorin, or run the AppImage on any distribution.", url: `${site.url}/download` },
      { "@type": "HowToStep", name: "Install the service", text: "The .deb starts the service itself. In the AppImage, click Install service to unlock color control and background rules.", url: `${site.url}/guide#start` },
      { "@type": "HowToStep", name: "Pick a look", text: "Set brightness, a mode and colors for the whole keyboard, a zone or single keys on the Lighting page.", url: `${site.url}/guide#panel` },
      { "@type": "HowToStep", name: "Automate it", text: "Turn on ready-made rules such as Dim on battery or Turn off when idle, or write your own.", url: `${site.url}/guide#rules` },
    ],
  };

  return (
    <>
      <JsonLd data={[webPageLd({ path: "/guide", name: `${title} · ByteKeys`, description }), breadcrumbLd([["Guide", "/guide"]]), howTo]} />
      <section className="container-x pt-14 sm:pt-20">
        <p className="eyebrow">Guide</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">Using ByteKeys</h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-dim">
          From the first start to rules, the command line and what to do when a keyboard isn&apos;t found.
        </p>
      </section>

      <div className="container-x mt-12 grid gap-12 lg:grid-cols-[13rem_1fr]">
        <nav aria-label="On this page" className="hidden lg:block">
          <ul className="sticky top-24 space-y-1.5 border-l border-line pl-4 text-sm">
            {toc.map(([id, label]) => (
              <li key={id}>
                <a href={`#${id}`} className="text-dim transition-colors hover:text-ink">
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <article className="prose-bk min-w-0 max-w-3xl [&>h2:first-child]:mt-0">
          <h2 id="start">First start</h2>
          <p>
            Open <strong>ByteKeys</strong> from your applications menu. It detects your laptop and its keyboard lighting, picks
            the right driver and creates profiles and rules to start from.
          </p>
          <p>
            Changing keyboard lighting needs root, so a small service, <code>bytekeysd</code>, does the hardware work while the
            control panel runs as you:
          </p>
          <ul>
            <li>
              <strong>.deb:</strong> the service comes with the package and starts on installation.
            </li>
            <li>
              <strong>AppImage:</strong> it starts in portable mode. Click <strong>Install service</strong> on the System page or
              the banner; it asks for your password once and installs the service to <code>/opt/bytekeys</code>.
            </li>
            <li>
              <strong>From source:</strong> <code>sudo make install</code> installs to <code>/usr/local</code> and starts the
              service.
            </li>
          </ul>
          <p>
            In portable mode, without the service, the control panel and the command line run the same engine themselves with
            whatever your user may access. Brightness still works for the active desktop user; colors, modes and background rules
            need the service. Check it with <code>bytekeys service status</code>.
          </p>

          <h2 id="panel">The control panel</h2>
          <p>Five pages, in a dark or light theme:</p>
          <ul>
            {panelPages.map((p) => (
              <li key={p.id}>
                <strong>{p.name}:</strong> {p.body}
              </li>
            ))}
          </ul>
          <p>A tray icon gives you quick changes without opening the window.</p>

          <h2 id="effects">Modes and effects</h2>
          <p>
            One-click modes on the Lighting page: {modes.join(", ")}. When your keyboard has its own hardware mode for one of
            them, ByteKeys uses it. Software effects work on every keyboard, even plain white ones: {softwareEffects.join(", ")}.
            The Effects page lists everything your keyboard supports, with speed, direction and colors.
          </p>

          <h2 id="rules">Rules</h2>
          <p>
            A rule is <em>when this happens, do that</em>. While its trigger holds, its action is layered on top of your own
            settings. Rules apply top to bottom, so later rules win. When you change a setting a rule is overriding, the rule
            steps aside until it stops applying. Thresholds have some slack, so a value hovering near a limit doesn&apos;t flicker.
          </p>
          <h3>Ready-made rules</h3>
          <p>They come with ByteKeys and stay off until you turn them on:</p>
          <ul>
            {readyRules.map((r) => (
              <li key={r.id}>
                <strong>{r.name}</strong>: {r.detail} (<code>{r.id}</code>)
              </li>
            ))}
          </ul>
          <h3>Triggers and actions</h3>
          <p>When: {ruleTriggers.join("; ")}.</p>
          <p>Do: {ruleActions.join("; ")}.</p>
          <p>
            Rules can be exported and imported from the command line: <code>bytekeys rules export</code> and{" "}
            <code>bytekeys rules import FILE</code>.
          </p>

          <h2 id="profiles">Profiles</h2>
          <p>
            A profile is a saved look for all your keyboards. Switch profiles from the control panel, the tray, the command line (
            <code>bytekeys profile apply Night</code>) or a rule, such as Night mode.
          </p>

          <h2 id="shortcuts">Keyboard shortcuts</h2>
          <p>
            ByteKeys follows the laptop&apos;s own Fn brightness keys. On laptops whose Fn keys don&apos;t reach the backlight, bind
            these commands to shortcuts in your desktop&apos;s keyboard settings:
          </p>
          <div className="not-prose mt-4">
            <CodeBlock id="guide-shortcuts" code={"bytekeys brightness up\nbytekeys brightness down\nbytekeys toggle"} />
          </div>

          <h2 id="cli">Command line</h2>
          <p>
            <code>bytekeys</code> talks to the service, or runs portable when there is none. Add <code>--json</code> for
            machine-readable output, <code>-d DEVICE</code> to target one keyboard, and <code>--local</code> to skip the service.
            From the AppImage, run <code>./ByteKeys-*.AppImage cli COMMAND</code>.
          </p>
          <div className="not-prose mt-5 overflow-x-auto rounded-2xl border border-line">
            <table className="w-full min-w-[34rem] text-left text-sm">
              <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Command</th>
                  <th scope="col" className="px-4 py-3 font-medium">What it does</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {cliReference.map((c) => (
                  <tr key={c.cmd} className="align-top">
                    <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[13px] text-ink">bytekeys {c.cmd}</td>
                    <td className="px-4 py-2.5 text-dim">{c.help}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="not-prose mt-5">
            <CodeBlock
              id="guide-cli"
              label="Examples"
              code={
                'bytekeys color "#ff8800"              # whole keyboard orange\nbytekeys color red green blue white   # one color per zone\nbytekeys mode cycle                   # cycle through all colors\nbytekeys flash --color red --count 3  # e.g. from a notification script'
              }
            />
          </div>

          <h2 id="settings">Settings</h2>
          <p>
            Show them with <code>bytekeys settings</code> and change one with <code>bytekeys settings key=value</code>:
          </p>
          <ul>
            {settings.map(([key, value, note]) => (
              <li key={key}>
                <code>{key}</code> (default <code>{value}</code>): {note}
              </li>
            ))}
          </ul>

          <h2 id="openrgb">OpenRGB</h2>
          <p>
            For keyboards ByteKeys has no driver for, such as Razer, Gigabyte and AORUS, MSI per-key or Legion per-key, run{" "}
            <a href="https://openrgb.org">OpenRGB</a> with its SDK server enabled. ByteKeys connects to it on{" "}
            <code>127.0.0.1:6742</code> and controls whatever OpenRGB supports.
          </p>
          <div className="not-prose mt-4">
            <CodeBlock id="guide-openrgb" code="openrgb --server" />
          </div>

          <h2 id="troubleshooting">Troubleshooting</h2>
          <h3>My keyboard isn&apos;t detected</h3>
          <p>
            The System page shows what ByteKeys found and hints, such as a kernel module to install. Copy the report there, or run{" "}
            <code>bytekeys report</code>, and open a <a href={site.deviceIssue}>Device support issue</a> with it. The{" "}
            <Link href="/hardware">hardware page</Link> lists what works today.
          </p>
          <h3>Colors and modes don&apos;t change</h3>
          <p>
            You are probably in portable mode. Install the service (see <a href="#start">First start</a>) and check it with{" "}
            <code>bytekeys service status</code>.
          </p>
          <h3>ASUS TUF lights stay dark or ignore colors</h3>
          <p>Kernels 6.1 to 6.4 and 6.10 had bugs in asus-wmi&apos;s keyboard lighting. Use kernel 6.5 or later, but not 6.10.0.</p>
          <h3>My keyboard is marked Experimental</h3>
          <p>
            Its driver follows a documented protocol but hasn&apos;t been confirmed on that hardware yet. If it works, or doesn&apos;t,
            a <a href={site.deviceIssue}>report</a> helps everyone with the same laptop.
          </p>

          <h2 id="security">Security and privacy</h2>
          <ul>
            <li>
              Anyone may read the service&apos;s state, but only root, members of the <code>bytekeys</code> group and the user at
              the active local session may change it. Every request is checked.
            </li>
            <li>Every value is validated, and device paths come only from the service&apos;s own discovery.</li>
            <li>
              Input devices are read only for activity timestamps, for idle rules and the Reactive effect. Key codes are never
              stored or logged.
            </li>
            <li>The systemd unit runs the service sandboxed.</li>
            <li>
              ByteKeys makes no network connections of its own; the only one is to an OpenRGB SDK server, on your own machine
              unless you point it elsewhere.
            </li>
          </ul>
          <p>
            Found a vulnerability? Report it privately, not in a public issue, as the{" "}
            <a href={site.docs.security}>security policy</a> explains.
          </p>
        </article>
      </div>
    </>
  );
}
