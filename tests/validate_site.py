from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRED = [SITE / "index.html", SITE / "styles.css", SITE / "data.js", SITE / "app.js"]
REQUIRED_COPY = [
    "Automation OS — Centinal26",
    "1.0.0-rc4-converged",
    "REVIEW",
    "Intent",
    "Authorization",
    "Bounded Execution",
    "Evidence / Audit",
    "Controlled Evolution",
    "RECONSTRUCTED_SUCCESSOR",
    "COMPATIBLE_MODULE",
    "STATIC_VALIDATED",
    "No automatic GA promotion",
]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.local_refs: list[str] = []
        self.has_main = False
        self.has_nav = False
        self.has_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "main":
            self.has_main = True
        elif tag == "nav":
            self.has_nav = True
        elif tag == "h1":
            self.has_h1 = True
        if values.get("id"):
            self.ids.append(values["id"] or "")
        for key in ("href", "src"):
            value = values.get(key)
            if value and value.startswith("./"):
                self.local_refs.append(value[2:].split("#", 1)[0].split("?", 1)[0])


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.is_file()]
    if missing:
        raise SystemExit(f"site files missing: {missing}")

    html = (SITE / "index.html").read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(html)

    if not (parser.has_main and parser.has_nav and parser.has_h1):
        raise SystemExit("site must contain main, nav, and h1 landmarks")
    if len(parser.ids) != len(set(parser.ids)):
        raise SystemExit("duplicate HTML ids detected")
    for ref in parser.local_refs:
        if ref and not (SITE / ref).is_file():
            raise SystemExit(f"missing local site reference: {ref}")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in REQUIRED)
    missing_copy = [value for value in REQUIRED_COPY if value not in combined]
    if missing_copy:
        raise SystemExit(f"required project copy missing: {missing_copy}")

    forbidden = [
        r"javascript:",
        r"physical_android_validated\s*[:=]\s*true",
        r"current_release_status[^\n]{0,30}PASS",
        r"\bGA\s*[:=]\s*true\b",
    ]
    for pattern in forbidden:
        if re.search(pattern, combined, re.IGNORECASE):
            raise SystemExit(f"forbidden website claim/pattern detected: {pattern}")

    print("Automation OS website validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
