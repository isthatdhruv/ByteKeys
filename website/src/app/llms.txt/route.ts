import { cliExamples, features, hardware, homeFaq } from "@/lib/content";
import { site } from "@/lib/site";

export const dynamic = "force-static";

// A plain-text summary for language models and answer engines (llmstxt.org).
export function GET() {
  const body = `# ByteKeys

> ${site.tagline}. Free and open-source (${site.license.id}). White backlights, single-zone, multi-zone and per-key RGB, detected and configured automatically.

ByteKeys is a Linux app with a control panel, a tray icon, a command line tool (bytekeys) and a small root service (bytekeysd). It is an open-source project by ${site.company.name} (${site.company.url}) and its contributors. Source: ${site.repo}

## Pages

- [Download](${site.url}/download): .deb for Debian, Ubuntu, Linux Mint, Pop!_OS and Zorin; AppImage for any x86_64 distribution; build from source with Python 3.10+ and PyQt6 or PySide6.
- [Supported hardware](${site.url}/hardware): every laptop family, controller and kernel interface, with status.
- [Guide](${site.url}/guide): service and portable mode, effects, rules, profiles, shortcuts, every command, settings, OpenRGB, troubleshooting.
- [Privacy](${site.url}/privacy)

## Features

${features.map((f) => `- ${f.title}: ${f.body}`).join("\n")}

## Supported hardware

${hardware.map((h) => `- ${h.name}${h.ids ? ` (${h.ids})` : ""}: ${h.lighting}. Through ${h.through}. ${h.status}.`).join("\n")}

## Command line examples

${cliExamples.map((c) => `- \`${c.cmd}\`${c.note ? `: ${c.note}` : ""}`).join("\n")}

## FAQ

${homeFaq.map((f) => `### ${f.q}\n\n${f.a}`).join("\n\n")}
`;
  return new Response(body, { headers: { "content-type": "text/plain; charset=utf-8" } });
}
