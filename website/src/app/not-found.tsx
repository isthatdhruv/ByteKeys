import Link from "next/link";

export default function NotFound() {
  return (
    <section className="container-x py-28 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">This page doesn&apos;t exist.</h1>
      <p className="mt-4 text-dim">It may have moved. These pages are a good place to start:</p>
      <p className="mt-8 flex flex-wrap justify-center gap-3">
        <Link href="/" className="btn btn-primary">
          Home
        </Link>
        <Link href="/download" className="btn btn-ghost">
          Download
        </Link>
        <Link href="/hardware" className="btn btn-ghost">
          Supported hardware
        </Link>
      </p>
    </section>
  );
}
