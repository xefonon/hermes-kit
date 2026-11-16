#!/usr/bin/env bash
# Install hermes-kit into a Hermes home and register its cron jobs. Safe to re-run:
# scripts and skills are overwritten, data and existing jobs are left alone.
#   DELIVER=telegram:<chat_id> [CRON_MODEL=<model id>] [TZ_NAME=Europe/Copenhagen] ./install.sh
# DELIVER must be a concrete target: jobs are created from a shell, so "origin" has no chat to resolve to.
set -euo pipefail

: "${DELIVER:?set DELIVER to a concrete target, e.g. telegram:<chat_id>}"
TZ_NAME="${TZ_NAME:-Europe/Copenhagen}"
# Ask Hermes for its home: the hosted agent uses /opt/data, not ~/.hermes.
HH="${HERMES_HOME:-$(dirname "$(hermes config path)")}"
[ -f "$HH/config.yaml" ] || { echo "no Hermes home found at $HH" >&2; exit 1; }
here="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$HH/scripts" "$HH/skills/personal" "$HH/personal/state"
cp "$here"/scripts/*.py "$HH/scripts/"
for s in "$here"/skills/*/; do
  name="$(basename "$s")"
  rm -rf "$HH/skills/personal/$name"
  cp -R "$s" "$HH/skills/personal/$name"
  sed -i.bak "s|<HERMES_HOME>|$HH|g" "$HH/skills/personal/$name/SKILL.md"
  rm "$HH/skills/personal/$name/SKILL.md.bak"
done
[ -f "$HH/personal/watches.json" ] || echo '[]' > "$HH/personal/watches.json"

existing="$(hermes cron list 2>/dev/null || true)"
add_job() {
  local name="$1"; shift
  if grep -q -- "$name" <<<"$existing"; then
    echo "skip: $name already exists"
  else
    hermes cron create --name "$name" --deliver "$DELIVER" --timezone "$TZ_NAME" "$@"
  fi
}

model_args=()
[ -n "${CRON_MODEL:-}" ] && model_args=(--model "$CRON_MODEL")

add_job release-watch --monitor-script release_watch.py ${model_args[@]+"${model_args[@]}"} "0 8 * * 1" \
  "The monitor diff lists apps whose latest stable release changed (lines starting with +). \
For each such app run: python3 $HH/scripts/release_watch.py notes \"<app>\" \
If the notes only point to a changelog URL, fetch it and read only that version's section. \
Then reply with one line per app: '<app> <tag>: <the one or two changes that matter most to someone who uses it daily>'. \
No preamble, no links, nothing else."
add_job price-watch --no-agent --script price_watch.py "0 9 * * *"
add_job spend-report --no-agent --script spend_report.py "0 9 1 * *"

echo "installed into $HH (deliver=$DELIVER, tz=$TZ_NAME, model=${CRON_MODEL:-default})"
