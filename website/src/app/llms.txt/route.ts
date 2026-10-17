import { cliExamples, features, hardware, homeFaq, launchKeys, performanceFeatures } from "@/lib/content";
import { site } from "@/lib/site";

export const dynamic = "force-static";

// A plain-text summary for language models and answer engines (llmstxt.org).
export function GET() {
  const body = `# ByteKeys

> ${site.tagline}. Free and open-source (${site.license.id}). White backlights, single-zone, multi-zone and per-key RGB, detected and configured automatically.

ByteKeys is a Linux control center for laptops: keyboard lighting, performance modes, fan curves (ASUS), a battery charge limit and the vendor launch key (Armoury Crate, NitroSense, OMEN, MSI Center). It has a control center app, a tray icon, a command line tool (bytekeys) and a small root service (bytekeysd). It is an open-source project by ${site.company.name} (${site.company.url}) and its contributors. Source: ${site.repo}

## Pages

- [Download](${site.url}/download): .deb for Debian, Ubuntu, Linux Mint, Pop!_OS and Zorin; AppImage for any x86_64 distribution; build from source with Python 3.10+ and PyQt6 or PySide6.
- [Supported hardware](${site.url}/hardware): every laptop family, controller and kernel interface, with status.
- [Guide](${site.url}/guide): service and portable mode, performance modes, fan curves, charge limit, launch key, lighting, automations, profiles, every command, settings, OpenRGB, troubleshooting.
- [Privacy](${site.url}/privacy)

## Features

${features.map((f) => `- ${f.title}: ${f.body}`).join("\n")}

## Performance, fans and battery

${performanceFeatures.map((f) => `- ${f.feature}: ${f.worksOn}. Through ${f.through}.`).join("\n")}

ByteKeys only uses controls the firmware runs itself and never drives fan PWM directly. Fan curves must keep the fans at 50% or more from 80 °C and end at 70% or more.

## Launch keys

${launchKeys.map((k) => `- ${k.laptop}: ${k.key} (${k.code})`).join("\n")}

## Supported keyboard lighting

${hardware.map((h) => `- ${h.name}${h.ids ? ` (${h.ids})` : ""}: ${h.lighting}. Through ${h.through}. ${h.status}.`).join("\n")}

## Command line examples

${cliExamples.map((c) => `- \`${c.cmd}\`${c.note ? `: ${c.note}` : ""}`).join("\n")}

## FAQ

${homeFaq.map((f) => `### ${f.q}\n\n${f.a}`).join("\n\n")}
`;
  return new Response(body, { headers: { "content-type": "text/plain; charset=utf-8" } });
}
