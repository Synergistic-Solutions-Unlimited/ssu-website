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
  7. Client anonymity     clients may be named as relationships, never inside a
                          case study or proof card describing what he built for them
  8. Mirrored build       family-care-hub assets all resolve and none are orphaned,
                          and its copy matches between server HTML and client bundle
  9. Claim consistency    a registered figure is stated the same on every page
 10. Retired terms       a renamed thing does not survive under its old name

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

# Josh's rule, 2026-08-27. Two tiers, because a blanket ban stopped matching policy.
#
#   The RELATIONSHIPS are nameable. Carriers and tower companies he worked for can
#   appear on the site.
#
#   What he BUILT FOR THEM is not. The documentation standards two carriers adopted,
#   and the relocation automation, stay unattributed. He will name them in person.
#
# So client names are refused only where the page is telling the story of something he
# made: inside a case study or proof card anywhere, and on the two case-study pages
# outright. A carrier named in a portfolio card is fine; the same carrier named beside
# the standard it adopted is not.
CLIENT_NAMES = [
    "uscellular", "u.s. cellular", "us cellular",
    "at&t", "at &amp; t", "t-mobile", "tmobile", "verizon", "gogo",
    "firstnet", "towercom", "american tower", "crown castle", "horvath",
    "craig & associates", "craig and associates", "king street", "vanguard elite",
    "vem global",
]

# Never, anywhere. Naming the former firm is the exact thing the pending contract
# due diligence with Josh's former business partner covers. He has not cleared it.
FIRM_BLOCKED = ["wireless group"]

# Pages that exist only to tell the story of something he built.
CASE_PAGES = {"portfolio-feasibility.html", "property-operations.html"}

# Individually cleared exceptions, (page, client). Each one is a decision Josh made
# about a specific story, recorded here rather than applied by loosening the rule,
# so the rule keeps working everywhere else and every exception has a name on it.
#
#   contested-outcomes / firstnet -- Josh, 2026-08-27. The easement recovery is site
#   work, not a program he authored for them, so his 2026-08-27 ruling permits it.
STORY_CLIENT_EXCEPTIONS = {
    ("contested-outcomes.html", "firstnet"),
}

# Blocks that tell that story on any other page.
STORY_BLOCK = re.compile(
    r'<article class="[^"]*(?:case-study|proof-card)[^"]*">(.*?)</article>', re.S)


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

        # 7. client anonymity, per the two-tier rule above
        lowered = src.lower()
        for firm in FIRM_BLOCKED:
            if firm in lowered:
                fail.append(f"{name}: {firm!r} is blocked everywhere, pending due diligence")
        if os.path.basename(name) in CASE_PAGES:
            scopes = [("page", lowered)]
        else:
            scopes = [("case study or proof card", m.group(1).lower())
                      for m in STORY_BLOCK.finditer(src)]
        base = os.path.basename(name)
        for where, text in scopes:
            for client in CLIENT_NAMES:
                if (base, client) in STORY_CLIENT_EXCEPTIONS:
                    continue
                if client in text:
                    fail.append(f"{name}: client {client!r} named inside a {where}. "
                                "Relationships are nameable; what he built for them is not.")

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

    fail += check_mirror(root)
    fail += check_claim_consistency(root)
    fail += check_retired_terms(root)

    if navs:
        reference = navs.get("index.html") or next(iter(navs.values()))
        for name, nav in navs.items():
            if nav != reference:
                fail.append(f"{name}: primary navigation differs from index.html")

    return fail


# Sentences that must read identically in the mirrored page's server HTML and in its
# client bundle. The page is a React build: text in index.html alone is replaced by the
# client render, so a copy edit there is invisible to visitors and adds a hydration
# mismatch. Both mistakes were made by hand before this check existed.
MIRROR_COPY = [
    "When my own family needed to coordinate closely and quickly",
    "An urgent situation in my own family, changing by the hour",
    "One person was fielding repeated questions",
]


def check_mirror(root: str) -> list[str]:
    """The mirrored case study is a vendored build, so the usual page checks miss its
    two real failure modes: copy that only reaches the HTML, and a chunk whose content
    was edited without renaming it, which leaves browsers on the cached old copy."""
    base = os.path.join(root, "family-care-hub")
    index = os.path.join(base, "index.html")
    assets = os.path.join(base, "assets")
    if not (os.path.isfile(index) and os.path.isdir(assets)):
        return []

    fail: list[str] = []
    html = open(index, encoding="utf-8").read()
    chunks = {f: open(os.path.join(assets, f), encoding="utf-8").read()
              for f in sorted(os.listdir(assets)) if f.endswith(".js")}

    # every referenced asset resolves, and nothing on disk is left unreferenced
    present = set(os.listdir(assets))
    refs: set[str] = set()
    for body in [html, *chunks.values()]:
        refs |= set(re.findall(r"assets/([A-Za-z0-9_.-]+\.(?:js|css))", body))
    for name in sorted(refs - present):
        fail.append(f"family-care-hub: references a missing asset {name!r}")
    for name in sorted(present - refs):
        fail.append(f"family-care-hub: {name!r} is on disk but nothing references it")

    # copy parity: a sentence in the server HTML must also be in the bundle that renders it
    bundle = "".join(chunks.values())
    for line in MIRROR_COPY:
        in_html, in_bundle = line in html, line in bundle
        if in_html and not in_bundle:
            fail.append(f"family-care-hub: {line[:44]!r}... is in index.html but not in any "
                        "chunk, so the client render will replace it")
        elif in_bundle and not in_html:
            fail.append(f"family-care-hub: {line[:44]!r}... is in a chunk but not in "
                        "index.html, which is a hydration mismatch")
    return fail


# A figure stated in several places drifts when only some are updated. That happened
# twice within an hour: SCOPE made the site a three-application practice and two pages
# went on saying two, because the fix was verified by grepping for the sentence that had
# been changed rather than for the claim. Register a claim here and every statement of it
# has to agree.
#
# Each entry is (name, pattern). The pattern must capture the quantity. Words and digits
# are compared as the same value, so "three" and "3" do not count as a disagreement.
# Names the site has retired. A renamed practice leaves its old name behind in the places
# nobody re-reads: "Systems Engineering" survived the rename in every footer and in the
# homepage eyebrow, on all thirteen pages, while the nav and the practice band already
# said something else. Checked against the rendered text, not the source.
RETIRED_TERMS = {
    "systems engineering": "the second practice is named Systems & Automation",
}


CLAIM_CONSISTENCY = [
    ("native applications", re.compile(
        r"(\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b)\s+native\s+(?:mac ?os\s+)?applications?",
        re.I)),
    ("operational systems", re.compile(
        r"(\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b)\s+operational\s+systems?", re.I)),
    ("denials", re.compile(
        r"(\b(?:one|two|three|four|five|\d+)\b)\s+denials?\b", re.I)),
    # Registered 2026-08-27 after this figure was corrected on three pages and survived
    # on a fourth, where Josh spotted it. The hours-to-first-notarised-build claim.
    ("hours to first notarised build", re.compile(
        r"(\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b)\s+hours?\s+"
        r"(?:and\s+\d+\s+minutes\s+)?(?:after the first commit|to the first notarised)", re.I)),
]

_WORD_NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
             "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def check_retired_terms(root: str) -> list[str]:
    """A retired name must not survive anywhere in the rendered text."""
    fail = []
    for f in pages(root):
        text = re.sub(r"<[^>]+>", " ", open(os.path.join(root, f), encoding="utf-8").read()).lower()
        for term, why in RETIRED_TERMS.items():
            if term in text:
                fail.append(f"{f}: retired term {term!r} still appears. {why}")
    return fail


def check_claim_consistency(root: str) -> list[str]:
    """Every page must state a registered figure the same way."""
    seen: dict[str, dict[str, list[str]]] = {name: {} for name, _ in CLAIM_CONSISTENCY}
    for f in pages(root):
        src = open(os.path.join(root, f), encoding="utf-8").read()
        text = re.sub(r"<[^>]+>", " ", src)
        for name, pattern in CLAIM_CONSISTENCY:
            for m in pattern.finditer(text):
                value = m.group(1).lower()
                value = _WORD_NUM.get(value, value)
                seen[name].setdefault(value, []).append(f)
    fail = []
    for name, values in seen.items():
        if len(values) > 1:
            detail = "; ".join(f"{v} in {', '.join(sorted(set(f)))}" for v, f in sorted(values.items()))
            fail.append(f"claim {name!r} is stated inconsistently: {detail}")
    return fail


DEFECTS = [
    ("unbalanced tag", lambda s: s.replace("</main>", "", 1)),
    ("dead internal link", lambda s: s.replace('href="contact.html"', 'href="nope.html"', 1)),
    ("aria-labelledby", lambda s: s.replace('id="situation-heading"', 'id="moved"', 1)),
    ("undefined class", lambda s: s.replace('class="lede"', 'class="lede undefined-xyz"', 1)),
    ("nav drift", lambda s: s.replace('<a href="about.html">About</a>', "", 1)),
    ("em dash", lambda s: s.replace("The situation", "The — situation", 1)),
    ("client named in a case study", lambda s: s.replace("A national wireless carrier", "UScellular", 1)),
    ("a registered figure drifting", lambda s: s.replace("<p class=\"lede\">", "<p class=\"lede\">Two native applications. ", 1)),
    ("a retired name coming back", lambda s: s.replace("<p class=\"lede\">", "<p class=\"lede\">Systems Engineering. ", 1)),
    ("former firm named anywhere", lambda s: s.replace("<p class=\"lede\">", "<p class=\"lede\">Wireless Group Consultants. ", 1)),
    # A cleared name is cleared for one page only. Planting it in a different page's
    # case study must still fail, or the exception has quietly become a hole.
    ("cleared name reused on another page", lambda s: s.replace("A national wireless carrier", "FirstNet", 1)),
]

# These two mutate the mirrored build rather than the page under test.
MIRROR_DEFECTS = [
    ("mirror copy drift", "family-care-hub/index.html",
     lambda s: s.replace("When my own family needed to coordinate", "When a family needed to coordinate", 1)),
    ("mirror orphaned chunk", "family-care-hub/index.html",
     lambda s: s.replace("framework-DjPHiq1u-r2.js", "framework-DjPHiq1u-r9.js")),
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

    for label, rel, mutate in MIRROR_DEFECTS:
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "site")
            shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git"))
            path = os.path.join(copy, rel)
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

    total = len(DEFECTS) + len(MIRROR_DEFECTS)
    print(f"\nSELF-TEST PASSED: {total} injected defects, {total} caught.")
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
