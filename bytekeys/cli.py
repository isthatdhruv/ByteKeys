"""bytekeys: command line control of keyboard lighting."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import APP_NAME, __version__, ipc
from .ipc import ServiceError

EPILOG = """examples:
  bytekeys status                       show keyboards and their lighting
  bytekeys brightness 60                set brightness to 60 %
  bytekeys brightness up                one step brighter
  bytekeys color "#ff8800"              whole keyboard orange
  bytekeys color red green blue white   one color per zone
  bytekeys mode breathing               breathing (uses the keyboard's own mode if it has one)
  bytekeys mode cycle                   cycle through all colors
  bytekeys effect wave --speed 70       rainbow wave
  bytekeys profile apply Night          switch profile
  bytekeys flash --color red --count 3  blink (e.g. from a notification script)
"""


def _client(args):
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR,
                        format="%(levelname)s %(name)s: %(message)s")
    return ipc.connect(path=args.socket, local=args.local, demo=args.demo, restore=False)


def _print_json(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _bar(pct: int, width: int = 20) -> str:
    filled = int(round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def _describe_state(dev: dict) -> str:
    st = dev["effective"]
    if not st["on"] or st["brightness"] == 0:
        light = "off"
    elif dev.get("levels"):
        idx = max(1, int(st["brightness"] / 100 * dev["brightness_max"] + 0.5))
        light = f"{dev['levels'][min(idx, len(dev['levels']) - 1)]} ({st['brightness']}%)"
    else:
        light = f"{st['brightness']}%"
    parts = [f"brightness {light}"]
    if dev["color_mode"] != "none":
        if st.get("zones"):
            parts.append("zones " + " ".join(st["zones"][:8]) + (" ..." if len(st["zones"]) > 8 else ""))
        else:
            parts.append(f"color {st['color']}")
    if st["effect"] != "static":
        parts.append(f"effect {st['effect']}")
    return ", ".join(parts)


def cmd_status(client, args) -> int:
    hello = client.call("hello")
    system = client.call("system")
    devices = client.call("devices")
    if args.json:
        _print_json({"service": hello, "system": system, "devices": devices})
        return 0
    mode = "service" if hello["mode"] == "service" else "portable (no service running)"
    print(f"{APP_NAME} {hello['version']} - {system['model']}")
    print(f"Mode: {mode}")
    if not devices:
        print("\nNo controllable keyboard lighting found.")
    for dev in devices:
        kind = {"none": "single color", "single": "RGB", "zones": f"{len(dev['zones'])}-zone RGB",
                "perkey": f"per-key RGB ({len(dev['zones'])} keys)"}[dev["color_mode"]]
        print(f"\n● {dev['name']}  [{dev['id']}]")
        print(f"  {kind} via {dev['backend']}")
        print(f"  {_describe_state(dev)}")
        st = dev["effective"]
        if st["on"]:
            print(f"  {_bar(st['brightness'])}")
        if dev["rules_active"]:
            print(f"  rules active: {', '.join(dev['rules_active'])}")
        if dev.get("access"):
            print(f"  ! {dev['access']}")
        if dev.get("error"):
            print(f"  ! {dev['error']}")
    hints = [h for h in system.get("hints", []) if h["level"] != "info"]
    if hints:
        print()
        for h in hints:
            print(f"{'!' if h['level'] == 'warn' else '-'} {h['text']}")
    return 0


def cmd_list(client, args) -> int:
    devices = client.call("devices")
    if args.json:
        _print_json(devices)
        return 0
    for dev in devices:
        print(f"{dev['id']:40} {dev['name']}  ({dev['color_mode']}, {dev['backend']})")
    return 0


def _set(client, args, changes: dict) -> int:
    views = client.call("set", device=args.device, changes=changes)
    if args.json:
        _print_json(views)
    else:
        for v in views:
            print(f"{v['name']}: {_describe_state(v)}")
    return 0


def cmd_power(client, args) -> int:
    if args.command == "toggle":
        views = client.call("toggle", device=args.device)
        if not args.json:
            for v in views:
                print(f"{v['name']}: {_describe_state(v)}")
        else:
            _print_json(views)
        return 0
    return _set(client, args, {"on": args.command == "on"})


def cmd_brightness(client, args) -> int:
    value = args.value.lower()
    if value in ("up", "+"):
        views = client.call("nudge", device=args.device, step=1)
    elif value in ("down", "-"):
        views = client.call("nudge", device=args.device, step=-1)
    else:
        pct = int(value.rstrip("%"))
        return _set(client, args, {"on": pct > 0, **({"brightness": pct} if pct > 0 else {})})
    for v in views:
        print(f"{v['name']}: {_describe_state(v)}")
    return 0


def cmd_color(client, args) -> int:
    if args.zone is not None:
        return _set(client, args, {"zones": {str(args.zone): args.colors[0]}, "on": True})
    if len(args.colors) == 1:
        return _set(client, args, {"color": args.colors[0], "on": True})
    return _set(client, args, {"color": args.colors[0], "zones": args.colors, "on": True})


def _resolve_effect(dev: dict, name: str) -> str:
    ids = [e["id"] for e in dev["effects"]]
    for candidate in (name, f"hw:{name}", name.lower(), f"hw:{name.lower()}"):
        if candidate in ids:
            return candidate
    raise ServiceError("invalid", f"effect {name!r} is not available on {dev['name']}. "
                                  f"Choose from: {', '.join(ids)}")


def cmd_effect(client, args) -> int:
    devices = client.call("devices")
    targets = devices if args.device in (None, "all") else [d for d in devices if args.device in d["id"]]
    if not targets:
        raise ServiceError("not_found", f"no device matches {args.device!r}")
    params: dict = {}
    if args.speed is not None:
        params["speed"] = args.speed
    if args.direction:
        params["direction"] = args.direction
    for dev in targets:
        changes: dict = {"effect": _resolve_effect(dev, args.name), "on": True}
        if params:
            changes["params"] = params
        if args.color:
            changes["effect_colors"] = args.color
        views = client.call("set", device=dev["id"], changes=changes)
        for v in views:
            print(f"{v['name']}: {_describe_state(v)}")
    return 0


def cmd_mode(client, args) -> int:
    from . import modes

    devices = client.call("devices")
    targets = devices if args.device in (None, "all") else [d for d in devices if args.device in d["id"]]
    if not targets:
        raise ServiceError("not_found", f"no device matches {args.device!r}")
    changed = 0
    for dev in targets:
        effect_id = next((eid for mode, _t, eid in modes.quick_modes(dev) if mode == args.name), None)
        if effect_id is None:
            print(f"{dev['name']}: no {args.name} mode", file=sys.stderr)
            continue
        effect = next(e for e in dev["effects"] if e["id"] == effect_id)
        changes = modes.effect_changes(dev, effect)
        if args.speed is not None:
            changes["params"]["speed"] = args.speed
        for v in client.call("set", device=dev["id"], changes=changes):
            where = " (on the keyboard)" if effect["hardware"] else ""
            print(f"{v['name']}: {effect['name']}{where}")
        changed += 1
    return 0 if changed else 2


def cmd_effects(client, args) -> int:
    devices = client.call("devices")
    for dev in devices:
        if args.device and args.device not in dev["id"]:
            continue
        print(f"{dev['name']} [{dev['id']}]")
        for e in dev["effects"]:
            tag = "hardware" if e["hardware"] else "software"
            params = ", ".join(p["id"] for p in e["params"])
            print(f"  {e['id']:24} {e['name']:18} {tag:9} {params}")
    return 0


def cmd_profile(client, args) -> int:
    if args.action == "list":
        profiles = client.call("profiles")
        if args.json:
            _print_json(profiles)
        for p in profiles if not args.json else []:
            print(p["name"])
        return 0
    if args.action == "save":
        client.call("profile_save", name=args.name)
        print(f"Saved profile {args.name!r}")
    elif args.action == "apply":
        client.call("profile_apply", name=args.name)
        print(f"Applied profile {args.name!r}")
    elif args.action == "delete":
        client.call("profile_delete", name=args.name)
        print(f"Deleted profile {args.name!r}")
    elif args.action == "rename":
        client.call("profile_rename", old=args.name, new=args.new)
        print(f"Renamed {args.name!r} to {args.new!r}")
    return 0


def cmd_rules(client, args) -> int:
    rules = client.call("rules")
    if args.action == "list":
        if args.json:
            _print_json(rules)
            return 0
        for r in rules:
            mark = "●" if r["enabled"] else "○"
            print(f"{mark} {r['id']:16} {r['name']}  [{r['trigger']['type']} -> {r['action']['type']}]")
        return 0
    if args.action in ("enable", "disable"):
        found = False
        for r in rules:
            if r["id"] == args.id:
                r["enabled"] = args.action == "enable"
                found = True
        if not found:
            raise ServiceError("not_found", f"no rule with id {args.id!r}")
        client.call("rules_set", rules=rules)
        print(f"Rule {args.id!r} {args.action}d")
        return 0
    if args.action == "export":
        _print_json(rules)
        return 0
    if args.action == "import":
        with open(args.id, encoding="utf-8") if args.id != "-" else sys.stdin as f:
            new_rules = json.load(f)
        client.call("rules_set", rules=new_rules)
        print(f"Imported {len(new_rules)} rules")
        return 0
    return 1


def cmd_feature(client, args) -> int:
    dev = client.call("device", device=args.device or "all")
    if not args.name:
        for f in dev["features"]:
            print(f"{f['id']:20} {f['name']:32} = {f['value']}")
        if not dev["features"]:
            print("This device has no extra settings.")
        return 0
    view = client.call("feature", device=dev["id"], feature=args.name, value=args.value)
    for f in view["features"]:
        if f["id"] == args.name:
            print(f"{f['name']} = {f['value']}")
    return 0


def cmd_flash(client, args) -> int:
    client.call("flash", device=args.device, color=args.color, count=args.count, period=args.period)
    return 0


def cmd_sensors(client, args) -> int:
    data = client.call("sensors")
    if args.json:
        _print_json(data)
        return 0
    r = data["readings"]
    rows = [
        ("Power", "plugged in" if r["ac_online"] else "battery" if r["ac_online"] is False else "unknown"),
        ("Battery", f"{r['battery']}%" if r["battery"] is not None else "-"),
        ("CPU temperature", f"{r['temperature']:.0f} °C" if r["temperature"] is not None else "-"),
        ("CPU load", f"{r['cpu']:.0f}%" if r["cpu"] is not None else "(needs two samples)"),
        ("Caps Lock", "on" if r["capslock"] else "off" if r["capslock"] is not None else "-"),
        ("Idle", f"{r['idle']:.0f} s" if r["idle"] is not None else "unavailable"),
        ("Ambient light", f"{r['lux']:.0f} lux" if r["lux"] is not None else "-"),
    ]
    for k, v in rows:
        print(f"{k:16} {v}")
    return 0


def cmd_settings(client, args) -> int:
    if args.pairs:
        changes = {}
        for pair in args.pairs:
            key, _, value = pair.partition("=")
            changes[key] = value
        settings = client.call("settings_set", changes=changes)
    else:
        settings = client.call("settings")
    if args.json:
        _print_json(settings)
    else:
        for k, v in sorted(settings.items()):
            print(f"{k:24} {v}")
    return 0


def cmd_report(client, args) -> int:
    print(client.call("report"), end="")
    return 0


def cmd_rescan(client, args) -> int:
    devices = client.call("rescan")
    print(f"Found {len(devices)} device(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="bytekeys", description=f"{APP_NAME}: keyboard lighting control for Linux laptops",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    ap.add_argument("--json", action="store_true", help="machine readable output")
    ap.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    ap.add_argument("--local", action="store_true", help="do not use the service (portable mode)")
    ap.add_argument("--demo", action="store_true", help="add simulated keyboards (portable mode)")
    ap.add_argument("--socket", default=ipc.SOCKET_PATH, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command", metavar="COMMAND")

    def add(name, fn, help_text, device=True):
        p = sub.add_parser(name, help=help_text)
        if device:
            p.add_argument("-d", "--device", help="device id (default: all)")
        p.set_defaults(func=fn)
        return p

    add("status", cmd_status, "show keyboards and lighting (default)")
    add("list", cmd_list, "list devices", device=False)
    for name in ("on", "off", "toggle"):
        add(name, cmd_power, f"turn the lights {name}" if name != "toggle" else "toggle the lights")
    p = add("brightness", cmd_brightness, "set brightness: 0-100, up or down")
    p.add_argument("value")
    p = add("color", cmd_color, "set color(s): #rrggbb, r,g,b or a name; one per zone allowed")
    p.add_argument("colors", nargs="+")
    p.add_argument("--zone", type=int, help="only change this zone (index)")
    p = add("effect", cmd_effect, "play an effect")
    p.add_argument("name")
    p.add_argument("--speed", type=int)
    p.add_argument("--direction", choices=["left", "right"])
    p.add_argument("--color", action="append", help="effect color (repeatable)")
    p = add("mode", cmd_mode, "switch mode: static, breathing, cycle, wave or strobe")
    p.add_argument("name", choices=["static", "breathing", "cycle", "wave", "strobe"])
    p.add_argument("--speed", help="speed (a number, or 0/1/2 on keyboards with three speeds)")
    add("effects", cmd_effects, "list available effects")
    p = add("profile", cmd_profile, "manage profiles", device=False)
    p.add_argument("action", choices=["list", "save", "apply", "delete", "rename"])
    p.add_argument("name", nargs="?")
    p.add_argument("new", nargs="?")
    p = add("rules", cmd_rules, "list, enable, disable, export or import automation rules", device=False)
    p.add_argument("action", choices=["list", "enable", "disable", "export", "import"], nargs="?",
                   default="list")
    p.add_argument("id", nargs="?", help="rule id (or a file for import)")
    p = add("feature", cmd_feature, "show or change device specific settings")
    p.add_argument("name", nargs="?")
    p.add_argument("value", nargs="?")
    p = add("flash", cmd_flash, "blink the keyboard")
    p.add_argument("--color", default="#ffffff")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--period", type=float, default=0.5)
    add("sensors", cmd_sensors, "show sensor readings used by rules", device=False)
    p = add("settings", cmd_settings, "show or change settings (key=value)", device=False)
    p.add_argument("pairs", nargs="*")
    add("report", cmd_report, "print a diagnostic report", device=False)
    add("rescan", cmd_rescan, "look for keyboards again", device=False)
    sub.add_parser("gui", help="open the control panel")
    p = sub.add_parser("service", help="install, remove or check the system service")
    p.add_argument("action", choices=["install", "uninstall", "status"])
    sub.add_parser("daemon", help="run the system service in the foreground", add_help=False)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["daemon"]:
        from .daemon import main as daemon_main
        return daemon_main(argv[1:])
    if argv[:1] == ["gui"]:
        from .gui.app import main as gui_main
        return gui_main(argv[1:])
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "service":
        from .service import main as service_main
        return service_main([args.action])
    if not args.command:
        args.command, args.func, args.device = "status", cmd_status, None
    if args.command == "profile" and args.action != "list" and not args.name:
        parser.error("profile name required")
    try:
        client = _client(args)
    except Exception as e:
        print(f"bytekeys: cannot start: {e}", file=sys.stderr)
        return 1
    try:
        return args.func(client, args)
    except ServiceError as e:
        print(f"bytekeys: {e.message}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    finally:
        if getattr(client, "mode", "") == "portable":
            # Give the render thread a moment to push the last change.
            import time
            time.sleep(0.3)
        client.close()


if __name__ == "__main__":
    sys.exit(main())
