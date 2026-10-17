import type { Metadata } from "next";
import Link from "next/link";
import CodeBlock from "@/components/CodeBlock";
import JsonLd from "@/components/JsonLd";
import StatusBadge from "@/components/StatusBadge";
import { hardware, kernelInterfaces, statusNote, usbDrivers, type HardwareStatus } from "@/lib/content";
import { breadcrumbLd, faqLd, pageMetadata, webPageLd } from "@/lib/seo";
import { site } from "@/lib/site";

const title = "Supported laptops and keyboards";
const description =
  "Which laptop keyboards ByteKeys controls on Linux: ASUS TUF and ROG, Lenovo Legion, Clevo and TUXEDO per-key, Dell and Alienware, HP Omen, Acer, MSI, System76, ThinkPad and more.";

export const metadata: Metadata = pageMetadata({ title, description, path: "/hardware" });

// Questions people search for, answered from the hardware tables.
const faq = [
  {
    q: "Does ByteKeys support Lenovo Legion keyboard RGB on Linux?",
    a: "Yes for the 4-zone keyboards of Legion, LOQ and IdeaPad Gaming laptops (USB IDs 048d:c955 to c995), through a built-in driver with Breathing, Color cycle and Wave. It is marked Experimental until someone confirms it on their laptop. Legion per-key Spectrum keyboards work through OpenRGB.",
  },
  {
    q: "Does it work with ASUS TUF and ROG laptops?",
    a: "ASUS TUF Gaming keyboards work through the kernel's asus-wmi driver with RGB, Static, Breathing, Color cycle, Strobe and Pulse, and boot, awake and sleep lighting; this is tested on real hardware. Use kernel 6.5 or later, but not 6.10.0. ASUS ROG keyboards with a USB Aura controller have an Experimental built-in driver.",
  },
  {
    q: "What about Clevo, Tongfang, XMG and TUXEDO laptops?",
    a: "Per-key keyboards with an ITE 8291 controller have an Experimental built-in driver with 9 hardware effects. With tuxedo-drivers installed, TUXEDO, Clevo and Uniwill keyboards work through the kernel, 1-zone, 3-zone or per-key.",
  },
  {
    q: "Does it support Dell G-series and Alienware?",
    a: "Dell G15 and G16 and Alienware keyboards with the AW-ELC controller (187c:0550 and 0551) have an Experimental 4-zone driver with Breathing. Older Alienware laptops work through the kernel's alienware-wmi driver.",
  },
  {
    q: "HP Omen, Victus and Acer Predator or Nitro?",
    a: "Yes, with a kernel module: omen-rgb-keyboard or hp-omen for HP, four zones with animations; the facer module for Acer Predator and Nitro, four zones with effects. ByteKeys tells you which module is missing.",
  },
  {
    q: "My laptop only has a white backlight. Does ByteKeys help?",
    a: "Yes. White backlights on ThinkPad, IdeaPad, Yoga, Dell, Apple, Framework, Chromebook, Samsung, LG gram, Toshiba, Sony, MSI and more work through the kernel, with brightness levels and firmware timeouts where available, and the software effects work on them too.",
  },
  {
    q: "What about Razer, Gigabyte, AORUS and MSI per-key keyboards?",
    a: "Those go through OpenRGB. Run OpenRGB with its SDK server (openrgb --server) and ByteKeys controls whatever OpenRGB supports.",
  },
];

const order: HardwareStatus[] = ["Tested", "Supported", "Experimental"];

export default function HardwarePage() {
  return (
    <>
      <JsonLd data={[webPageLd({ path: "/hardware", name: `${title} · ByteKeys`, description }), breadcrumbLd([["Hardware", "/hardware"]]), faqLd(faq)]} />

      <section className="container-x pt-14 sm:pt-20">
        <p className="eyebrow">Supported hardware</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">Laptops and keyboards ByteKeys controls</h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-dim">
          Keyboard lights the Linux kernel exposes, common USB lighting controllers through built-in drivers, and everything
          OpenRGB supports.
        </p>
        <ul className="mt-8 grid gap-3 sm:grid-cols-3">
          {order.map((s) => (
            <li key={s} className="card p-4 text-sm leading-relaxed text-dim">
              <StatusBadge status={s} />
              <p className="mt-2">{statusNote[s]}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="all-heading" className="container-x mt-14">
        <h2 id="all-heading" className="text-2xl font-bold tracking-tight">
          All hardware
        </h2>
        <div className="mt-6 hidden overflow-hidden rounded-2xl border border-line md:block">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Hardware</th>
                <th scope="col" className="px-4 py-3 font-medium">Through</th>
                <th scope="col" className="px-4 py-3 font-medium">Lighting</th>
                <th scope="col" className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {hardware.map((h) => (
                <tr key={h.id} id={h.id} className="scroll-mt-24 align-top">
                  <td className="px-4 py-3">
                    <span className="font-medium text-ink">{h.name}</span>
                    {h.ids && <span className="mt-1 block font-mono text-xs text-faint">{h.ids}</span>}
                  </td>
                  <td className="px-4 py-3 text-dim">
                    {h.throughUrl ? (
                      <a href={h.throughUrl} className="text-accent hover:underline">
                        {h.through}
                      </a>
                    ) : (
                      h.through
                    )}
                  </td>
                  <td className="px-4 py-3 text-dim">{h.lighting}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={h.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="mt-6 space-y-3 md:hidden">
          {hardware.map((h) => (
            <li key={h.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <span className="font-medium text-ink">{h.name}</span>
                <StatusBadge status={h.status} />
              </div>
              {h.ids && <p className="mt-1 font-mono text-xs text-faint">{h.ids}</p>}
              <p className="mt-2 text-sm text-dim">{h.lighting}</p>
              <p className="mt-1 text-sm text-faint">Through {h.through}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="missing-heading" className="container-x mt-16 grid gap-8 lg:grid-cols-2">
        <div className="min-w-0">
          <h2 id="missing-heading" className="text-2xl font-bold tracking-tight">
            Keyboard not detected?
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-dim">
            Find out how your keyboard&apos;s lighting is reachable, then open a{" "}
            <a href={site.deviceIssue} className="text-accent hover:underline">
              Device support issue
            </a>{" "}
            with the report. In the control panel, the System page copies the same report.
          </p>
          <div className="mt-5">
            <CodeBlock
              id="hw-report"
              code={"bytekeys report          # what ByteKeys sees: LEDs, HID devices, USB IDs, kernel modules\nls /sys/class/leds/      # kernel LED devices (look for *kbd_backlight*)\nlsusb                    # USB lighting controllers"}
            />
          </div>
        </div>
        <div className="min-w-0">
          <h2 className="text-2xl font-bold tracking-tight">Write the driver</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-dim">
            Adding a keyboard is usually one small driver class. If <code>/sys/class/leds/</code> already has a{" "}
            <code>kbd_backlight</code> entry, ByteKeys most likely handles it. USB and I2C HID controllers get a driver in{" "}
            <code>bytekeys/hw/drivers/</code>, with a byte-exact test, and stay Experimental until someone confirms them on real
            hardware.
          </p>
          <p className="mt-4">
            <a href={site.docs.addingDevices} className="btn btn-ghost">
              Read the driver guide
            </a>
          </p>
        </div>
      </section>

      <section aria-labelledby="usb-heading" className="container-x mt-16">
        <h2 id="usb-heading" className="text-2xl font-bold tracking-tight">
          Built-in USB and HID drivers
        </h2>
        <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-dim">
          These controllers are driven directly through <code>/dev/hidraw</code>. Animations are never written to keyboard
          memory; a settled look is saved only when you turn on saving to the keyboard.
        </p>
        <div className="mt-6 overflow-x-auto rounded-2xl border border-line">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Controller</th>
                <th scope="col" className="px-4 py-3 font-medium">USB IDs</th>
                <th scope="col" className="px-4 py-3 font-medium">Writes keyboard memory</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {usbDrivers.map((d) => (
                <tr key={d.name} className="align-top">
                  <td className="px-4 py-3 font-medium text-ink">{d.name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-dim">{d.ids}</td>
                  <td className="px-4 py-3 text-dim">{d.flash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-dim">
          Not built in, use OpenRGB: Lenovo per-key Spectrum, MSI per-key SteelSeries, Gigabyte and AORUS, Razer (or OpenRazer).
        </p>
      </section>

      <section aria-labelledby="kernel-heading" className="container-x mt-16">
        <h2 id="kernel-heading" className="text-2xl font-bold tracking-tight">
          Kernel interfaces
        </h2>
        <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-dim">
          Without the service, brightness still works for the active desktop user through systemd-logind; colors and modes need
          the service.
        </p>
        <div className="mt-6 overflow-x-auto rounded-2xl border border-line">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="bg-surface-2 text-xs uppercase tracking-wider text-faint">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">Driver or module</th>
                <th scope="col" className="px-4 py-3 font-medium">LED or path</th>
                <th scope="col" className="px-4 py-3 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {kernelInterfaces.map((k) => (
                <tr key={k.driver} className="align-top">
                  <td className="px-4 py-3 font-medium text-ink">{k.driver}</td>
                  <td className="px-4 py-3 font-mono text-xs text-dim">{k.path}</td>
                  <td className="px-4 py-3 text-dim">{k.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-dim">
          Protocol details for every driver are in{" "}
          <a href={site.docs.supportedHardware} className="text-accent hover:underline">
            docs/SUPPORTED_HARDWARE.md
          </a>
          .
        </p>
      </section>

      <section aria-labelledby="hw-faq-heading" className="container-x mt-16 max-w-3xl">
        <h2 id="hw-faq-heading" className="text-2xl font-bold tracking-tight">
          Hardware questions
        </h2>
        <div className="mt-6 divide-y divide-line rounded-2xl border border-line bg-surface">
          {faq.map((f) => (
            <div key={f.q} className="px-5 py-4">
              <h3 className="font-medium text-ink">{f.q}</h3>
              <p className="mt-1.5 text-[15px] leading-relaxed text-dim">{f.a}</p>
            </div>
          ))}
        </div>
        <p className="mt-8">
          <Link href="/download" className="btn btn-primary">
            Download ByteKeys
          </Link>
        </p>
      </section>
    </>
  );
}
