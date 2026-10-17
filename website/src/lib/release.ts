import { site } from "@/lib/site";

// The latest release, read from GitHub: file names, hashes and the version from the release's
// SHA256SUMS, sizes from the files themselves, the date and notes from CHANGELOG.md. Pages that use it
// revalidate hourly, so a new release shows up without a deploy. Every value is null when GitHub
// can't be reached, and the pages then link to the releases page instead.

const REVALIDATE = 3600;

export interface ReleaseFile {
  name: string;
  url: string;
  sha256: string;
  sizeBytes: number | null;
}

export interface Release {
  version: string;
  tag: string;
  /** ISO date from the CHANGELOG heading, when there is one. */
  date: string | null;
  /** The CHANGELOG entry's bullet points, as written there (Markdown inline code kept). */
  notes: string[];
  deb: ReleaseFile | null;
  appImage: ReleaseFile | null;
  checksumsUrl: string;
  pageUrl: string;
}

async function getText(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, { next: { revalidate: REVALIDATE }, signal: AbortSignal.timeout(8000) });
    return res.ok ? await res.text() : null;
  } catch {
    return null;
  }
}

// A one-byte range request: GitHub's signed download URLs refuse HEAD, but answer a ranged GET with
// the full size in Content-Range.
async function getSize(url: string): Promise<number | null> {
  try {
    const res = await fetch(url, {
      headers: { Range: "bytes=0-0" },
      next: { revalidate: REVALIDATE },
      signal: AbortSignal.timeout(8000),
    });
    const total = Number(res.headers.get("content-range")?.split("/")[1]);
    const length = Number(res.headers.get("content-length"));
    await res.arrayBuffer();
    if (res.status === 206 && total > 0) return total;
    return res.ok && length > 1 ? length : null;
  } catch {
    return null;
  }
}

/** "<sha256>  <name>" lines (sha256sum output; a "*" before the name marks binary mode). */
export function parseChecksums(text: string): { sha256: string; name: string }[] {
  return text
    .split("\n")
    .map((line) => line.trim().match(/^([0-9a-f]{64})\s+\*?(.+)$/i))
    .filter((m): m is RegExpMatchArray => m !== null)
    .map((m) => ({ sha256: m[1].toLowerCase(), name: m[2].trim() }));
}

/** The "## <version> (<date>)" section of CHANGELOG.md, with wrapped bullets joined. */
export function parseChangelog(text: string, version: string): { date: string | null; notes: string[] } | null {
  const lines = text.split("\n");
  const start = lines.findIndex((l) => l.startsWith(`## ${version} `) || l.trim() === `## ${version}`);
  if (start === -1) return null;
  const date = lines[start].match(/\((\d{4}-\d{2}-\d{2})\)/)?.[1] ?? null;
  const notes: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (line.startsWith("## ")) break;
    if (line.startsWith("- ")) notes.push(line.slice(2).trim());
    else if (/^\s+\S/.test(line) && notes.length) notes[notes.length - 1] += ` ${line.trim()}`;
  }
  return { date, notes };
}

export async function getLatestRelease(): Promise<Release | null> {
  const sums = await getText(site.checksums);
  if (!sums) return null;
  const files = parseChecksums(sums);
  const deb = files.find((f) => /^bytekeys_.+_all\.deb$/.test(f.name));
  const appImage = files.find((f) => /^ByteKeys-.+-x86_64\.AppImage$/.test(f.name));
  const version =
    deb?.name.match(/^bytekeys_(.+)_all\.deb$/)?.[1] ?? appImage?.name.match(/^ByteKeys-(.+)-x86_64\.AppImage$/)?.[1];
  if (!version) return null;
  const tag = `v${version}`;
  const download = (name: string) => `${site.repo}/releases/download/${tag}/${encodeURIComponent(name)}`;
  const withSize = async (f: { sha256: string; name: string } | undefined): Promise<ReleaseFile | null> =>
    f ? { ...f, url: download(f.name), sizeBytes: await getSize(download(f.name)) } : null;

  const [debFile, appImageFile, changelog] = await Promise.all([
    withSize(deb),
    withSize(appImage),
    getText(site.changelogRaw),
  ]);
  const entry = changelog ? parseChangelog(changelog, version) : null;
  return {
    version,
    tag,
    date: entry?.date ?? null,
    notes: entry?.notes ?? [],
    deb: debFile,
    appImage: appImageFile,
    checksumsUrl: download("SHA256SUMS"),
    pageUrl: `${site.repo}/releases/tag/${tag}`,
  };
}

export function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}
