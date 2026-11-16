#!/usr/bin/env python3
"""No-agent price watcher. Reads watches.json, prints only alerts; empty output = silent.

watches.json: [{"name": "...", "url": "...", "drop_pct": 15}]
The first successful read becomes the baseline. Alerts fire once per new low below
baseline × (1 − drop_pct/100), on stock changes, and once after 3 failed reads in a row.
"""

import html
import json
import os
import re
import urllib.request
from pathlib import Path

FAILS_BEFORE_ALERT = 3
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def root() -> Path:
    return Path(os.environ.get("HERMES_PERSONAL_DIR", Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "personal"))


def to_float(s: str) -> float | None:
    s = re.sub(r"[^\d.,]", "", str(s)).strip(".,")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.rsplit(",", 1)[1]) <= 2 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def offers(node: object):
    if isinstance(node, list):
        for n in node:
            yield from offers(n)
    elif isinstance(node, dict):
        if "price" in node or "lowPrice" in node:
            yield node
        for v in node.values():
            yield from offers(v)


def extract(page: str) -> tuple[float, bool | None] | None:
    """Return (price, in_stock) from JSON-LD offers, falling back to price meta tags."""
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(html.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        for o in offers(data):
            price = to_float(o.get("price", o.get("lowPrice", "")))
            if price:
                avail = str(o.get("availability", ""))
                return price, (None if not avail else "InStock" in avail or "LimitedAvailability" in avail)
    for pat in (r'property="(?:product|og):price:amount"\s+content="([^"]+)"',
                r'itemprop="price"\s+content="([^"]+)"',
                r'content="([^"]+)"\s+itemprop="price"'):
        if (m := re.search(pat, page)) and (price := to_float(m[1])):
            return price, None
    return None


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,da;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def check(w: dict, s: dict, page: str | None) -> list[str]:
    """Update state `s` in place for watch `w` and return alert lines."""
    name, out = w["name"], []
    got = extract(page) if page is not None else None
    if got is None:
        s["fails"] = s.get("fails", 0) + 1
        if s["fails"] == FAILS_BEFORE_ALERT:
            out.append(f"⚠ {name}: couldn't read a price {FAILS_BEFORE_ALERT} times in a row; check {w['url']}")
        return out
    price, in_stock = got
    s["fails"] = 0
    if "baseline" not in s:
        s["baseline"] = price
    target = s["baseline"] * (1 - w.get("drop_pct", 15) / 100)
    if price <= target and price < s.get("alerted_at", float("inf")):
        out.append(f"💸 {name}: {price:g} (baseline {s['baseline']:g}, −{100 * (1 - price / s['baseline']):.0f} %) {w['url']}")
        s["alerted_at"] = price
    elif price > target:
        s.pop("alerted_at", None)
    if in_stock is not None and "in_stock" in s and in_stock != s["in_stock"]:
        out.append(f"📦 {name}: {'back in stock' if in_stock else 'out of stock'} {w['url']}")
    if in_stock is not None:
        s["in_stock"] = in_stock
    s["last"] = price
    return out


def main() -> None:
    wf = root() / "watches.json"
    if not wf.exists():
        return
    sf = root() / "state" / "price_watch.json"
    sf.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(sf.read_text()) if sf.exists() else {}
    alerts = []
    for w in json.loads(wf.read_text()):
        try:
            page = fetch(w["url"])
        except Exception:
            page = None
        alerts += check(w, state.setdefault(w["name"], {}), page)
    sf.write_text(json.dumps(state, indent=1))
    if alerts:
        print("\n".join(alerts))


if __name__ == "__main__":
    main()
