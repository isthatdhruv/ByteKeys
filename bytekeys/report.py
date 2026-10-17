"""Plain-text diagnostics report for bug reports and device support requests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from . import __version__, fsroot, sysinfo
from .hw.hidraw import enumerate_hidraw

if TYPE_CHECKING:
    from .engine.core import Engine


def _section(title: str) -> str:
    return f"\n## {title}\n"


def build_report(engine: "Engine") -> str:
    info = engine.system()
    dmi = info["dmi"]
    lines = [f"# ByteKeys {__version__} diagnostic report", ""]
    lines.append(f"Model:   {info['model']}  (family: {info.get('family') or 'unknown'})")
    lines.append(f"OS:      {info['os']}  kernel {info['kernel']}  {info['arch']}")
    lines.append(f"Mode:    {info['mode']}  privileged={info['privileged']}  "
                 f"input-watch={info['input_watch']}  appimage={info['appimage']}")

    lines.append(_section("DMI"))
    for k, v in dmi.items():
        if v and k not in ("product_serial", "board_serial", "chassis_serial", "product_uuid"):
            lines.append(f"{k:16} {v}")

    lines.append(_section("Relevant kernel modules"))
    lines.append(", ".join(info["modules"]) or "(none)")

    lines.append(_section("Devices"))
    for dev in engine.device_list():
        lines.append(f"- {dev['id']}: {dev['name']} [{dev['backend']}] color={dev['color_mode']} "
                     f"zones={len(dev['zones'])} brightness_max={dev['brightness_max']}")
        if dev.get("access"):
            lines.append(f"    access: {dev['access']}")
        if dev.get("error"):
            lines.append(f"    error:  {dev['error']}")
        hw = [e["id"] for e in dev["effects"] if e["hardware"]]
        if hw:
            lines.append(f"    hardware effects: {', '.join(hw)}")
        with engine.lock:
            device = engine.devices.get(dev["id"])
        if device is not None:
            try:
                diag = device.diagnostics()
            except Exception as e:  # diagnostics must never break the report
                diag = {"error": str(e)}
            lines.append("    " + json.dumps(diag, sort_keys=True, default=str)[:4000])
    if not engine.devices:
        lines.append("(no controllable devices found)")

    lines.append(_section("LED class devices"))
    for name in fsroot.listdir("/sys/class/leds"):
        if name.startswith("input") or "::lan" in name:
            continue
        max_b = fsroot.read(f"/sys/class/leds/{name}/max_brightness")
        attrs = [a for a in fsroot.listdir(f"/sys/class/leds/{name}")
                 if a not in ("device", "power", "subsystem", "uevent", "trigger")]
        lines.append(f"{name}  max={max_b}  attrs={','.join(attrs)}")

    lines.append(_section("HID devices"))
    for h in enumerate_hidraw():
        apps = " ".join(f"{p:04x}:{u:04x}" for p, u in h.reports.applications)
        feats = " ".join(f"id{k:#x}={v}B" for k, v in sorted(h.reports.feature.items()))
        lines.append(f"{h.node}  bus={h.bus:#04x}  {h.vid:04x}:{h.pid:04x}  if={h.interface}  "
                     f"{h.name!r}  usages=[{apps}]  feature=[{feats}]")

    lines.append(_section("USB devices"))
    for u in sysinfo.usb_devices():
        lines.append(f"{u['id']}  {u['manufacturer']} {u['product']}".rstrip())

    lines.append(_section("Hints"))
    for h in info["hints"]:
        lines.append(f"[{h['level']}] {h['text']}")

    lines.append(_section("Sensors"))
    lines.append(json.dumps(engine.sensor_readings(), sort_keys=True))
    return "\n".join(lines) + "\n"
