#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

run_update() {
  local url="$1"
  local column="$2"
  local output="$tmpdir/${column}.txt"

  echo "Downloading ${column} leaderboard from ${url}" >&2
  uv run download.py "$url" "$output" --format json

  echo "Updating elo.csv column ${column}" >&2
  uv run update_elo.py "$output" --column "$column"
}

run_update "https://lmarena.ai/leaderboard/text" "overall"
run_update "https://lmarena.ai/leaderboard/text/hard-prompts" "hard"
run_update "https://lmarena.ai/leaderboard/text/coding" "coding"
