# Contributing to ByteKeys

Thanks for helping! The most valuable contributions are:

1. **Hardware reports.** Run `bytekeys report` (or System → Copy report) and open a
   *Device support* issue, especially for keyboards marked *Experimental*.
2. **Drivers** for keyboards that are not supported yet. See [docs/ADDING_DEVICES.md](docs/ADDING_DEVICES.md).
3. Bug fixes, translations of hints and docs, UI polish.

## Development setup

```bash
make test        # python3 -m unittest; no hardware needed
make demo        # control center with simulated keyboards and fans (needs PyQt6 or PySide6)
make cli         # bytekeys status from the source tree
```

Useful environment variables:

- `BYTEKEYS_FSROOT=/dir` runs everything against a fake `/sys` tree.
- `BYTEKEYS_SOCKET=/tmp/x.sock` lets you run a development service: `python3 -m bytekeys daemon --demo`.
- `BYTEKEYS_QT=pyqt6|pyside6` picks the Qt binding.

## Guidelines

- The service, engine and CLI must keep working with the Python standard library only.
- Validate everything that comes from clients; never build file paths from client input.
- Hardware safety first: no flash writes in animations, no undocumented commands, rate limits for slow
  controllers.
- Add tests (fake sysfs trees, `RecordingTransport` for HID byte checks).
- Keep the UI consistent: cards, settings rows, the theme tokens in `bytekeys/gui/theme.py`.

By contributing you agree that your work is released under the GPL-3.0-or-later license.
