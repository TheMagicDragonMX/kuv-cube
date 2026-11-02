# kuv-cube

Software for the Kuv cube on a Raspberry Pi. It has two programs that take turns:

1. **`setup/`**: runs while the cube is offline. It advertises over Bluetooth, shows a PIN on the LED matrix, and lets the setup page of the web app choose a WiFi network.
2. **`main/`**: runs once the cube is online. It drives the LED matrix and talks to the web app.

```
boot ─┬─ offline ──► kuv-setup.service (python -m setup) ── page connects the cube to WiFi ──┐
      └─ online ───► kuv-cube.service  (python -m main)  ◄────────────────────────────────────┘
```

## Repository

| Path | What it is |
|---|---|
| `setup/` | Bluetooth + WiFi onboarding, run with `python -m setup` by `kuv-setup.service`. See below |
| `main/` | Everything the cube does once online, run with `python -m main` by `kuv-cube.service` |
| `deploy/` | The systemd units for the two programs above (copy to `/etc/systemd/system/`) |
| `tests/` | `python3 -m unittest` |
| `scripts/update.sh` | Auto-update script run by `kuv-update.timer` |
| `requirements.txt` | Python deps (`rgbmatrix` is built from `/home/luna/rpi-rgb-led-matrix`) |

## The setup program

Contract with the web app: `kuv-client/src/app/setup/README.md`.

| File | The one thing it does |
| --- | --- |
| `setup/__main__.py` | Wires everything together and runs the service |
| `setup/gatt.py` | The BlueZ side: GATT service, advertisement, disconnect watcher |
| `setup/bridge.py` | Per-page state, chunks in and out, status events |
| `setup/dispatcher.py` | PIN, lockout, and one handler per operation |
| `setup/network.py` | WiFi through NetworkManager (`nmcli`) |
| `setup/framing.py` | Cuts messages into chunks and joins them back |
| `setup/protocol.py` | UUIDs, error codes and types, mirror of `protocol.ts` |
| `setup/identity.py` | The name (`Kuv-XXXX`), the PIN and the version |
| `setup/display.py` | Shows the PIN on the matrix |

The PIN is generated on first run and kept in `/var/lib/kuv/setup-pin`. Read it with `sudo cat /var/lib/kuv/setup-pin` if the matrix is unavailable. Environment variables (set in the unit): `KUV_SETUP_PIN` (override, empty turns it off), `KUV_STATE_DIR`, `KUV_SETUP_STAY=1` (do not hand over after setup), `KUV_SETUP_PAIRING=1` (require Bluetooth pairing, encrypts the link), `KUV_FONT`, `KUV_SETUP_DISPLAY=0` (never touch the matrix, for testing next to a running cube).

System packages the Pi needs: `bluez` and `network-manager` (both default on Raspberry Pi OS Bookworm). The setup service runs as root because it uses the LED matrix and `nmcli`.

### Trying it

```bash
sudo /home/luna/kuv/venv/bin/python -m setup      # from /home/luna/kuv/kuv-cube; Ctrl+C to stop
```

then open the setup page in Chrome, pick `Kuv-XXXX`, and enter the PIN. Run `python3 -m unittest` to test everything that does not need the radio.

### Installing the units

```bash
sudo cp deploy/kuv-setup.service deploy/kuv-cube.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kuv-setup.service kuv-cube.service
```

Both are enabled; at boot each checks `nmcli` and only the right one runs. To let the update script also restart setup, add `kuv-setup.service` to the sudoers rule in `/etc/sudoers.d/kuv` and a matching `systemctl restart` line to `scripts/update.sh`.

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
├── kuv-setup.service            # runs python -m setup, only when the cube is offline at boot
├── kuv-cube.service             # runs python -m main, only when the cube is online
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
