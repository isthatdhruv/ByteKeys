import type { Metadata } from "next";
import Link from "next/link";
import CodeBlock from "@/components/CodeBlock";
import JsonLd from "@/components/JsonLd";
import { cliReference, modes, panelPages, readyRules, ruleActions, ruleTriggers, softwareEffects } from "@/lib/content";
import { breadcrumbLd, pageMetadata, webPageLd } from "@/lib/seo";
import { site } from "@/lib/site";

const title = "Guide: lighting, fans and performance on Linux";
const description =
  "How to use ByteKeys: the service, keyboard lighting, performance modes, fan curves, charge limits, the launch key, automations, every command and troubleshooting.";

export const metadata: Metadata = pageMetadata({ title, description, path: "/guide" });

const toc = [
  ["start", "First start"],
  ["center", "The control center"],
  ["performance", "Performance and fans"],
  ["battery", "Battery charge limit"],
  ["launch-key", "Launch key"],
  ["lighting", "Lighting and effects"],
  ["automation", "Automation"],
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
  ["launch_key", "0", "The evdev code of the key that opens ByteKeys; 0 is off. Set it from Settings → Launch key."],
  ["openrgb", "true", "Look for an OpenRGB SDK server."],
  ["openrgb_host", "127.0.0.1", "Where the OpenRGB SDK server runs."],
  ["openrgb_port", "6742", "Its port."],
  ["openrgb_all_devices", "false", "Use every OpenRGB device, not only keyboards."],
] as const;

export default function GuidePage() {
  const howTo = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: "Control keyboard lighting, fans and performance modes on a Linux laptop with ByteKeys",
    step: [
      { "@type": "HowToStep", name: "Install ByteKeys", text: "Install the .deb on Debian, Ubuntu, Linux Mint, Pop!_OS or Zorin, or run the AppImage on any distribution.", url: `${site.url}/download` },
      { "@type": "HowToStep", name: "Install the service", text: "The .deb starts the service itself. In the AppImage, click Install service on the Settings page to unlock colors, fan control and background automations.", url: `${site.url}/guide#start` },
      { "@type": "HowToStep", name: "Pick a performance mode", text: "Choose Silent, Balanced or Performance on the Home or Performance page, and draw fan curves on ASUS laptops.", url: `${site.url}/guide#performance` },
      { "@type": "HowToStep", name: "Set the lighting", text: "Pick a mode, an effect and colors for the whole keyboard, a zone or single keys on the Lighting page.", url: `${site.url}/guide#lighting` },
      { "@type": "HowToStep", name: "Automate it", text: "Turn on ready-made automations such as Dim on battery or Turn off when idle, or write your own.", url: `${site.url}/guide#automation` },
    ],
  };

  return (
    <>
      <JsonLd data={[webPageLd({ path: "/guide", name: `${title} · ByteKeys`, description }), breadcrumbLd([["Guide", "/guide"]]), howTo]} />
      <section className="container-x pt-14 sm:pt-20">
        <p className="eyebrow">Guide</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">Using ByteKeys</h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-dim">
          From the first start to fan curves, automations, the command line and what to do when something isn&apos;t found.
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
            Open <strong>ByteKeys</strong> from your applications menu, or press your laptop&apos;s launch key. It identifies your
            laptop, picks the right drivers and creates profiles and automations to start from.
          </p>
          <p>
            Lighting, fans and battery settings need root, so a small service, <code>bytekeysd</code>, does the hardware work
            while the control center runs as you:
          </p>
          <ul>
            <li>
              <strong>.deb:</strong> the service comes with the package and starts on installation.
            </li>
            <li>
              <strong>AppImage:</strong> it starts in portable mode. Click <strong>Install service</strong> on the Settings page
              or the banner; it asks for your password once and installs the service to <code>/opt/bytekeys</code>.
            </li>
            <li>
              <strong>From source:</strong> <code>sudo make install</code> installs to <code>/usr/local</code> and starts the
              service.
            </li>
          </ul>
          <p>
            In portable mode, without the service, the control center and the command line run the same engine themselves with
            whatever your user may access. Brightness still works for the active desktop user; colors, fan control and
            background automations need the service. Check it with <code>bytekeys service status</code>. When the control center
            finds an older service than itself, it offers to update it.
          </p>

          <h2 id="center">The control center</h2>
          <p>Six pages in the sidebar, in a dark or light look:</p>
          <ul>
            {panelPages.map((p) => (
              <li key={p.id}>
                <strong>{p.name}:</strong> {p.body}
              </li>
            ))}
          </ul>
          <p>A tray icon gives you quick changes without opening the window.</p>

          <h2 id="performance">Performance and fans</h2>
          <p>
            <strong>Performance modes</strong> are the firmware&apos;s own: Silent, Balanced and Performance on ASUS, and
            whatever your laptop offers through its ACPI platform profile elsewhere. ByteKeys switches them through
            power-profiles-daemon when it runs, so your desktop&apos;s power menu stays in sync, and notices changes made with the
            Fn keys or the desktop.
          </p>
          <p>
            <strong>Fan curves</strong> work on ASUS laptops with firmware fan curves, most TUF and ROG since 2021. Drag the eight
            points of each fan&apos;s curve on the Performance page, start from a preset, or go back to the factory curve. Each
            performance mode keeps its own curves, and ByteKeys switches them with the mode, including from the Fn keys. Every
            curve is checked before it reaches the firmware: temperatures rise, speeds never drop, at least 50% from 80 °C and at
            least 70% at the last point.
          </p>
          <p>
            <strong>Full fan speed</strong> is a switch on ASUS laptops with SPEC 8.3 fans. Your curves come back when you turn
            it off.
          </p>
          <p>
            ByteKeys never drives fan speeds itself: the firmware runs the curves, so a crash or a stopped service can never leave
            a fan off. The kernel forgets custom curves on every mode change, at boot and after sleep, so the service puts them
            back and checks every second that they are still active.
          </p>
          <div className="not-prose mt-4">
            <CodeBlock
              id="guide-perf"
              code={
                "bytekeys perf                 # current mode and the modes available\nbytekeys perf quiet           # switch mode\nbytekeys fans                 # temperatures, fan speeds and curves\nbytekeys fans boost on        # full fan speed (off to stop)\nbytekeys fans firmware 1      # CPU fan back to the firmware curve"
              }
            />
          </div>

          <h2 id="battery">Battery charge limit</h2>
          <p>
            A laptop that lives on its charger lasts longer when it stops charging early. Pick 60, 80 or 100% on the Home or
            Performance page (80 or 100% on LG). It works on laptops with a charge threshold, such as ASUS, ThinkPad, Dell,
            Huawei, LG, Samsung, MSI, System76, Toshiba and Fujitsu, and on Lenovo IdeaPad and Legion conservation mode. Some
            laptops reset the limit at boot; the service sets it again at start and after resume.
          </p>
          <div className="not-prose mt-4">
            <CodeBlock id="guide-charge" code={"bytekeys charge-limit       # show the limit\nbytekeys charge-limit 80    # stop charging at 80 %"} />
          </div>

          <h2 id="launch-key">Launch key</h2>
          <p>
            The key that opens Armoury Crate, NitroSense, PredatorSense, OMEN Gaming Hub, MSI Center or MyASUS on Windows opens
            ByteKeys. It knows the keys of the laptops listed on the hardware page; <strong>Settings → Launch key → Detect key</strong>{" "}
            learns any other special key. With the service running, the key brings ByteKeys to the front from anywhere.
          </p>
          <p>
            On GNOME-based desktops (Ubuntu, Pop!_OS, Zorin and others) and KDE Plasma, ByteKeys also adds a desktop shortcut, so
            the key starts ByteKeys when it is closed; on KDE it takes effect at the next login. On other desktops, add a
            shortcut that runs <code>bytekeys-gui</code>. The <Link href="/hardware#keys-heading">hardware page</Link> lists the
            keys ByteKeys knows.
          </p>

          <h2 id="lighting">Lighting and effects</h2>
          <p>
            One-click modes: {modes.join(", ")}, each with an animated preview. When your keyboard has its own hardware mode for
            one of them, ByteKeys uses it. Software effects work on every keyboard, even plain white ones:{" "}
            {softwareEffects.join(", ")}. Pick colors with the color wheel for the whole keyboard, or click and drag over keys in
            the preview for zones and single keys.
          </p>

          <h2 id="automation">Automation</h2>
          <p>
            An automation is <em>when this happens, do that</em>. While its trigger holds, its action is layered on top of your
            own settings. Automations apply top to bottom, so later ones win. When you change a setting an automation is
            overriding, it steps aside until it stops applying. Thresholds have some slack, so a value hovering near a limit
            doesn&apos;t flicker.
          </p>
          <h3>Ready-made automations</h3>
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
            From the command line they are called rules: <code>bytekeys rules enable battery-dim</code>,{" "}
            <code>bytekeys rules export</code> and <code>bytekeys rules import FILE</code>.
          </p>

          <h2 id="profiles">Profiles</h2>
          <p>
            A profile is a saved look for all your keyboards. Switch profiles from the control center, the tray, the command line
            (<code>bytekeys profile apply Night</code>) or an automation, such as Night mode.
          </p>

          <h2 id="shortcuts">Keyboard shortcuts</h2>
          <p>
            ByteKeys follows the laptop&apos;s own Fn keys. On laptops whose Fn keys don&apos;t reach the backlight, bind these
            commands to shortcuts in your desktop&apos;s keyboard settings:
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
            <table className="w-full min-w-[36rem] text-left text-sm">
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
            The Settings page shows what ByteKeys found and hints, such as a kernel module to install. Use{" "}
            <strong>Settings → Copy report</strong>, or run <code>bytekeys report</code>, and open a{" "}
            <a href={site.deviceIssue}>Device support issue</a> with it. The <Link href="/hardware">hardware page</Link> lists what
            works today.
          </p>
          <h3>Colors, fans or automations don&apos;t change anything</h3>
          <p>
            You are probably in portable mode. Install the service (see <a href="#start">First start</a>) and check it with{" "}
            <code>bytekeys service status</code>.
          </p>
          <h3>My fan curves keep resetting</h3>
          <p>
            Another program is probably rewriting them, for example asusd running alongside ByteKeys. ByteKeys backs off and logs
            a warning when that happens; use one of the two for fan curves.
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
              Input devices are read only for activity timestamps and to compare presses with the one configured launch key. Key
              codes are never stored or logged, and detecting a launch key accepts only special keys, never letters, digits or
              modifiers.
            </li>
            <li>Fan curves are validated, and only firmware-run curves are used, so ByteKeys can never leave the fans stopped.</li>
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
