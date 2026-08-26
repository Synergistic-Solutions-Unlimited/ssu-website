#!/usr/bin/env python3
"""Structural checker for thinksynergy.biz.

The last arc built a checker like this and did not keep it, so the standard had to be
rebuilt from a handoff. It lives in the repo now.

Checks, per the standing constraints in the website handoff:

  1. Tag balance          every opened element is closed, in order
  2. Internal links       every relative href resolves to a file on disk
  3. aria-labelledby      every referenced id exists on the same page
  4. CSS classes          every class used in HTML is defined in styles.css
  5. Nav identity         the same links, in the same order, on every page
  6. Em dashes            none anywhere (Josh reads them as an AI tell)
  7. Client anonymity     no blocked client identifier appears on the public site

Run:  python3 tools/check-site.py
      python3 tools/check-site.py --root /path/to/copy

Exit 0 on pass, 1 on any failure. Prove it can fail before trusting a pass:
      python3 tools/check-site.py --self-test
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# Blocked on the public site until contract due diligence completes. His resume does
# name them; that asymmetry is deliberate. Do not harmonize the two.
BLOCKED_CLIENTS = [
    "uscellular", "u.s. cellular", "us cellular",
    "at&t", "at &amp; t", "t-mobile", "tmobile",
    "verizon", "gogo", "firstnet", "towercom",
    "king street", "vanguard elite", "vem global",
]


def pages(root: str) -> list[str]:
    """Top-level HTML pages. The mirrored case study has its own template and is
    checked for tag balance and em dashes only, not for nav identity."""
    return sorted(
        f for f in os.listdir(root)
        if f.endswith(".html") and os.path.isfile(os.path.join(root, f))
    )


class Balance(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> with nothing open")
            return
        open_tag, open_line = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                f"line {self.getpos()[0]}: </{tag}> closes <{open_tag}> opened at line {open_line}"
            )

    def finish(self) -> list[str]:
        for tag, line in self.stack:
            self.errors.append(f"line {line}: <{tag}> never closed")
        return self.errors


def check(root: str) -> list[str]:
    fail: list[str] = []
    html_files = pages(root)
    if not html_files:
        return [f"no HTML pages found under {root}"]

    css_path = os.path.join(root, "styles.css")
    if not os.path.isfile(css_path):
        return [f"styles.css missing at {css_path}"]
    css = open(css_path, encoding="utf-8").read()
    defined = set(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", css))

    navs: dict[str, list[tuple[str, str]]] = {}
    all_html = list(html_files)
    fch = os.path.join("family-care-hub", "index.html")
    if os.path.isfile(os.path.join(root, fch)):
        all_html.append(fch)

    for name in all_html:
        path = os.path.join(root, name)
        src = open(path, encoding="utf-8").read()
        mirrored = name == fch

        # 1. tag balance
        parser = Balance()
        parser.feed(src)
        for err in parser.finish():
            fail.append(f"{name}: unbalanced tag, {err}")

        # 6. em dashes
        for marker in ("—", "&mdash;"):
            if marker in src:
                line = src[: src.index(marker)].count("\n") + 1
                fail.append(f"{name}: em dash at line {line}")

        # 7. client anonymity
        lowered = src.lower()
        for client in BLOCKED_CLIENTS:
            if client in lowered:
                fail.append(f"{name}: blocked client identifier {client!r}")

        if mirrored:
            continue

        # 2. internal links resolve
        for href in re.findall(r'href="([^"]+)"', src):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = href.split("#", 1)[0]
            if not target:
                continue
            candidate = os.path.join(root, target.lstrip("/"))
            if os.path.isdir(candidate):
                candidate = os.path.join(candidate, "index.html")
            if not os.path.exists(candidate):
                fail.append(f"{name}: dead internal link {href!r}")

        # 3. aria-labelledby targets exist
        ids = set(re.findall(r'\bid="([^"]+)"', src))
        for ref in re.findall(r'aria-labelledby="([^"]+)"', src):
            for token in ref.split():
                if token not in ids:
                    fail.append(f"{name}: aria-labelledby={token!r} has no matching id")

        # 4. every class used is defined
        for attr in re.findall(r'class="([^"]*)"', src):
            for cls in attr.split():
                if cls not in defined:
                    fail.append(f"{name}: class {cls!r} is not defined in styles.css")

        # 5. nav identity. Compared as an ordered list of (href, label): whitespace
        # formatting differs between pages, and aria-current is correctly per-page.
        nav = re.search(r'<nav aria-label="Primary navigation">.*?</nav>', src, re.S)
        if not nav:
            fail.append(f"{name}: no primary navigation")
        else:
            navs[name] = re.findall(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', nav.group(0))

    if navs:
        reference = navs.get("index.html") or next(iter(navs.values()))
        for name, nav in navs.items():
            if nav != reference:
                fail.append(f"{name}: primary navigation differs from index.html")

    return fail


DEFECTS = [
    ("unbalanced tag", lambda s: s.replace("</main>", "", 1)),
    ("dead internal link", lambda s: s.replace('href="contact.html"', 'href="nope.html"', 1)),
    ("aria-labelledby", lambda s: s.replace('id="situation-heading"', 'id="moved"', 1)),
    ("undefined class", lambda s: s.replace('class="lede"', 'class="lede undefined-xyz"', 1)),
    ("nav drift", lambda s: s.replace('<a href="about.html">About</a>', "", 1)),
    ("em dash", lambda s: s.replace("The situation", "The — situation", 1)),
    ("client name", lambda s: s.replace("A national wireless carrier", "UScellular", 1)),
]


def self_test(root: str) -> int:
    """A checker that has never failed is not known to work. Inject one defect at a
    time into a throwaway copy and require the checker to catch each one."""
    baseline = check(root)
    if baseline:
        print("SELF-TEST ABORTED: the clean tree already fails.", file=sys.stderr)
        for line in baseline:
            print(f"  {line}", file=sys.stderr)
        return 1

    target = "portfolio-feasibility.html"
    if not os.path.isfile(os.path.join(root, target)):
        print(f"SELF-TEST ABORTED: {target} not found", file=sys.stderr)
        return 1

    missed = []
    for label, mutate in DEFECTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "site")
            shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git"))
            path = os.path.join(copy, target)
            src = open(path, encoding="utf-8").read()
            broken = mutate(src)
            if broken == src:
                missed.append(f"{label}: the defect did not apply, the probe is vacuous")
                continue
            open(path, "w", encoding="utf-8").write(broken)
            if check(copy):
                print(f"  caught: {label}")
            else:
                missed.append(f"{label}: NOT CAUGHT")

    if missed:
        print("\nSELF-TEST FAILED. The checker cannot detect:", file=sys.stderr)
        for line in missed:
            print(f"  {line}", file=sys.stderr)
        return 1

    print(f"\nSELF-TEST PASSED: {len(DEFECTS)} injected defects, {len(DEFECTS)} caught.")
    return 0


def main() -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=here)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test(args.root)

    failures = check(args.root)
    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"PASS: {len(pages(args.root))} pages checked, no problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
