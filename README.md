# hermes-kit

Personal Hermes Agent add-ons built so a cheap model with a daily cap does as little as possible: scripts do the storage, parsing and change detection; the model only classifies input or summarises a diff.

| Piece | Kind | Model calls |
|---|---|---|
| `voice-inbox` skill + `inbox.py` | todo / idea / journal from voice notes | 1 short call per note |
| `photo-inbox` skill + `inbox.py` | receipts → CSV, letters → log + reminder, fridge → dinners | 1 vision call per photo |
| `release-watch` | monitor job, Mon 08:00 | 0 unless a stable release appeared |
| `price-watch` | no-agent job, daily 09:00 | 0 |
| `spend-report` | no-agent job, 1st of month 09:00 | 0 |

Install (re-runnable; keeps data and existing jobs):

    DELIVER=telegram:<chat_id> CRON_MODEL=<cheap model id> ./install.sh

Data lives in `$HERMES_HOME/personal/`. Add price watches to `watches.json`:

    [{"name": "Kindle Paperwhite", "url": "https://…", "drop_pct": 15}]

Tests: `uvx pytest tests`
