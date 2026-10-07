# Deployment templates

Placeholder. Nothing here is usable yet.

- **S05** (interim service runner) adds the service units that keep the
  game server running until NetBBS can supervise door services itself:
  `rc.d/blacksite` for NetBSD and `systemd/blacksite.service`, plus the
  install steps for the venv and the install directory.
- **S31** (NetBBS integration and release) adds
  `netbbs-door-profile.json`, the importable native stdio door profile
  (venv interpreter, argv `-m blacksite.door`), and its door-service
  variant once the upstream request lands.

Until then, `docs/design/02-architecture.md` §3 and §8 describe how the
pieces are meant to run.
