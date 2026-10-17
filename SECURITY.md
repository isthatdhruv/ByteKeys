# Security policy

`bytekeysd` runs as root and accepts requests from local users, so security reports are taken seriously.

Please report vulnerabilities privately through GitHub's **Report a vulnerability** button (Security tab)
rather than in public issues. You will get an answer within a few days.

What the service does to stay safe:

- Requests are authorized per call with `SO_PEERCRED`: changes are only accepted from root, the
  `bytekeys` group and users with an active local session.
- All values are validated; hardware paths come only from the service's own discovery.
- Input devices are read only for activity timestamps and to compare presses with the one configured
  launch key; key codes are never stored or logged. Detecting the launch key accepts only an allowlist
  of special keys (never letters, digits or modifiers).
- Fan curves are validated (rising temperatures, never-falling speeds, minimum speeds when hot) and only
  firmware-run curves are used, so the fans can never be left stopped by ByteKeys.
- The systemd unit enables sandboxing (NoNewPrivileges, ProtectSystem, ProtectHome, PrivateTmp, ...).
