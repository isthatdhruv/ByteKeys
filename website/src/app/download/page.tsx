import type { Metadata } from "next";
import Link from "next/link";
import { Download, Package, Terminal } from "lucide-react";
import CodeBlock from "@/components/CodeBlock";
import GithubMark from "@/components/GithubMark";
import JsonLd from "@/components/JsonLd";
import TrackedLink from "@/components/TrackedLink";
import { formatDate, formatSize, getLatestRelease, type ReleaseFile } from "@/lib/release";
import { breadcrumbLd, faqLd, pageMetadata, webPageLd } from "@/lib/seo";
import { site } from "@/lib/site";

export const revalidate = 3600;

const title = "Download for Linux: .deb and AppImage";
const description =
  "Download ByteKeys for Linux: a .deb for Debian, Ubuntu, Linux Mint, Pop!_OS and Zorin, an AppImage for any distribution, or build from source. Free, GPL-3.0.";

export const metadata: Metadata = pageMetadata({ title, description, path: "/download" });

const faq = [
  {
    q: "Which file do I need?",
    a: "On Debian, Ubuntu, Linux Mint, Pop!_OS or Zorin, take the .deb: it includes the background service and starts it for you. On any other x86_64 distribution, take the AppImage and click Install service once it is running.",
  },
  {
    q: "What does the AppImage's Install service button do?",
    a: "It asks for your password once and installs the ByteKeys service to /opt/bytekeys with a systemd unit, which unlocks color control and background rules. Remove it again with the AppImage's service uninstall command.",
  },
  {
    q: "How do I check the download?",
    a: "Every release publishes a SHA256SUMS file. Download it next to the package and run sha256sum -c SHA256SUMS --ignore-missing; each file you downloaded should report OK.",
  },
];

// Inline `code` from CHANGELOG bullets.
function Notes({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/).map((part, i) =>
        part.startsWith("`") && part.endsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> : <span key={i}>{part}</span>,
      )}
    </>
  );
}

function FileButton({ file, kind, label }: { file: ReleaseFile; kind: string; label: string }) {
  return (
    <TrackedLink href={file.url} event="download_click" props={{ file: kind }} className="btn btn-primary">
      <Download aria-hidden="true" className="h-4 w-4" /> {label}
      {file.sizeBytes ? <span className="font-normal opacity-80">· {formatSize(file.sizeBytes)}</span> : null}
    </TrackedLink>
  );
}

export default async function DownloadPage() {
  const release = await getLatestRelease();
  const deb = release?.deb;
  const appImage = release?.appImage;
  const debName = deb?.name ?? "bytekeys_<version>_all.deb";
  const appImageName = appImage?.name ?? "ByteKeys-<version>-x86_64.AppImage";

  return (
    <>
      <JsonLd
        data={[
          webPageLd({ path: "/download", name: `${title} · ByteKeys`, description }),
          breadcrumbLd([["Download", "/download"]]),
          faqLd(faq),
        ]}
      />
      <section className="container-x pt-14 sm:pt-20">
        <p className="eyebrow">Download</p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight sm:text-5xl">Download ByteKeys for Linux</h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-dim">
          Free and open source. Pick the package for your distribution, or build it from source.
        </p>
        {release ? (
          <p className="mt-4 text-sm text-faint">
            Version {release.version}
            {release.date && <> · released {formatDate(release.date)}</>} ·{" "}
            <a href={release.pageUrl} className="text-accent hover:underline">
              release on GitHub
            </a>
          </p>
        ) : (
          <div className="mt-8">
            <a href={site.latestRelease} className="btn btn-primary">
              <Download aria-hidden="true" className="h-4 w-4" /> Get the latest release on GitHub
            </a>
          </div>
        )}
      </section>

      <section aria-label="Packages" className="container-x mt-12 grid gap-5 lg:grid-cols-2">
        <article className="card flex min-w-0 flex-col p-6 sm:p-8">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent/12 text-accent">
              <Package aria-hidden="true" className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-xl font-semibold text-ink">.deb package</h2>
              <p className="text-sm text-dim">Debian, Ubuntu, Linux Mint, Pop!_OS, Zorin</p>
            </div>
          </div>
          <p className="mt-5 text-[15px] leading-relaxed text-dim">
            Includes the background service, which apt enables and starts for you. Open ByteKeys from your applications menu
            afterwards.
          </p>
          <div className="mt-6">
            {deb ? <FileButton file={deb} kind="deb" label="Download .deb" /> : null}
          </div>
          <div className="mt-6">
            <CodeBlock id="install-deb" label="Install" code={`cd ~/Downloads\nsudo apt install ./${debName}`} />
          </div>
        </article>

        <article className="card flex min-w-0 flex-col p-6 sm:p-8">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent/12 text-accent">
              <Package aria-hidden="true" className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-xl font-semibold text-ink">AppImage</h2>
              <p className="text-sm text-dim">Any distribution, x86_64</p>
            </div>
          </div>
          <p className="mt-5 text-[15px] leading-relaxed text-dim">
            Starts in portable mode. Click <strong className="text-ink">Install service</strong> on the System page or the banner to
            unlock color control and background rules: it asks for your password once and installs the service to{" "}
            <code>/opt/bytekeys</code>.
          </p>
          <div className="mt-6">
            {appImage ? <FileButton file={appImage} kind="appimage" label="Download AppImage" /> : null}
          </div>
          <div className="mt-6">
            <CodeBlock
              id="install-appimage"
              label="Run"
              code={`cd ~/Downloads\nchmod +x ${appImageName}\n./${appImageName}`}
            />
          </div>
          <p className="mt-4 text-sm text-dim">
            The same file runs the command line tool: <code>./{appImageName} cli status</code>
          </p>
        </article>
      </section>

      <section aria-labelledby="source-heading" className="container-x mt-5">
        <article className="card p-6 sm:p-8">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent/12 text-accent">
              <Terminal aria-hidden="true" className="h-5 w-5" />
            </span>
            <div>
              <h2 id="source-heading" className="text-xl font-semibold text-ink">
                From source
              </h2>
              <p className="text-sm text-dim">Python 3.10 or later, with PyQt6 or PySide6</p>
            </div>
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <CodeBlock
              id="install-source"
              code={`git clone https://github.com/isthatdhruv/ByteKeys.git && cd ByteKeys\nmake run            # control panel from the source tree\nsudo make install   # install to /usr/local and start the service`}
            />
            <p className="text-[15px] leading-relaxed text-dim">
              The service and the command line tool use only the Python standard library; the control panel adds Qt 6.{" "}
              <code>make demo</code> opens the control panel with simulated keyboards, and <code>sudo make uninstall</code> removes
              a <code>make install</code>.
            </p>
          </div>
        </article>
      </section>

      {release && (deb || appImage) ? (
        <section aria-labelledby="verify-heading" className="container-x mt-16">
          <h2 id="verify-heading" className="text-2xl font-bold tracking-tight">
            Verify the download
          </h2>
          <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-dim">
            Every release is built by GitHub Actions from a tagged commit and publishes SHA-256 checksums. Download{" "}
            <a href={release.checksumsUrl} className="text-accent hover:underline">
              SHA256SUMS
            </a>{" "}
            next to the package, then:
          </p>
          <div className="mt-5 max-w-2xl">
            <CodeBlock id="verify" code="sha256sum -c SHA256SUMS --ignore-missing" />
          </div>
          <dl className="mt-6 space-y-3 text-sm">
            {[deb, appImage].filter((f): f is ReleaseFile => Boolean(f)).map((f) => (
              <div key={f.name} className="card px-4 py-3">
                <dt className="font-medium text-ink">{f.name}</dt>
                <dd className="mt-1 break-all font-mono text-xs text-dim">{f.sha256}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {release && release.notes.length ? (
        <section aria-labelledby="notes-heading" className="container-x mt-16">
          <h2 id="notes-heading" className="text-2xl font-bold tracking-tight">
            What&apos;s in {release.version}
          </h2>
          <ul className="mt-5 max-w-3xl list-disc space-y-2 pl-5 text-[15px] leading-relaxed text-dim marker:text-accent">
            {release.notes.map((n) => (
              <li key={n}>
                <Notes text={n} />
              </li>
            ))}
          </ul>
          <p className="mt-5 text-sm">
            <a href={site.changelog} className="text-accent hover:underline">
              Full changelog
            </a>{" "}
            ·{" "}
            <a href={site.releases} className="text-accent hover:underline">
              All releases
            </a>
          </p>
        </section>
      ) : null}

      <section aria-labelledby="req-heading" className="container-x mt-16 grid gap-10 lg:grid-cols-2">
        <div className="min-w-0">
          <h2 id="req-heading" className="text-2xl font-bold tracking-tight">
            Requirements
          </h2>
          <ul className="mt-4 space-y-3 text-[15px] leading-relaxed text-dim">
            <li>
              <strong className="text-ink">.deb:</strong> <code>python3</code> 3.10 or later and <code>python3-pyqt6</code> or{" "}
              <code>python3-pyside6.qtwidgets</code>, which apt installs. It recommends <code>pkexec</code> and{" "}
              <code>qt6-wayland</code> and suggests <code>openrgb</code>.
            </li>
            <li>
              <strong className="text-ink">AppImage:</strong> brings its own Python and PySide6.
            </li>
            <li>
              <strong className="text-ink">OpenRGB keyboards:</strong> run OpenRGB with its SDK server enabled,{" "}
              <code>openrgb --server</code>. ByteKeys connects to it on <code>127.0.0.1:6742</code>.
            </li>
          </ul>
        </div>
        <div className="min-w-0">
          <h2 className="text-2xl font-bold tracking-tight">Uninstall</h2>
          <div className="mt-4 space-y-4">
            <CodeBlock id="uninstall-deb" label=".deb" code={"sudo apt remove bytekeys   # keeps your settings\nsudo apt purge bytekeys    # also removes /var/lib/bytekeys"} />
            <CodeBlock id="uninstall-appimage" label="AppImage service" code={`./${appImageName} service uninstall`} />
          </div>
        </div>
      </section>

      <section aria-labelledby="dl-faq-heading" className="container-x mt-16 max-w-3xl">
        <h2 id="dl-faq-heading" className="text-2xl font-bold tracking-tight">
          Download questions
        </h2>
        <div className="mt-6 divide-y divide-line rounded-2xl border border-line bg-surface">
          {faq.map((f) => (
            <div key={f.q} className="px-5 py-4">
              <h3 className="font-medium text-ink">{f.q}</h3>
              <p className="mt-1.5 text-[15px] leading-relaxed text-dim">{f.a}</p>
            </div>
          ))}
        </div>
        <p className="mt-8 flex flex-wrap gap-3">
          <Link href="/guide" className="btn btn-ghost">
            First steps in the guide
          </Link>
          <a href={site.repo} className="btn btn-ghost">
            <GithubMark className="h-4 w-4" /> Source on GitHub
          </a>
        </p>
      </section>
    </>
  );
}
