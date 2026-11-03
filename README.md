# kuv-cube

Software for the Kuv cube on a Raspberry Pi. Three programs, started by systemd:

1. **`programs/matrix/`**: always running. It is the only one that touches the LED panels; the other two draw by asking it, so neither ever has to give the panels up.
2. **`programs/setup/`**: runs while the cube is offline. It advertises over Bluetooth, shows a PIN on the LED matrix, and lets the setup page of the web app choose a WiFi network.
3. **`programs/main/`**: runs once the cube is online. It draws on the LED matrix and talks to the web app.

```
boot ──► kuv-matrix.service (python -m programs.matrix)         always, owns the panels
      │
      ├─ offline ──► kuv-setup.service (python -m programs.setup) ── page connects the cube to WiFi ──┐
      └─ online ───► kuv-cube.service  (python -m programs.main)  ◄────────────────────────────────────┘
```

Programs draw by sending the matrix program a "scene" (see `programs/common/matrix_protocol.py`). The scene of the highest-priority program wins: the PIN (setup) is shown over whatever main draws, and main comes back by itself when the PIN is cleared or setup stops.

## Repository

| Path | What it is |
|---|---|
| `programs/matrix/` | Owns the LED panels, run with `python -m programs.matrix` by `kuv-matrix.service` |
| `programs/setup/` | Bluetooth + WiFi onboarding, run with `python -m programs.setup` by `kuv-setup.service`. See below |
| `programs/main/` | Everything the cube does once online, run with `python -m programs.main` by `kuv-cube.service` |
| `programs/common/` | What the programs share: the client and message format for talking to the matrix program |
| `scripts/logs.sh` | Run on your laptop: streams the Pi's logs to your terminal |
| `deploy/` | The systemd units for the programs above (copy to `/etc/systemd/system/`) |
| `tests/` | `python3 -m unittest` |
| `scripts/update.sh` | Auto-update script run by `kuv-update.timer` |
| `requirements.txt` | Python deps (`rgbmatrix` is built from `/home/luna/rpi-rgb-led-matrix`) |

## The setup program

Contract with the web app: `kuv-client/src/app/setup/README.md`.

| File | The one thing it does |
| --- | --- |
| `programs/setup/__main__.py` | Wires everything together and runs the service |
| `programs/setup/gatt.py` | The BlueZ side: GATT service, advertisement, disconnect watcher |
| `programs/setup/bridge.py` | Per-page state, chunks in and out, status events |
| `programs/setup/dispatcher.py` | PIN and one handler per operation |
| `programs/setup/network.py` | WiFi through NetworkManager (`nmcli`) |
| `programs/setup/framing.py` | Cuts messages into chunks and joins them back |
| `programs/setup/protocol.py` | UUIDs, error codes and types, mirror of `protocol.ts` |
| `programs/setup/identity.py` | The name (`Kuv-XXXX`), the PIN and the version |
| `programs/setup/display.py` | Shows the PIN on the matrix, through the matrix program |

The PIN (4 digits, unlimited attempts) is generated on first run and kept in `/var/lib/kuv/setup-pin`. Read it with `sudo cat /var/lib/kuv/setup-pin` if the matrix is unavailable. Environment variables (set in the unit): `KUV_SETUP_PIN` (override, empty turns it off), `KUV_STATE_DIR`, `KUV_SETUP_STAY=1` (do not hand over after setup), `KUV_SETUP_PAIRING=1` (require Bluetooth pairing, encrypts the link), `KUV_FONT_DIR` (read by the matrix program: where the BDF fonts are).

System packages the Pi needs: `bluez` and `network-manager` (both default on Raspberry Pi OS Bookworm). The setup service runs as root because of `nmcli` and Bluetooth; the matrix program runs as root because of the GPIO.

### Trying it

```bash
sudo /home/luna/kuv/venv/bin/python -m programs.setup      # from /home/luna/kuv/kuv-cube; Ctrl+C to stop
```

(the matrix program must be running for the PIN to appear on the panels), then open the setup page in Chrome, pick `Kuv-XXXX`, and enter the PIN. Run `python3 -m unittest` to test everything that does not need the radio.

### Watching the cube from your laptop

`scripts/logs.sh` streams what the programs write down to your laptop's terminal. Run it on the laptop, not on the Pi: it uses `ssh pi`, so the laptop and the Pi must be on the same network.

```bash
./scripts/logs.sh              # follow all three programs, starting with the last 50 lines
./scripts/logs.sh setup        # only one: matrix, setup or main (also: bluetooth, wifi)
./scripts/logs.sh -b           # start from the last boot
./scripts/logs.sh -s -n 200    # print the last 200 lines and stop
```

Each program has its own color. The Pi keeps the logs across reboots, so after a setup done while the Pi had no network you can read what happened (`./scripts/logs.sh -b setup`). Programs log what they do through `programs/common/logs.py`; never log secrets such as WiFi passwords or the PIN a page sent.

### Installing the units

```bash
sudo cp deploy/kuv-matrix.service deploy/kuv-setup.service deploy/kuv-cube.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kuv-matrix.service kuv-setup.service kuv-cube.service
```

All three are enabled. The matrix program always runs; at boot setup and cube each check `nmcli` and only the right one runs. The update script restarts only `kuv-cube.service` (all the sudoers rule allows), and starting `kuv-cube` also starts `kuv-matrix` if it is not running. A change to the matrix program itself therefore needs `sudo systemctl restart kuv-matrix.service` or a reboot. To automate that, allow `systemctl restart kuv-matrix.service` in `/etc/sudoers.d/kuv` and add it to `scripts/update.sh` before the `kuv-cube` restart.

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
├── kuv-matrix.service           # runs python -m programs.matrix, always; the only one that opens the panels
├── kuv-setup.service            # runs python -m programs.setup, only when the cube is offline at boot
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
