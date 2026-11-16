---
name: voice-inbox
description: "File voice notes and short texts into todo, ideas or journal; list and tick off todos."
version: 0.1.0
author: hermes-kit
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Inbox, Todo, Journal, Voice]
---

# Voice inbox

All storage goes through one script. Never edit the files yourself, never paste a transcript back.

    INBOX="python3 ~/.hermes/scripts/inbox.py"

## When to use

- The user sends a voice note (transcribe it first) or a text starting with `todo`, `idea`, `note`.
- The user writes `todo` / `todos` alone (list), or `done <words or number>`.

## Classify, then run exactly one command

| The note… | Command |
|---|---|
| says "todo", "remind me", "I need to", "don't forget", or is clearly an action | `$INBOX todo add "<task, imperative, ≤ 12 words>" [--due <date>]` |
| says "idea", or is a thought or question with no action | `$INBOX idea "<idea, ≤ 25 words>"` |
| anything else (a feeling, an event, a log of the day) | `$INBOX journal "<the note, lightly cleaned>"` |
| `todo` / `todos` alone | `$INBOX todo list` |
| `done <x>` | `$INBOX todo done "<x>"` |

Due dates: resolve relative dates ("Friday", "tomorrow at 9") against today in the user's timezone and pass `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM`. No date mentioned → no `--due`. Never invent one.

A note with several items: run one command per item.

## Reply

- Exit 0: reply with the script's output and nothing else (e.g. `→ todo (due 2026-11-20)`).
- Exit 2: the output is a question for the user (ambiguous match or bad input). Send it as is and wait.
- If you can't tell todo from idea from journal, ask once: `1 todo · 2 idea · 3 journal?` and file on the reply.

## Reminders

Only for todos with a time (`--due YYYY-MM-DDTHH:MM`): after the add succeeds, create a one-off cron job at that time, delivered to this chat, with prompt `Reply with exactly: ⏰ <task>`. Date-only todos get no reminder.
