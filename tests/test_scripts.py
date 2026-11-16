import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import inbox  # noqa: E402
import price_watch  # noqa: E402
import release_watch  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PERSONAL_DIR", str(tmp_path))
    return tmp_path


def run(capsys, *argv):
    inbox.main(list(argv))
    return capsys.readouterr().out.strip()


def test_todo_add_list_done(capsys):
    assert run(capsys, "todo", "add", "Book dentist", "--due", "2026-11-20") == "→ todo (due 2026-11-20)"
    assert run(capsys, "todo", "add", "Buy oat milk") == "→ todo"
    assert run(capsys, "todo", "add", "buy oat milk!") == "already on the list: buy oat milk!"
    assert run(capsys, "todo", "list") == "1. Book dentist (due 2026-11-20)\n2. Buy oat milk"
    assert run(capsys, "todo", "done", "dentist") == "done: Book dentist"
    assert run(capsys, "todo", "list") == "1. Buy oat milk"
    assert run(capsys, "todo", "done", "1") == "done: Buy oat milk"
    assert run(capsys, "todo", "list") == "no open todos"


def test_todo_done_ambiguous_asks(capsys):
    run(capsys, "todo", "add", "Call mum")
    run(capsys, "todo", "add", "Call dad")
    with pytest.raises(SystemExit) as e:
        inbox.main(["todo", "done", "call"])
    assert e.value.code == 2
    assert capsys.readouterr().out.startswith("which one?")


def test_bad_due_date_asks(capsys):
    with pytest.raises(SystemExit) as e:
        inbox.main(["todo", "add", "x", "--due", "Friday"])
    assert e.value.code == 2


def test_idea_and_journal_files(capsys, home):
    assert run(capsys, "idea", "e-ink weather glyphs") == "→ ideas"
    assert run(capsys, "journal", "Ran 8 km") == "→ journal"
    assert "e-ink weather glyphs" in (home / "ideas.md").read_text()
    assert "Ran 8 km" in (home / "journal" / f"{date.today():%Y-%m-%d}.md").read_text()


def test_receipt_dedup_and_spend(capsys):
    args = ["receipt", "--date", "2026-10-03", "--shop", "Netto", "--amount", "212.5", "--currency", "dkk",
            "--category", "groceries"]
    assert run(capsys, *args) == "logged: Netto 212.50 DKK (groceries)"
    assert run(capsys, *args) == "already logged: Netto 212.50 DKK"
    run(capsys, "receipt", "--date", "2026-10-09", "--shop", "DSB", "--amount", "48", "--currency", "DKK",
        "--category", "transport")
    assert run(capsys, "spend", "2026-10") == (
        "Spending 2026-10\ngroceries: 212.50 DKK\ntransport: 48.00 DKK\ntotal: 260.50 DKK")
    assert run(capsys, "spend", "2026-09") == ""


def test_receipt_rejects_unknown_category(capsys):
    with pytest.raises(SystemExit):
        inbox.main(["receipt", "--date", "2026-10-03", "--shop", "x", "--amount", "1", "--currency", "DKK",
                    "--category", "fun"])


def test_spend_defaults_to_last_month(capsys):
    last = date.today().replace(day=1) - timedelta(days=1)
    run(capsys, "receipt", "--date", last.isoformat(), "--shop", "Irma", "--amount", "10", "--currency", "DKK",
        "--category", "groceries")
    assert inbox.spend(None).startswith(f"Spending {last:%Y-%m}")


@pytest.mark.parametrize("raw, want", [("1.234,50", 1234.5), ("1,234.50", 1234.5), ("899,00 kr.", 899.0),
                                       ("1,299", 1299.0), ("249.95", 249.95), ("n/a", None)])
def test_price_parsing(raw, want):
    assert price_watch.to_float(raw) == want


def test_extract_json_ld_and_meta():
    ld = ('<script type="application/ld+json">{"@type":"Product","offers":{"@type":"Offer",'
          '"price":"1299.00","availability":"https://schema.org/OutOfStock"}}</script>')
    assert price_watch.extract(ld) == (1299.0, False)
    assert price_watch.extract('<meta property="product:price:amount" content="499,95">') == (499.95, None)
    assert price_watch.extract("<html>no price</html>") is None


def page(price, stock="InStock"):
    return ('<script type="application/ld+json">{"offers":{"price":"%s","availability":"%s"}}</script>'
            % (price, stock))


def test_price_alerts_once_per_new_low_and_on_stock_change():
    w, s = {"name": "Kindle", "url": "u", "drop_pct": 15}, {}
    assert price_watch.check(w, s, page(1000)) == []
    assert price_watch.check(w, s, page(900)) == []
    assert price_watch.check(w, s, page(840))[0].startswith("💸 Kindle: 840")
    assert price_watch.check(w, s, page(840)) == []
    assert price_watch.check(w, s, page(800))[0].startswith("💸 Kindle: 800")
    assert price_watch.check(w, s, page(800, "OutOfStock")) == ["📦 Kindle: out of stock u"]


def test_price_failure_alerts_once_after_three():
    w, s = {"name": "X", "url": "u"}, {}
    alerts = [price_watch.check(w, s, None) for _ in range(4)]
    assert alerts == [[], [], ["⚠ X: couldn't read a price 3 times in a row; check u"], []]


ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry><link href="https://github.com/a/b/releases/tag/nightly"/><content>n</content></entry>
 <entry><link href="https://github.com/a/b/releases/tag/v1.29.0-pre"/><content>p</content></entry>
 <entry><link href="https://github.com/a/b/releases/tag/v0.23.1%2Bcanary.1"/><content>c</content></entry>
 <entry><link href="https://github.com/a/b/releases/tag/v1.28.1"/><content>&lt;p&gt;Fix &amp;amp; speed&lt;/p&gt;</content></entry>
</feed>"""


def test_latest_stable_skips_prereleases():
    tag, content = release_watch.latest_stable(ATOM)
    assert tag == "v1.28.1"
    assert release_watch.to_text(content) == "Fix & speed"


def test_snapshot_keeps_last_good_tag_on_failure(monkeypatch):
    monkeypatch.setattr(release_watch, "APPS", {"A": "a/b"})
    monkeypatch.setattr(release_watch, "fetch", lambda repo: ATOM)
    assert release_watch.snapshot() == "A v1.28.1"

    def boom(repo):
        raise OSError("offline")

    monkeypatch.setattr(release_watch, "fetch", boom)
    monkeypatch.setattr(release_watch, "fetch_api_latest", boom)
    assert release_watch.snapshot() == "A v1.28.1"
