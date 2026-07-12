# Update notes — 12 Jul 2026

## Changes made

- Fixed `download.py` to use only the first line of each LMArena model cell. LMArena
  now renders provider and license metadata on a second line in that cell; exporting
  the full cell produced an extra physical line per model and caused `update_elo.py`
  to reject the result as malformed TSV. The extractor shown in `README.md` was kept
  in sync with the executable version.
- Ran `update.sh` successfully against all three live leaderboards. It refreshed 374
  overall models, 374 hard-prompt models, and 369 coding models in `elo.csv`; seven
  models were newly added by the overall update.
- Updated the date shown in `README.md` to match the refreshed data.

## Maintenance notes

- `download.py` requires a Chromium browser exposing CDP at
  `http://localhost:9222`. It extracts the third and fourth cells from LMArena's
  leaderboard table, so upstream table-layout or cell-content changes can break the
  TSV contract again. A valid export has one `Model<TAB>Score` header followed by one
  two-column line per model; inspect that shape first if `update_elo.py` reports a TSV
  error.
- The overall and hard exports can have identical line and byte counts while still
  containing different scores. Compare content or hashes rather than treating equal
  sizes as evidence that routing failed.
- `update_elo.py` enriches touched rows from OpenRouter only when it finds a
  conservative, unambiguous model-name match. This run intentionally left 114
  overall/hard models and 109 coding models unmatched rather than guessing prices or
  launch dates.
- An overall update marks previously active models missing from the current overall
  leaderboard with an approximate end month. Newly seen models without OpenRouter
  launch metadata receive the previous month with a `?`; review these approximate
  dates when authoritative model information becomes available.
