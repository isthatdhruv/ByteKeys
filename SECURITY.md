# Security policy

`bytekeysd` runs as root and accepts requests from local users, so security reports are taken seriously.

Please report vulnerabilities privately through GitHub's **Report a vulnerability** button (Security tab)
rather than in public issues. You will get an answer within a few days.

What the service does to stay safe:

- Requests are authorized per call with `SO_PEERCRED`: changes are only accepted from root, the
  `bytekeys` group and users with an active local session.
- All values are validated; hardware paths come only from the service's own discovery.
- Input devices are read only for activity timestamps; key codes are never stored or logged.
- The systemd unit enables sandboxing (NoNewPrivileges, ProtectSystem, ProtectHome, PrivateTmp, ...).
