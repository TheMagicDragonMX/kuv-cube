#!/bin/bash
# Checks GitHub for new commits on `dev` and updates the cube when there are some.
# Run by kuv-update.timer (as user luna). DISCORD_WEBHOOK_URL comes from /etc/kuv/kuv.env.
# Only the programs whose code changed are restarted (see deploy/kuv-sudoers for what luna may do).

REPO_DIR="/home/luna/kuv/kuv-cube"
VENV_DIR="/home/luna/kuv/venv"

# Everything lives in a function and the script exits right after calling it: bash reads a script
# while running it, so a `git pull` that rewrites this very file could otherwise run garbage.
main() {
    set -euo pipefail

    cd "$REPO_DIR"

    # Fetch repository (the timeout keeps a dead connection from holding the timer)
    timeout 60 git fetch origin dev

    # Compare local with remote latest commits
    local local_commit remote_commit
    local_commit=$(git rev-parse HEAD)
    remote_commit=$(git rev-parse 'dev@{u}')

    # -----------------------------------
    #   They are the same, do nothing
    # -----------------------------------
    if [ "$local_commit" = "$remote_commit" ]; then
        echo "Kuv script is up to date :3"
        return 0
    fi

    # -----------------------------------
    #  They are different, run an update
    # -----------------------------------
    echo "New changes detected"
    echo "Updating Kuv script..."

    local changed
    changed=$(git diff --name-only "$local_commit" "$remote_commit")

    # Alert discord about the update (a failed alert must not stop the update)
    curl -sS -m 10 -H "Content-Type: application/json" -X POST \
        -d '{"embeds": [{"title": "🍒 Rasbperry Pi", "description": "The `Pi` script code updated 🌟", "color": 16516072 }]}' \
        "${DISCORD_WEBHOOK_URL:-}" || echo "Could not alert Discord"

    # Pull changes. Fast-forward only: if the cube's copy diverged, fail loudly instead of merging.
    git merge --ff-only "$remote_commit"

    # Install new dependences only when they changed
    if grep -q '^requirements.txt$' <<< "$changed"; then
        timeout 300 "$VENV_DIR/bin/python" -m pip install -r requirements.txt
    fi

    # Restart what changed. programs/common is used by all three programs.
    local everything=false
    grep -qE '^(requirements.txt|deploy/)' <<< "$changed" && everything=true

    if grep -q '^deploy/' <<< "$changed"; then
        sudo systemctl daemon-reload
    fi

    if $everything || grep -qE '^programs/(matrix|common)/' <<< "$changed"; then
        sudo systemctl restart kuv-matrix.service
    fi

    # Only restarts setup if it is running; it is when the cube is offline.
    if $everything || grep -qE '^programs/(setup|common)/' <<< "$changed"; then
        sudo systemctl try-restart kuv-setup.service
    fi

    # Restarting the cube program stops setup, which would cut a page off in the middle of the
    # WiFi setup. If setup is running, it hands over to the new code by itself.
    if $everything || grep -qE '^programs/(main|common)/' <<< "$changed"; then
        if ! systemctl is-active --quiet kuv-setup.service; then
            sudo systemctl restart kuv-cube.service
        fi
    fi

    echo "Kuv script updated successfully :3"
}

main "$@"
exit $?
