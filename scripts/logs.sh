#!/bin/bash
# Streams the Kuv cube's logs to THIS terminal. Run it on your laptop, not on the Pi: it connects to
# the Pi with ssh (the same `ssh pi` you already use) and shows what the programs write down.
#
#   ./scripts/logs.sh                 follow all three programs, starting with the last 50 lines
#   ./scripts/logs.sh setup           only the setup program (matrix | setup | main)
#   ./scripts/logs.sh setup bluetooth several at once; also: bluetooth, wifi (NetworkManager)
#   ./scripts/logs.sh -n 200          start with the last 200 lines
#   ./scripts/logs.sh -b              start from the last boot instead
#   ./scripts/logs.sh -s              print what is there and stop, without following
#   ./scripts/logs.sh -p              no colors
#
# Another Pi or another ssh name: KUV_HOST=other-name ./scripts/logs.sh
# Press Ctrl+C to stop.

HOST="${KUV_HOST:-pi}"
LINES_BACK=50
SINCE_BOOT=0
FOLLOW=1
COLOR=1
UNITS=()

usage() {
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
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
REMOTE="journalctl --no-hostname --output=short"

for unit in "${UNITS[@]}"; do
    REMOTE+=" -u $unit"
done

if [ "$SINCE_BOOT" -eq 1 ]; then
    REMOTE+=" -b"
else
    REMOTE+=" -n $LINES_BACK"
fi

SSH=(ssh -o ConnectTimeout=8 -o ServerAliveInterval=15 -o LogLevel=ERROR)

if [ "$FOLLOW" -eq 1 ]; then
    REMOTE+=" -f"
    SSH+=(-t)   # lets Ctrl+C stop the command on the Pi too
else
    REMOTE+=" --no-pager"
fi

# Colors: one per program, red for warnings and errors.
paint() {
    if [ "$COLOR" -eq 1 ] && [ -t 1 ]; then
        local esc=$'\033'
        sed -u -E \
            -e "s/\r$//" \
            -e "s/(kuv-matrix)(\[[0-9]+\])/${esc}[36m\1\2${esc}[0m/" \
            -e "s/(kuv-setup)(\[[0-9]+\])/${esc}[35m\1\2${esc}[0m/" \
            -e "s/(kuv-main)(\[[0-9]+\])/${esc}[32m\1\2${esc}[0m/" \
            -e "s/(WARNING .*)$/${esc}[33m\1${esc}[0m/" \
            -e "s/((ERROR|CRITICAL) .*)$/${esc}[31m\1${esc}[0m/"
    else
        sed -u -e "s/\r$//"
    fi
}

echo "Connecting to $HOST... (Ctrl+C to stop)" >&2

"${SSH[@]}" "$HOST" "$REMOTE" | paint
STATUS=${PIPESTATUS[0]}

# 255 is ssh itself failing (no network, wrong name); a followed log only ends on Ctrl+C.
if [ "$STATUS" -eq 255 ]; then
    echo "Could not reach '$HOST'. Is the Pi on the same network, and does 'ssh $HOST' work?" >&2
fi

exit "$STATUS"
