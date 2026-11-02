# kuv-cube

Python script that drives the LED matrix of the Kuv cube on a Raspberry Pi.

## Repository

| Path | What it is |
|---|---|
| `main.py` | Entry point, run by `kuv-cube.service` |
| `src/` | `hardware.py`, `matrix.py`, `network.py` |
| `scripts/update.sh` | Auto-update script run by `kuv-update.timer` |
| `requirements.txt` | Python deps (`rgbmatrix` is built from `/home/luna/rpi-rgb-led-matrix`) |

## Raspberry Pi setup

Everything kuv-related on the Pi, and where it lives:

```
/home/luna/kuv/
├── kuv-cube/                 # this repo, cloned from TheMagicDragonMX/kuv-cube (branch dev)
└── venv/                     # Python venv, kept outside the repo
/home/luna/rpi-rgb-led-matrix/   # LED matrix library (installed into the venv by requirements.txt)
/etc/kuv/discord.env             # Discord webhook URLs (root:root, mode 600, NOT in git)
/etc/sudoers.d/kuv               # lets luna restart kuv-cube.service without a password
/etc/systemd/system/
├── kuv-cube.service             # runs main.py
├── kuv-update.service           # runs scripts/update.sh
├── kuv-update.timer             # triggers kuv-update.service 1 min after boot, then every minute
├── kuv-discord-boot.service     # Discord alert when the Pi boots
└── kuv-discord-shutdown.service # Discord alert on shutdown / reboot / halt
```

### How it fits together

- `kuv-update.timer` runs `scripts/update.sh` every minute. If `origin/dev` has new commits it
  posts to Discord, pulls, reinstalls `requirements.txt` into `/home/luna/kuv/venv`, and restarts
  `kuv-cube.service`.
- Because the update script lives in this repo, it updates itself on the next pull.
- Paths are hardcoded in `kuv-cube.service` and `scripts/update.sh` (`REPO_DIR`, `VENV_DIR`).
  If you move folders, edit both.

### Discord webhooks

`/etc/kuv/discord.env` holds the secrets, read by systemd through `EnvironmentFile=`:

```
DISCORD_WEBHOOK_URL=...            # boot + update messages
DISCORD_WEBHOOK_SHUTDOWN_URL=...   # shutdown message
```

Never commit these. To rotate: edit the file, nothing else needs to change (units read it on each run).

### Useful commands

```bash
systemctl status kuv-cube.service kuv-update.timer
journalctl -u kuv-cube.service -e
journalctl -u kuv-update.service -e
sudo systemctl restart kuv-cube.service
sudo systemctl daemon-reload      # after editing any unit file
```

### Rebuilding the venv

```bash
python3 -m venv /home/luna/kuv/venv
/home/luna/kuv/venv/bin/pip install -r /home/luna/kuv/kuv-cube/requirements.txt
```
