#!/bin/bash
# Checks GitHub for new commits on `dev` and updates the cube when there are some.
# Run by kuv-update.timer (as user luna). DISCORD_WEBHOOK_URL comes from /etc/kuv/discord.env.

REPO_DIR="/home/luna/kuv/kuv-cube"
VENV_DIR="/home/luna/kuv/venv"

cd "$REPO_DIR" || exit 1

# Fetch repository
git fetch origin dev

# Compare local with remote latest commits
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse dev@{u})

# -----------------------------------
#  They are different, run an update
# -----------------------------------
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "New changes detected"
    echo "Updating Kuv script..."

    # Alert discord about the update
    curl -H "Content-Type: application/json" -X POST -d '{"embeds": [{"title": "🍒 Rasbperry Pi", "description": "The `Pi` script code updated 🌟", "color": 16516072 }]}' "$DISCORD_WEBHOOK_URL"

    # Pull changes
    git pull origin dev

    # Install new dependences, just in case they changed
    "$VENV_DIR/bin/python" -m pip install -r requirements.txt

    # Restart the cube script (sudoers rule in /etc/sudoers.d/kuv allows exactly this)
    sudo systemctl restart kuv-cube.service

    echo "Kuv script updated successfully :3"

# -----------------------------------
#   They are the same, do nothing
# -----------------------------------
else
    echo "Kuv script is up to date :3"
fi
