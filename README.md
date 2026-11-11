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

## Where we are

*Checked on the Pi on 2026-11-03.* The three programs run as intended: `kuv-matrix` and `kuv-cube` are active, `kuv-setup` is correctly skipped because the cube is online, the update timer is healthy, and the CPU is at about 53 °C. The cube runs the live-link code (`50ddd06`), but the **link is off** because `/etc/kuv/kuv.env` does not exist on the Pi yet (only the old `/etc/kuv/discord.env`), so main logs "running without the live link".

Done in the repo, **not yet on the Pi**: the single config file (`deploy/kuv.env.example`, see [Configuration](#configuration)) and the units that read it. The Pi gets them when this is pushed to `dev` and the update timer pulls it.

**Next steps, in order** (do the first two before pushing, or the Discord alerts stop):

1. On the Pi, create the config file and keep the webhooks:
   ```bash
   sudo cp /home/luna/kuv/kuv-cube/deploy/kuv.env.example /etc/kuv/kuv.env   # after the push; or copy it by hand
   sudo chmod 600 /etc/kuv/kuv.env
   sudo sh -c 'cat /etc/kuv/discord.env >> /etc/kuv/kuv.env'                  # then delete the placeholder DISCORD_* lines
   ```
2. In `/etc/kuv/kuv.env` set `KUV_SERVER_URL` to the address the Pi reaches the API at (the LAN IP of the computer running kuv-api, port 5038) and `KUV_CUBE_SECRET` to a new random secret (`openssl rand -hex 32`).
3. Run kuv-api with the same secret as `Cubes__Secret`, listening on the LAN and not only on localhost (`dotnet run --urls http://0.0.0.0:5038`).
4. Push to `dev`, then `sudo systemctl daemon-reload && sudo systemctl restart kuv-cube.service`.
5. Check: `journalctl -u kuv-cube -e` must say "Linked to the server as cube …". Then open the web app at `/cube-chat` (log in first), type the cube id (`cat /etc/machine-id` on the Pi, or `KUV_CUBE_ID`) and send a message: the cube answers with a mock reply.

**After that**, the live link is ready to carry real commands: the next feature is a `play_program` command (server sends a program JSON, the handler validates it and calls `CubePlayer.play`), then the cube sending user inputs to the server. Known gaps of the link: the client's token is only checked when the socket opens; the web app's server address (`ws://localhost:5038`) and the production origin checks are not configurable yet; `PANEL_SLOTS` in `programs/main/cube/view/panel_layout.py` is still a placeholder until the real panel wiring is set.

## Repository

| Path | What it is |
|---|---|
| `programs/matrix/` | Owns the LED panels, run with `python -m programs.matrix` by `kuv-matrix.service` |
| `programs/setup/` | Bluetooth + WiFi onboarding, run with `python -m programs.setup` by `kuv-setup.service`. See below |
| `programs/main/` | Everything the cube does once online, run with `python -m programs.main` by `kuv-cube.service`. Its library for running user programs is `programs/main/cube/`. See below |
| `programs/common/` | What the programs share: the client and message format for talking to the matrix program |
| `deploy/` | The systemd units for the programs above (copy to `/etc/systemd/system/`) |
| `tests/` | `python3 -m unittest` |
| `scripts/update.sh` | Auto-update script run by `kuv-update.timer` |
| `requirements.txt` | Python deps (`rgbmatrix` is built from `/home/luna/rpi-rgb-led-matrix`) |

## The cube library

`programs/main/cube/` runs the programs the users make in the web app. A program is the JSON that the editor of `kuv-client` produces; the library checks it, runs it over time and shows it on the panels. It is a layer-by-layer port of `kuv-client/src/app/cube/engine/` (same layers, same names in `snake_case`, same JSON), so a change in one is a change in the other. The map of the layers is in `programs/main/cube/__init__.py`.

```python
player = CubePlayer({"on_frame": lambda state: matrix.show(scene_of(state))})
player.play(program)      # program: the JSON as a dict; raises ProgramError (with the path of the problem) if invalid
```

The web app's `CubeView` (3D) has no counterpart; its place is `view/panel_layout.py`, which turns the pixel buffer into one 64×64 `image` item per lit face for the matrix program. **`PANEL_SLOTS` there is a placeholder**: set the slot (column, row of the 2×3 grid of panels) and the rotation of every face to how the panels are really wired.

Not ported: the example programs (`examples/` in the web app) and the 3D parts (`view/`, `component/`).

Trying it on the Pi, with the matrix program running (Ctrl+C to stop):

```bash
/home/luna/kuv/venv/bin/python -m programs.main program.json    # or `-` to read the program from the standard input
```

Without a file, `programs.main` still just paints the panels blue. Tests: `tests/test_cube_*.py`.

## The live link

When the server is configured, `programs.main` keeps a WebSocket open to `kuv-api` (`/ws/cube`) to receive commands and send events. It reconnects by itself (1 s doubling to 30 s), so the server may be down. Without the settings it runs as before, without the link.

Its settings are `KUV_SERVER_URL`, `KUV_CUBE_SECRET` and `KUV_CUBE_ID`, see [Configuration](#configuration).

The messages are in `programs/main/link/protocol.py` (mirror of `kuv-client/src/app/cube/link/protocol.ts` and `CubeMessage` in kuv-api). A command is a handler registered in `programs/main/link/commands.py`, which gets the payload and returns the events to send back. For now the only one is `message`, which answers with a mock `reply`. The cube id is what the user types in the web app's `/cube-chat` page. Tests: `tests/test_link.py`.

## Configuration

Every setting of the Pi lives in **one file**, `/etc/kuv/kuv.env` (root:root, mode 600, not in git because it holds secrets). Its template, with a comment on every setting, is [`deploy/kuv.env.example`](deploy/kuv.env.example). All the `kuv-*.service` units read it through `EnvironmentFile=-/etc/kuv/kuv.env`, so after editing it you only restart the unit that uses the setting.

```bash
sudo mkdir -p /etc/kuv && sudo cp deploy/kuv.env.example /etc/kuv/kuv.env
sudo chmod 600 /etc/kuv/kuv.env && sudo nano /etc/kuv/kuv.env
```

| Setting | What it is | Default | Used by |
| --- | --- | --- | --- |
| `KUV_SERVER_URL` | Address of kuv-api (`ws://host:5038`). No URL, no live link | none | `kuv-cube` |
| `KUV_CUBE_SECRET` | Secret the server expects from cubes (= `Cubes__Secret` in kuv-api) | none | `kuv-cube` |
| `KUV_CUBE_ID` | This cube's id, the one users type in the web app | `/etc/machine-id` | `kuv-cube` |
| `KUV_SETUP_PIN` | PIN for the Bluetooth setup; empty turns it off | generated, 4 digits | `kuv-setup` |
| `KUV_STATE_DIR` | Where the cube remembers the generated PIN (`setup-pin`) | `/var/lib/kuv` | `kuv-setup` |
| `KUV_SETUP_STAY` | `1` = setup keeps running after the cube is online | off | `kuv-setup` |
| `KUV_SETUP_PAIRING` | `1` = require Bluetooth pairing | off | `kuv-setup` |
| `KUV_FONT_DIR` | BDF fonts folder, used to draw the PIN | `/home/luna/rpi-rgb-led-matrix/fonts` | `kuv-matrix` |
| `DISCORD_WEBHOOK_URL` | Webhook for the boot and "code updated" messages | none | `kuv-discord-boot`, `kuv-update` |
| `DISCORD_WEBHOOK_SHUTDOWN_URL` | Webhook for the shutdown message | none | `kuv-discord-shutdown` |

Not in this file on purpose: `KUV_SETUP_HANDOFF` (wiring between two units, set in `kuv-setup.service`), the hardware tuning of the panels (rows, brightness, GPIO slowdown: constants in `programs/matrix/screen.py`), the folder paths (`REPO_DIR`, `VENV_DIR` in `scripts/update.sh` and the units) and the secrets of the API (those are `Jwt__Key`, `Cubes__Secret` and the database string, in `kuv-api`'s own environment).

To run a program by hand with the same settings: `sudo bash -c 'set -a; . /etc/kuv/kuv.env; set +a; exec /home/luna/kuv/venv/bin/python -m programs.main'`.

**Migrating from the old files:** the Discord webhooks used to be in `/etc/kuv/discord.env`. Move them into `kuv.env` (`sudo sh -c 'cat /etc/kuv/discord.env >> /etc/kuv/kuv.env'`) or the Discord alerts stop. Then `sudo cp deploy/*.service /etc/systemd/system/ && sudo systemctl daemon-reload`.

## The setup program

Contract with the web app: `kuv-client/src/app/cube/setup/README.md`.

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

The PIN (4 digits, unlimited attempts) is generated on first run and kept in `/var/lib/kuv/setup-pin`. Read it with `sudo cat /var/lib/kuv/setup-pin` if the matrix is unavailable. Its settings (`KUV_SETUP_PIN`, `KUV_STATE_DIR`, `KUV_SETUP_STAY`, `KUV_SETUP_PAIRING`) are in [Configuration](#configuration).

System packages the Pi needs: `bluez` and `network-manager` (both default on Raspberry Pi OS Bookworm). The setup service runs as root because of `nmcli` and Bluetooth; the matrix program runs as root because of the GPIO.

### Trying it

```bash
sudo /home/luna/kuv/venv/bin/python -m programs.setup      # from /home/luna/kuv/kuv-cube; Ctrl+C to stop
```

(the matrix program must be running for the PIN to appear on the panels), then open the setup page in Chrome, pick `Kuv-XXXX`, and enter the PIN. Run `python3 -m unittest` to test everything that does not need the radio.

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
/etc/kuv/kuv.env                 # ALL the settings and secrets (root:root, mode 600, NOT in git)
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
