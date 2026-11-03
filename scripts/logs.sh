#!/bin/bash
# Streams the Kuv cube's logs to THIS terminal. Run it on your laptop, not on the Pi: it connects to
# the Pi with ssh (the same `ssh pi` you already use) and shows what the programs write down, one
# tidy line per event (needs python3 here).
#
#   ./scripts/logs.sh                 follow all three programs, starting with the last 50 lines
#   ./scripts/logs.sh setup           only the setup program (matrix | setup | main)
#   ./scripts/logs.sh setup bluetooth several at once; also: bluetooth, wifi (NetworkManager)
#   ./scripts/logs.sh -n 200          start with the last 200 lines
#   ./scripts/logs.sh -b              start from the last boot instead
#   ./scripts/logs.sh -s              print what is there and stop, without following
#   ./scripts/logs.sh -p              no colors
#   ./scripts/logs.sh -d              debug: show what ssh is doing, if it seems stuck
#
# Another Pi or another ssh name: KUV_HOST=other-name ./scripts/logs.sh
# Press Ctrl+C to stop.

HOST="${KUV_HOST:-pi}"
LINES_BACK=50
SINCE_BOOT=0
FOLLOW=1
COLOR=1
DEBUG=0
UNITS=()

usage() {
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        matrix)    UNITS+=(kuv-matrix.service) ;;
        setup)     UNITS+=(kuv-setup.service) ;;
        main)      UNITS+=(kuv-cube.service) ;;
        bluetooth) UNITS+=(bluetooth.service) ;;
        wifi)      UNITS+=(NetworkManager.service) ;;
        -n)        shift; LINES_BACK="$1" ;;
        -b)        SINCE_BOOT=1 ;;
        -s)        FOLLOW=0 ;;
        -p)        COLOR=0 ;;
        -d)        DEBUG=1 ;;
        -h|--help) usage 0 ;;
        *)         echo "Unknown option: $1" >&2; usage 1 ;;
    esac

    shift
done

if [ ${#UNITS[@]} -eq 0 ]; then
    UNITS=(kuv-matrix.service kuv-setup.service kuv-cube.service)
fi

if ! [[ "$LINES_BACK" =~ ^[0-9]+$ ]]; then
    echo "-n needs a number" >&2
    exit 1
fi

# Build the journalctl command that runs on the Pi.
# The first line tells the formatter that the connection works, even before any log arrives.
REMOTE="echo '{\"CONNECTED\": true}'; journalctl --output=json"

for unit in "${UNITS[@]}"; do
    REMOTE+=" -u $unit"
done

if [ "$SINCE_BOOT" -eq 1 ]; then
    REMOTE+=" -b"
else
    REMOTE+=" -n $LINES_BACK"
fi

SSH=(ssh -o ConnectTimeout=8 -o ServerAliveInterval=15)

if [ "$DEBUG" -eq 1 ]; then
    SSH+=(-v)
else
    SSH+=(-o LogLevel=ERROR)
fi

if [ "$FOLLOW" -eq 1 ]; then
    REMOTE+=" -f"
    SSH+=(-t)   # lets Ctrl+C stop the command on the Pi too
else
    REMOTE+=" --no-pager"
fi

# While following, ssh puts this terminal in "raw" mode (so Ctrl+C reaches the Pi), where a new line
# moves down without going back to the left edge. Ending every line with a carriage return keeps the
# lines from stepping to the right.
FORMAT=("$(dirname "$0")/format_logs.py")

if [ "$FOLLOW" -eq 1 ] && [ -t 0 ]; then
    FORMAT+=(--cr)
fi

if [ "$COLOR" -eq 0 ] || ! [ -t 1 ]; then
    FORMAT+=(--no-color)
fi

echo "Connecting to $HOST... (Ctrl+C to stop)" >&2

"${SSH[@]}" "$HOST" "$REMOTE" | python3 "${FORMAT[@]}"
STATUS=${PIPESTATUS[0]}

# 255 is ssh itself failing (no network, wrong name); a followed log only ends on Ctrl+C.
if [ "$STATUS" -eq 255 ]; then
    echo "Could not reach '$HOST'. Is the Pi on the same network, and does 'ssh $HOST' work?" >&2
fi

exit "$STATUS"
