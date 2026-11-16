#!/usr/bin/env python3
"""Release watcher for Hermes monitor mode.

No args: print one stable line per app ("<app> <latest stable tag>"). Hermes hashes
this output and only wakes the model when it changes. On a fetch failure the last
good tag is reused so a network blip never looks like a release.

`notes <app>`: print the latest stable release notes as plain text, truncated.
"""

import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

APPS = {
    "Zed": "zed-industries/zed",
    "kitty": "kovidgoyal/kitty",
    "Herdr": "herdrdev/herdr-app",
    "herdr-core": "herdrdev/herdr",
    "Hermes Agent": "NousResearch/hermes-agent",
}
STABLE = re.compile(r"^v?\d+(\.\d+)+$")
NS = {"a": "http://www.w3.org/2005/Atom"}
NOTES_CHARS = 2000


def state_file() -> Path:
    p = Path(os.environ.get("HERMES_PERSONAL_DIR", Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "personal")) / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p / "release_watch.json"


def fetch(repo: str) -> bytes:
    req = urllib.request.Request(f"https://github.com/{repo}/releases.atom", headers={"User-Agent": "hermes-kit"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def fetch_api_latest(repo: str) -> tuple[str, str] | None:
    """Fallback when nightlies/canaries push every stable release out of the Atom feed window."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"User-Agent": "hermes-kit", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.load(r)
    return (d["tag_name"], html.escape(d.get("body") or "")) if STABLE.match(d["tag_name"]) else None


def latest_stable(feed: bytes) -> tuple[str, str] | None:
    for e in ET.fromstring(feed).findall("a:entry", NS):
        href = e.find("a:link", NS).get("href", "")
        tag = urllib.request.unquote(href.rsplit("/tag/", 1)[-1])
        if STABLE.match(tag):
            return tag, e.findtext("a:content", "", NS)
    return None


def latest(repo: str) -> tuple[str, str] | None:
    return latest_stable(fetch(repo)) or fetch_api_latest(repo)


def to_text(content_html: str) -> str:
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", content_html)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:NOTES_CHARS] + ("\n[truncated]" if len(t) > NOTES_CHARS else "")


def snapshot() -> str:
    f = state_file()
    last = json.loads(f.read_text()) if f.exists() else {}
    for app, repo in APPS.items():
        try:
            if hit := latest(repo):
                last[app] = hit[0]
        except Exception:
            pass
    f.write_text(json.dumps(last, indent=1))
    return "\n".join(f"{app} {last[app]}" for app in APPS if app in last)


def notes(app: str) -> str:
    if app not in APPS:
        print(f"unknown app {app!r}; known: {', '.join(APPS)}")
        sys.exit(2)
    hit = latest(APPS[app])
    if hit is None:
        return f"{app}: no stable release found"
    return f"{app} {hit[0]}\n{to_text(hit[1])}"


if __name__ == "__main__":
    print(notes(sys.argv[2]) if sys.argv[1:2] == ["notes"] else snapshot())
