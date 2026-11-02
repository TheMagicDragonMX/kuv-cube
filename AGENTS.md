# Kü-V cube (Raspberry Pi) - Project Context for AI Coding Agents

This repo is the software that runs on the cube's Raspberry Pi 4: it drives the LED matrices and, before that, gets the cube onto the user's WiFi. The web app lives in `kuv-client` and the REST API in `kuv-api`; their own `AGENTS.md` / docs describe the whole Kü-V system.

## 1. What is here

| Path | What it is |
| --- | --- |
| `setup/` | Gets the cube onto WiFi over Bluetooth (`python -m setup`). Everything below is inside it |
| `setup/protocol.py` | Protocol constants and types. Mirror of `kuv-client/src/app/setup/protocol.ts` |
| `setup/framing.py` | Cuts messages into Bluetooth-sized chunks and joins them back |
| `setup/network.py` | WiFi through NetworkManager (`nmcli`) |
| `setup/dispatcher.py` | Answers requests: PIN, lockout, routing each operation |
| `setup/bridge.py` | Per-page state, chunks in and out, status events. No BlueZ in it |
| `setup/gatt.py` | The only file that talks to BlueZ |
| `setup/identity.py`, `setup/display.py` | Name / PIN / version, and the PIN on the matrix |
| `main/` | Everything the cube does once online (`python -m main`): the matrix and the web app |
| `deploy/` | systemd units. Setup runs only when offline at boot, main only when online |
| `tests/` | `python3 -m unittest` |

Keep the two programs apart: `setup/` must not grow code for the web app, and `main/` must not grow onboarding code. `setup/` may import `main.matrix` (the shared panel config), nothing else from `main/`.

The setup contract is described in `kuv-client/src/app/setup/README.md`. When the protocol changes, change `protocol.ts` and `setup/protocol.py` together and bump `PROTOCOL_VERSION`.

The two programs are separate processes and never run at the same time (both need the LED matrix), so each unit checks at boot whether the cube is online.

## 2. Constraints

- The Pi's CPU temperature must stay below 80 °C (target < 60 °C). Keep code non-blocking so the matrix does not drop frames.
- Setup code is `asyncio`: never block the event loop (no `time.sleep`, no blocking subprocess calls).
- Messages over Bluetooth are JSON lines, see the setup README.

## 3. Coding Style Rules

> **Note:** This list is open-ended and mirrors the one in `kuv-client/AGENTS.md`, adapted to Python. More rules will be added over time. When the user says something like *"hey new rule, we need to..."*, treat it as a new coding style rule: add it to this section and apply it to all new and edited code from then on.

### Comments and documentation
- Every declaration needs a docstring saying what it is for: modules, classes, functions, methods, properties, variables, constants defined before any logic, type aliases and each key of a `TypedDict`.
- Docstrings are always spread over multiple lines. A docstring for one line of text takes three lines: the opening `"""`, the text, and the closing `"""`.
- Functions, methods, classes and modules carry the docstring as their first statement. For variables, constants, instance attributes and `TypedDict` keys, the docstring goes on the lines right below the declaration.
- Always leave a blank line before a declaration that has a docstring, so it never sits right under the code above it.
- Use `#` comments only inside function bodies, to explain a step. Put a blank line before them as well.

```python
# Good
a = 1

b = 2
"""
What b is.
"""

# Bad
a = 1
b = 2  # What b is.
```

### Blocks of code
- In chained blocks (`if` / `elif` / `else`, `try` / `except` / `else` / `finally`, `for` / `else`), leave a blank line before each following block (`elif`, `else`, `except`, `finally`).
- Single-statement bodies go on their own line below the header, never on the same line (`if x: y` is not allowed).

```python
# Good
if condition:
    print("hey")

else:
    print("not hey")

# Bad
if condition:
    print("hey")
else:
    print("not hey")
```

### Others
- Use type aliases and `TypedDict` for the shape of data. Write aliases as `Name: TypeAlias = ...`, not the `type` statement, because the Pi may run Python 3.11. Do not use `Protocol`, `ABC` or `dataclass` to describe plain data shapes. The only exception is augmenting or implementing an existing library class that requires them.
- Python keeps its own formatting conventions where the TypeScript rules do not apply: 4 spaces for indentation, double quotes, `snake_case` names, `UPPER_CASE` constants.
