#!/usr/bin/env bash
set -euo pipefail

# --- Configuration -------------------------------------------------------
# Reads DB_PATH from .env (same file config.py reads) so this script needs no separate configuration in the common case.
ENV_FILE="$(dirname "$0")/../.env"
DB_PATH="data/televault.db"
if [[ -f "$ENV_FILE" ]]; then
    found=$(grep -E '^DB_PATH=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '"'"'"'' || true)
    DB_PATH="${found:-$DB_PATH}"
fi

BACKUP_DIR="$(dirname "$0")/../backups"
STATE_FILE="$BACKUP_DIR/.last_backup_state"

# A new backup runs if EITHER threshold is crossed:
MIN_INTERVAL_HOURS=24
MIN_SIZE_DELTA_PERCENT=5

# Backups older than this are pruned after a successful run.
RETENTION_DAYS=30
# --------------------------------------------------------------------------

mkdir -p "$BACKUP_DIR"

if [[ ! -f "$DB_PATH" ]]; then
    echo "[backup] DB not found at $DB_PATH - nothing to back up yet." >&2
    exit 0
fi

current_size=$(stat -c%s "$DB_PATH" 2>/dev/null || stat -f%z "$DB_PATH")
now=$(date +%s)
should_run=false
reason=""

if [[ ! -f "$STATE_FILE" ]]; then
    should_run=true
    reason="no previous backup recorded"
else
    # shellcheck disable=SC1090
    source "$STATE_FILE"   # sets last_backup_time, last_backup_size
    elapsed_hours=$(( (now - last_backup_time) / 3600 ))

    if (( elapsed_hours >= MIN_INTERVAL_HOURS )); then
        should_run=true
        reason="${elapsed_hours}h since last backup (>= ${MIN_INTERVAL_HOURS}h)"
    elif (( last_backup_size > 0 )); then
        size_delta=$(( current_size > last_backup_size ? current_size - last_backup_size : last_backup_size - current_size ))
        delta_percent=$(( size_delta * 100 / last_backup_size ))
        if (( delta_percent >= MIN_SIZE_DELTA_PERCENT )); then
            should_run=true
            reason="DB size changed ${delta_percent}% since last backup (>= ${MIN_SIZE_DELTA_PERCENT}%)"
        fi
    fi
fi

if [[ "$should_run" != true ]]; then
    echo "[backup] Skipping - neither time nor size threshold met."
    exit 0
fi

timestamp=$(date +%Y%m%d-%H%M%S)
backup_path="$BACKUP_DIR/televault-$timestamp.db"
echo "[backup] Running backup ($reason) -> $backup_path"

# sqlite3's own .backup command - consistent even with concurrent readers/writers, unlike a plain file copy, which can miss recent WAL-only writes.
sqlite3 "$DB_PATH" ".backup '$backup_path'"

cat > "$STATE_FILE" <<EOF
last_backup_time=$now
last_backup_size=$current_size
EOF

echo "[backup] Pruning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name 'televault-*.db' -mtime "+$RETENTION_DAYS" -delete
echo "[backup] Complete."