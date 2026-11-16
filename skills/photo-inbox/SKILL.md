---
name: photo-inbox
description: "Handle photos sent without instructions: letters and bills, receipts, food."
version: 0.1.0
author: hermes-kit
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Inbox, Receipts, Letters, Vision]
---

# Photo inbox

All storage goes through one script. Never edit the files yourself.

    INBOX="python3 ~/.hermes/scripts/inbox.py"

## When to use

The user sends a photo with no caption. If there is a caption, do what the caption says instead; use the commands below only if the caption asks to log or file something.

## Stop first

ID card, passport, driving licence, bank or credit card, anything showing a full card or ID number: do not describe, store or log it. Reply `Not storing ID or card photos; keep those out of this chat.` and stop.

## Classify, then act

| The photo shows… | Do |
|---|---|
| a receipt or till slip | `$INBOX receipt --date YYYY-MM-DD --shop "<shop>" --amount <total incl. VAT> --currency <ISO code> --category <cat>` |
| a letter, bill, invoice, fine or official notice | `$INBOX letter --sender "<sender>" --summary "<what it wants from the user, ≤ 15 words>" [--amount "<amount currency>"] [--deadline YYYY-MM-DD]` |
| food, a fridge or a cupboard | no command; reply with two dinners from what's visible (one line each) and a `missing:` line |
| anything else | ask `What should I do with this?` |

Receipt rules:
- `--amount` is the final total paid, a plain number with `.` as decimal separator (Danish `1.234,50` → `1234.50`).
- `--currency`: DKK unless the receipt shows otherwise.
- `--category` is exactly one of `groceries`, `eating-out`, `transport`, `home`, `health`, `other`.
- Date unreadable → use today.
- Total unreadable → don't guess; ask `Total?`.

Letter rules: if there is a deadline, after logging create a one-off cron job at 09:00 three days before it (or tomorrow 09:00 if that is already past), delivered to this chat, with prompt `Reply with exactly: 📄 <sender>: <summary> — due <deadline>`.

## Reply

- Exit 0: reply with the script's output only. For letters add one line: `<summary>; <amount>; due <deadline>`.
- Exit 2: the output is a question; send it as is.
