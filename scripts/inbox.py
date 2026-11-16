#!/usr/bin/env python3
"""Personal inbox store for Hermes: todos, ideas, journal, letters, receipts.

Every command prints one short line meant to be relayed to the user verbatim.
Exit code 2 means the agent must ask the user (ambiguous match, bad input).
"""

import argparse
import csv
import difflib
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

CATEGORIES = ("groceries", "eating-out", "transport", "home", "health", "other")
TODO_RE = re.compile(r"^- \[( |x)\] (.*?)(?: \(due: ([^)]+)\))?$")


def root() -> Path:
    p = Path(os.environ.get("HERMES_PERSONAL_DIR", Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "personal"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def fail(msg: str) -> None:
    print(msg)
    sys.exit(2)


def check_due(due: str | None) -> str | None:
    if due is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M"):
        try:
            datetime.strptime(due, fmt)
            return due
        except ValueError:
            pass
    fail(f"bad due date {due!r}: use YYYY-MM-DD or YYYY-MM-DDTHH:MM")


def norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def read_todos() -> list[tuple[bool, str, str | None]]:
    f = root() / "todo.md"
    if not f.exists():
        return []
    out = []
    for line in f.read_text().splitlines():
        if m := TODO_RE.match(line):
            out.append((m[1] == "x", m[2], m[3]))
    return out


def write_todos(items: list[tuple[bool, str, str | None]]) -> None:
    lines = [f"- [{'x' if d else ' '}] {t}" + (f" (due: {due})" if due else "") for d, t, due in items]
    (root() / "todo.md").write_text("\n".join(lines) + "\n")


def todo_add(text: str, due: str | None) -> str:
    due = check_due(due)
    items = read_todos()
    if any(not d and norm(t) == norm(text) for d, t, _ in items):
        return f"already on the list: {text}"
    items.append((False, text.strip(), due))
    write_todos(items)
    return f"→ todo (due {due})" if due else "→ todo"


def todo_list() -> str:
    open_ = [(t, due) for d, t, due in read_todos() if not d]
    if not open_:
        return "no open todos"
    return "\n".join(f"{i}. {t}" + (f" (due {due})" if due else "") for i, (t, due) in enumerate(open_, 1))


def todo_done(query: str) -> str:
    items = read_todos()
    open_idx = [i for i, (d, _, _) in enumerate(items) if not d]
    if not open_idx:
        return "no open todos"
    if query.isdigit():
        n = int(query)
        if not 1 <= n <= len(open_idx):
            fail(f"no open todo number {n}")
        hit = open_idx[n - 1]
    else:
        scored = sorted(
            ((difflib.SequenceMatcher(None, norm(query), norm(items[i][1])).ratio()
              + (0.5 if norm(query) in norm(items[i][1]) else 0.0), i) for i in open_idx),
            reverse=True,
        )
        best, hit = scored[0]
        if best < 0.5:
            fail(f"no open todo matches {query!r}")
        if len(scored) > 1 and best - scored[1][0] < 0.1:
            fail("which one? " + " | ".join(f"{open_idx.index(i) + 1}. {items[i][1]}" for _, i in scored[:3]))
    d, t, due = items[hit]
    items[hit] = (True, t, due)
    write_todos(items)
    return f"done: {t}"


def append(name: str, line: str) -> None:
    f = root() / name
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a") as fh:
        fh.write(line + "\n")


def idea(text: str) -> str:
    append("ideas.md", f"- {date.today().isoformat()}: {text.strip()}")
    return "→ ideas"


def journal(text: str) -> str:
    now = datetime.now()
    append(f"journal/{now:%Y-%m-%d}.md", f"- {now:%H:%M} {text.strip()}")
    return "→ journal"


def letter(sender: str, summary: str, amount: str | None, deadline: str | None) -> str:
    deadline = check_due(deadline)
    append("letters.md", f"- {date.today().isoformat()} | {sender} | {summary} | {amount or '-'} | due {deadline or '-'}")
    return f"→ letters ({sender}" + (f", due {deadline}" if deadline else "") + ")"


def receipt(day: str, shop: str, amount: float, currency: str, category: str) -> str:
    check_due(day)
    if category not in CATEGORIES:
        fail(f"category must be one of: {', '.join(CATEGORIES)}")
    currency = currency.upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        fail(f"bad currency {currency!r}: use a 3-letter code like DKK")
    f = root() / "spending" / f"{day[:7]}.csv"
    f.parent.mkdir(parents=True, exist_ok=True)
    rows = list(csv.reader(f.open())) if f.exists() else []
    key = (day, norm(shop), f"{amount:.2f}", currency)
    if any((r[0], norm(r[1]), r[2], r[3]) == key for r in rows):
        return f"already logged: {shop} {amount:.2f} {currency}"
    with f.open("a", newline="") as fh:
        csv.writer(fh).writerow([day, shop.strip(), f"{amount:.2f}", currency, category])
    return f"logged: {shop.strip()} {amount:.2f} {currency} ({category})"


def spend(month: str | None) -> str:
    if month is None:
        month = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    f = root() / "spending" / f"{month}.csv"
    if not f.exists():
        return ""
    totals: dict[tuple[str, str], float] = {}
    for d, _, amt, cur, cat in csv.reader(f.open()):
        totals[(cur, cat)] = totals.get((cur, cat), 0.0) + float(amt)
    lines = [f"Spending {month}"]
    for cur in sorted({c for c, _ in totals}):
        cats = sorted(((v, k) for (c, k), v in totals.items() if c == cur), reverse=True)
        lines += [f"{k}: {v:.2f} {cur}" for v, k in cats]
        lines.append(f"total: {sum(v for v, _ in cats):.2f} {cur}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="inbox")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("todo").add_subparsers(dest="action", required=True)
    ta = t.add_parser("add")
    ta.add_argument("text")
    ta.add_argument("--due")
    t.add_parser("list")
    t.add_parser("done").add_argument("query")
    sub.add_parser("idea").add_argument("text")
    sub.add_parser("journal").add_argument("text")
    lp = sub.add_parser("letter")
    lp.add_argument("--sender", required=True)
    lp.add_argument("--summary", required=True)
    lp.add_argument("--amount")
    lp.add_argument("--deadline")
    rp = sub.add_parser("receipt")
    rp.add_argument("--date", required=True)
    rp.add_argument("--shop", required=True)
    rp.add_argument("--amount", required=True, type=float)
    rp.add_argument("--currency", required=True)
    rp.add_argument("--category", required=True)
    sub.add_parser("spend").add_argument("month", nargs="?")
    a = p.parse_args(argv)

    if a.cmd == "todo":
        out = {"add": lambda: todo_add(a.text, a.due), "list": todo_list, "done": lambda: todo_done(a.query)}[a.action]()
    elif a.cmd == "idea":
        out = idea(a.text)
    elif a.cmd == "journal":
        out = journal(a.text)
    elif a.cmd == "letter":
        out = letter(a.sender, a.summary, a.amount, a.deadline)
    elif a.cmd == "receipt":
        out = receipt(a.date, a.shop, a.amount, a.currency, a.category)
    else:
        out = spend(a.month)
    if out:
        print(out)


if __name__ == "__main__":
    main()
