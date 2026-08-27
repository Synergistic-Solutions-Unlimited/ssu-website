#!/usr/bin/env python3
"""Per-page Open Graph cards, in the language of the existing brand card.

Every page shared one og-image.png, so a LinkedIn Featured carousel of three links
rendered as three identical tiles. The shared card was also stale: it carried the
retired "Systems Engineering" tagline. These keep its design (ink ground, lime rule,
serif headline, lime figure row) and give each page its own headline and figures.

Run: python3 tools/make-og.py     Output: og/<slug>.png at 1200x630.
"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 630
INK   = (20, 34, 33)
PAPER = (244, 241, 233)
LIME  = (204, 230, 106)
MUTED = (159, 179, 172)
RULE  = (60, 79, 74)

GB = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
G  = "/System/Library/Fonts/Supplemental/Georgia.ttf"
A  = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if not os.path.exists(A): A = "/System/Library/Fonts/Supplemental/Arial.ttf"
PAD = 64

def tracked(d, xy, text, font, fill, sp):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + sp
    return x

def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def card(slug, headline, stats):
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=LIME)

    f_mark = ImageFont.truetype(A, 20)
    f_word = ImageFont.truetype(A, 20)
    f_tag  = ImageFont.truetype(A, 13)
    f_fig  = ImageFont.truetype(G, 40)
    f_lab  = ImageFont.truetype(A, 13)

    # identity block, top left, matching the card this replaces
    cy = PAD + 20
    d.ellipse([PAD, cy - 20, PAD + 40, cy + 20], fill=LIME)
    tw = d.textlength("SSU", font=f_mark)
    d.text((PAD + 20 - tw / 2, cy - 10), "SSU", font=f_mark, fill=INK)
    d.text((PAD + 54, cy - 20), "Synergistic Solutions Unlimited", font=f_word, fill=PAPER)
    tracked(d, (PAD + 54, cy + 6), "PROPERTY OPERATIONS  ·  INFRASTRUCTURE  ·  SYSTEMS & AUTOMATION",
            f_tag, MUTED, 1.5)

    size = 66
    while size > 34:
        f_h = ImageFont.truetype(GB, size)
        lines = wrap(d, headline, f_h, W - PAD * 2)
        if len(lines) <= 3: break
        size -= 3
    block = len(lines) * int(size * 1.2)
    y = (H - block) // 2 + 10
    for ln in lines:
        d.text((PAD, y), ln, font=f_h, fill=PAPER)
        y += int(size * 1.2)

    if stats:
        yb = H - 122
        d.line([(PAD, yb), (W - PAD, yb)], fill=RULE, width=1)
        col = (W - PAD * 2) // max(len(stats), 1)
        for i, (fig, lab) in enumerate(stats):
            x = PAD + i * col
            d.text((x, yb + 22), fig, font=f_fig, fill=LIME)
            tracked(d, (x + 2, yb + 76), lab.upper(), f_lab, MUTED, 1.4)

    img.save(f"og/{slug}.png", optimize=True)
    return f"og/{slug}.png"

CARDS = [
 ("index", "Operational systems for land development and property operations.",
   [("865","Sites developed"),("23","States"),("13,875","Project documents"),("3","Denials in twelve years")]),
 ("infrastructure", "Twelve years getting land ready to build on.",
   [("865","Sites developed"),("23","States"),("13,875","Project documents"),("3","Denials in twelve years")]),
 ("hearing-record", "Several hundred hearings. Three denials in twelve years.",
   [("3","Denials, and three is exact"),("12","Years presenting"),("23","States"),("1","Called before filing")]),
 ("contested-outcomes", "Two sites where the straightforward path was already gone.",
   [("80","Acre parcel unleasable"),("15","Feet the easement covered"),("1","Border crossed"),("1","Tower built")]),
 ("portfolio-feasibility", "317 packages, 60 days, three days to build the pipeline.",
   [("317","Feasibility packages"),("316","Sites covered"),("60","Day window"),("3","Days to build it")]),
 ("property-operations", "One guided setup, instead of seven manual ones.",
   [("7","Systems in production"),("5","People running the month"),("28","Governed items"),("1","Guided setup")]),
 ("scope", "An hour can only be spent once.",
   [("497","Automated tests"),("18","Notarised releases"),("4","Hours to the first"),("2","Platforms, one store")]),
 ("client-onboarding", "One intake path, from first conversation to property setup.",
   [("6","Guided intake sections"),("10","Gated steps"),("19","Application routes"),("17","Tables of state")]),
 ("services", "Two practices. Land and entitlement, systems and automation.",
   [("12","Service areas"),("865","Sites"),("23","States")]),
 ("systems", "These are running right now.",
   [("7","Operational systems"),("3","Native applications"),("5","Web properties")]),
 ("proof", "The record, with the method that produced it.",
   [("865","Sites"),("317","Packages in 60 days"),("3","Denials in twelve years")]),
 ("about", "The sector changes. The problem does not.",
   [("2014","To present"),("23","States"),("865","Sites")]),
 ("contact", "Start with the work that needs clarity.", []),
]

if __name__ == "__main__":
    os.makedirs("og", exist_ok=True)
    for c in CARDS: print("  ", card(*c))
