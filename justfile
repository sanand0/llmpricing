build:
    #!/usr/bin/env bash
    set -euo pipefail
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT

    update() {
      local column="$1" url="$2" output="$tmpdir/$1.txt"
      echo "Downloading $column leaderboard from $url" >&2
      uv run download.py "$url" "$output" --format json
      echo "Updating elo.csv column $column" >&2
      uv run update_elo.py "$output" --column "$column"
    }

    update overall https://lmarena.ai/leaderboard/text
    update hard https://lmarena.ai/leaderboard/text/hard-prompts
    update coding https://lmarena.ai/leaderboard/text/coding

push:
    git add .
    git commit -m "Update models"
    git push
