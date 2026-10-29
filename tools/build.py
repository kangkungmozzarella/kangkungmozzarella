"""Builds the animated SVGs in assets/ from the portfolio repo.

Usage: python3 tools/build.py /path/to/portfolio-andre
Needs Pillow, fonttools, and brotli. The SVGs embed their fonts and images
because GitHub shows them as <img>, which cannot load anything external.
"""

import base64
import io
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image

PORTFOLIO = Path(sys.argv[1]).resolve()
OUT = Path(__file__).resolve().parent.parent / "assets"
SITE = "https://portfolio-andrea.my.id"

INK, PAPER, WHITE, MUTED = "#111111", "#fff4de", "#fffdf7", "#5c5447"
YELLOW, BLUE, PINK = "#ffd23f", "#8fb3ff", "#ff9ec4"
TONES = [YELLOW, BLUE, PINK]
# Dark pages hide an ink shadow, so the dark variants lift the cards with paper instead.
SHADOW = {"light": INK, "dark": PAPER}

content = json.loads((PORTFOLIO / "content/portfolio.json").read_text())


# Fonts: the same faces as the site, pinned to one weight and cut to ASCII.

def font_file(family):
    for path in sorted((PORTFOLIO / ".next/static/media").glob("*.p.*.woff2")):
        if TTFont(path)["name"].getDebugName(1).startswith(family):
            return path
    sys.exit(f"{family} not found. Run `npm run build` in the portfolio first.")


class Face:
    def __init__(self, name, family, axes):
        # A fixed timestamp keeps unchanged fonts byte for byte the same between builds.
        font = instancer.instantiateVariableFont(TTFont(font_file(family), recalcTimestamp=False), axes)
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "liga"]
        subsetter = subset.Subsetter(options)
        subsetter.populate(text="".join(chr(c) for c in range(32, 127)) + "’·")
        subsetter.subset(font)
        buffer = io.BytesIO()
        font.flavor = "woff2"
        font.save(buffer)
        self.name = name
        self.data = base64.b64encode(buffer.getvalue()).decode()
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]

    def width(self, text, size, tracking=0):
        units = sum(self.hmtx[self.cmap.get(ord(c), ".notdef")][0] for c in text)
        return units * size / self.upm + tracking * size * len(text)

    def css(self):
        return f"@font-face{{font-family:{self.name};src:url(data:font/woff2;base64,{self.data}) format('woff2')}}"


DISPLAY = Face("D", "Bricolage", {"wght": 800, "opsz": 96})
BODY = Face("B", "Archivo", {"wght": 600})
BOLD = Face("BB", "Archivo", {"wght": 800})


def wrap(face, text, size, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and face.width(trial, size) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def jpeg(path, size, focus=(0.5, 0.5), background=None):
    image = Image.open(path)
    if background:
        image = image.convert("RGBA")
        base = Image.new("RGBA", image.size, background)
        base.alpha_composite(image)
        image = base
    image = image.convert("RGB")
    target = size[0] / size[1]
    w, h = image.size
    if w / h > target:
        cw, ch = round(h * target), h
    else:
        cw, ch = w, round(w / target)
    x = round((w - cw) * focus[0])
    y = round((h - ch) * focus[1])
    image = image.crop((x, y, x + cw, y + ch)).resize(size, Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=74, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def svg(width, height, title, faces, css, body):
    style = "".join(face.css() for face in faces) + css
    # Anyone who asked for less motion gets the finished frame.
    style += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title>'
        f"<style>{style}</style>{body}</svg>"
    )


def card(x, y, w, h, fill, shadow, radius=18, offset=8, stroke=3):
    return (
        f'<rect x="{x + offset}" y="{y + offset}" width="{w}" height="{h}" rx="{radius}" fill="{shadow}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{INK}" stroke-width="{stroke}"/>'
    )


def text(x, y, value, face, size, fill=INK, anchor="start", extra=""):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{face.name}" font-size="{size}" '
        f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(value)}</text>'
    )


def write(name, variant, markup):
    suffix = "" if variant == "light" else "-dark"
    path = OUT / f"{name}{suffix}.svg"
    path.write_text(markup)
    print(f"{path.relative_to(OUT.parent)}  {len(markup) // 1024} KB")


# Header: the hanging ID badge from the site, with the name, a rotating line,
# and a strip of tape listing the stack.

def header(variant):
    W, H = 880, 400
    cx, cy, cw, ch = 3, 3, 862, 384
    profile = content["profile"]
    job = content["experience"][0]
    shadow = SHADOW[variant]
    css = [
        ".drop{animation:drop .7s cubic-bezier(.3,1.5,.6,1) both}",
        "@keyframes drop{from{transform:translateY(-330px)}}",
        ".swing,.sway{transform-box:view-box;transform-origin:170px 0}",
        ".swing{animation:swing 3.4s .45s ease-in-out both}",
        "@keyframes swing{0%{transform:rotate(16deg)}12%{transform:rotate(-11deg)}25%{transform:rotate(7.5deg)}"
        "38%{transform:rotate(-4.5deg)}52%{transform:rotate(2.6deg)}66%{transform:rotate(-1.3deg)}82%{transform:rotate(.5deg)}100%{transform:rotate(0)}}",
        ".sway{animation:sway 5s 3.9s ease-in-out infinite alternate}",
        "@keyframes sway{from{transform:rotate(-1.6deg)}to{transform:rotate(1.6deg)}}",
        ".ch{transform-box:fill-box;transform-origin:50% 100%;animation:rise .7s cubic-bezier(.2,1.4,.5,1) both}",
        "@keyframes rise{from{opacity:0;transform:translateY(46px) rotate(-14deg)}}",
        ".pop{transform-box:fill-box;transform-origin:50% 50%;animation:pop .6s cubic-bezier(.3,1.6,.6,1) both}",
        "@keyframes pop{from{opacity:0;transform:scale(.4) rotate(-8deg)}}",
        ".word{opacity:0;animation:word 12s infinite both}",
        ".word.first{opacity:1}",
        "@keyframes word{0%{opacity:0;transform:translateY(34px)}3%,22%{opacity:1;transform:none}25%,100%{opacity:0;transform:translateY(-34px)}}",
        ".tape{animation:tape 30s linear infinite}",
        ".dot{transform-box:fill-box;transform-origin:50% 50%;animation:ping 1.8s ease-out infinite}",
        "@keyframes ping{from{opacity:.9;transform:scale(1)}to{opacity:0;transform:scale(2.6)}}",
    ]
    out = [card(cx, cy, cw, ch, PAPER, shadow, radius=22, offset=10)]
    out.append(f'<clipPath id="inside"><rect x="{cx + 1.5}" y="{cy + 1.5}" width="{cw - 3}" height="{ch - 3}" rx="21"/></clipPath>')
    out.append('<g clip-path="url(#inside)">')

    # Tape across the bottom, behind the badge.
    stack = ["TypeScript", "React", "Next.js", "React Native", "Expo", "Node.js", "Laravel", "Three.js", "Python", "SQL", "Tailwind CSS", "Figma"]
    size, gap = 19, 46
    items, x = [], 0
    for word in stack:
        items.append((x, word))
        x += DISPLAY.width(word, size) + gap
    run = x
    css.append(f"@keyframes tape{{to{{transform:translateX(-{run:.1f}px)}}}}")
    band_y = 318
    tape = []
    for copy in range(2):
        for start, word in items:
            px = start + copy * run
            tape.append(text(px, band_y + 29, word, DISPLAY, size))
            star_x = px + DISPLAY.width(word, size) + gap / 2
            tape.append(f'<rect x="{star_x - 5:.1f}" y="{band_y + 17}" width="10" height="10" fill="{INK}" transform="rotate(45 {star_x:.1f} {band_y + 22})"/>')
    out.append(
        f'<g transform="rotate(-2.2 440 {band_y + 22})">'
        f'<rect x="-40" y="{band_y}" width="{W + 80}" height="44" fill="{YELLOW}" stroke="{INK}" stroke-width="3"/>'
        f'<g class="tape">{"".join(tape)}</g></g>'
    )

    # Status sticker.
    status = f"Currently building at {job['company']}"
    sw = BODY.width(status, 14) + 54
    sx = cx + cw - sw - 26
    out.append(
        f'<g class="pop" style="animation-delay:1.5s"><g transform="rotate(2.5 {sx + sw / 2:.1f} 44)">'
        + card(sx, 26, sw, 36, PINK, INK, radius=18, offset=4, stroke=2.5)
        + f'<circle class="dot" cx="{sx + 22:.1f}" cy="44" r="5" fill="{INK}"/><circle cx="{sx + 22:.1f}" cy="44" r="5" fill="{INK}"/>'
        + text(sx + 36, 49, status, BODY, 14)
        + "</g></g>"
    )

    # Name and lines on the right.
    left = 316
    out.append(
        f'<g class="pop" style="animation-delay:.5s">'
        + card(left, 92, BOLD.width("Hi, I’m", 17) + 28, 34, YELLOW, INK, radius=9, offset=4, stroke=2.5)
        + text(left + 14, 115, "Hi, I’m", BOLD, 17)
        + "</g>"
    )
    name = profile["name"]
    name_size = min(58, 520 / DISPLAY.width(name, 1))
    x = left
    for i, char in enumerate(name):
        if char != " ":
            out.append(text(x, 186, char, DISPLAY, f"{name_size:.1f}", extra=f'class="ch" style="animation-delay:{0.65 + i * 0.035:.3f}s"'))
        x += DISPLAY.width(char, name_size)

    lead = "I build"
    out.append(text(left, 238, lead, BOLD, 26))
    words = ["web apps", "mobile apps", "3D websites", "browser games"]
    wx = left + BOLD.width(lead + " ", 26) + 4
    out.append(f'<clipPath id="slot"><rect x="{wx - 4}" y="204" width="300" height="50"/></clipPath><g clip-path="url(#slot)">')
    for i, word in enumerate(words):
        bw = DISPLAY.width(word, 26) + 26
        first = " first" if i == 0 else ""
        out.append(
            f'<g class="word{first}" style="animation-delay:{i * 3}s">'
            f'<rect x="{wx}" y="210" width="{bw:.1f}" height="38" rx="9" fill="{TONES[i % 3]}" stroke="{INK}" stroke-width="2.5"/>'
            + text(wx + 13, 238, word, DISPLAY, 26)
            + "</g>"
        )
    out.append("</g>")

    intro = "Frontend engineer for web and mobile, with a background in data analysis. Based in Medan, Indonesia."
    for i, line in enumerate(wrap(BODY, intro, 16, 500)):
        out.append(text(left, 280 + i * 23, line, BODY, 16, MUTED))

    # The badge, hanging from the top edge.
    photo = jpeg(PORTFOLIO / "public" / content["about"]["portrait"], (272, 272), focus=(0.5, 0.0), background=YELLOW)
    bx, by, bw, bh = 90, 74, 160, 296
    first, *rest = name.split(" ")
    badge = [
        f'<rect x="157" y="-400" width="26" height="{by + 400 - 6}" fill="{PINK}" stroke="{INK}" stroke-width="3"/>',
        card(bx, by, bw, bh, WHITE, INK, radius=16, offset=0),
        f'<rect x="150" y="{by - 18}" width="40" height="30" rx="8" fill="{BLUE}" stroke="{INK}" stroke-width="3"/>',
        f'<rect x="147" y="{by + 18}" width="46" height="9" rx="4.5" fill="{PAPER}" stroke="{INK}" stroke-width="2.5"/>',
        f'<clipPath id="photo"><rect x="{bx + 12}" y="{by + 36}" width="136" height="136" rx="11"/></clipPath>',
        f'<image href="{photo}" x="{bx + 12}" y="{by + 36}" width="136" height="136" clip-path="url(#photo)"/>',
        f'<rect x="{bx + 12}" y="{by + 36}" width="136" height="136" rx="11" fill="none" stroke="{INK}" stroke-width="2.5"/>',
        text(bx + 12, by + 194, " ".join([first] + rest[:1]), DISPLAY, 16),
        text(bx + 12, by + 213, " ".join(rest[1:]), DISPLAY, 16),
    ]
    role = job["role"]
    rw = BOLD.width(role, 11) + 14
    badge += [
        f'<rect x="{bx + 12}" y="{by + 222}" width="{rw:.1f}" height="20" rx="5" fill="{BLUE}" stroke="{INK}" stroke-width="2"/>',
        text(bx + 19, by + 236, role, BOLD, 11),
        text(bx + 12, by + 258, job["company"], BODY, 9.5, MUTED),
        f'<line x1="{bx + 12}" y1="{by + 270}" x2="{bx + bw - 12}" y2="{by + 270}" stroke="{INK}" stroke-width="2" stroke-dasharray="5 4"/>',
        text(bx + 12, by + 287, profile["location"], BOLD, 11),
    ]
    out.append(f'<g class="drop"><g class="swing"><g class="sway">{"".join(badge)}</g></g></g>')
    out.append("</g>")
    write("header", variant, svg(W, H, f"{name}, {role}", [DISPLAY, BODY, BOLD], "".join(css), "".join(out)))


# Project cards: one wide card for the first project, then a pair grid.

def project(index, item, variant, wide):
    total = len(content["projects"])
    tone = TONES[index % 3]
    shadow = SHADOW[variant]
    W, H = (880, 300) if wide else (430, 370)
    cw, ch = W - 12, H - 12
    if wide:
        ix, iy, iw, ih = 18, 18, 470, 264
        tx, ty, tw = 512, 52, 330
    else:
        ix, iy, iw, ih = 16, 16, cw - 32, 172
        tx, ty, tw = 20, 210, cw - 40
    focus = (0.5, 0.5)
    cover = item["images"][0]
    src = cover["src"] if isinstance(cover, dict) else cover
    if isinstance(cover, dict):
        focus = (cover.get("x", 50) / 100, cover.get("y", 50) / 100)
    image = jpeg(PORTFOLIO / "public" / src, (iw * 2, ih * 2), focus=focus)
    css = (
        ".zoom{transform-box:fill-box;transform-origin:50% 50%;animation:zoom 9s ease-in-out infinite alternate}"
        "@keyframes zoom{to{transform:scale(1.08)}}"
        ".play{transform-box:fill-box;transform-origin:50% 50%;animation:beat 2.4s ease-in-out infinite}"
        "@keyframes beat{0%,70%,100%{transform:scale(1)}80%{transform:scale(1.12)}90%{transform:scale(.96)}}"
    )
    out = [card(1.5, 1.5, cw, ch, tone, shadow, radius=18, offset=9)]
    out.append(f'<clipPath id="shot"><rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="11"/></clipPath>')
    out.append(f'<g clip-path="url(#shot)"><image class="zoom" href="{image}" x="{ix}" y="{iy}" width="{iw}" height="{ih}" preserveAspectRatio="xMidYMid slice"/></g>')
    out.append(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="11" fill="none" stroke="{INK}" stroke-width="2.5"/>')
    number = f"{index + 1:02d} / {total:02d}"
    nw = BOLD.width(number, 12) + 18
    out.append(f'<rect x="{ix + 10}" y="{iy + 10}" width="{nw:.1f}" height="24" rx="6" fill="{WHITE}" stroke="{INK}" stroke-width="2"/>')
    out.append(text(ix + 19, iy + 27, number, BOLD, 12))

    name_size = 30 if wide else 24
    while DISPLAY.width(item["name"], name_size) > tw and name_size > 16:
        name_size -= 1
    y = ty
    if wide:
        y += 14
    category = item["category"]
    kw = BOLD.width(category, 12) + 18
    out.append(f'<rect x="{tx}" y="{y - 2}" width="{kw:.1f}" height="22" rx="6" fill="{WHITE}" stroke="{INK}" stroke-width="2"/>')
    out.append(text(tx + 9, y + 13, category, BOLD, 12))
    y += 22 + name_size + 6
    out.append(text(tx, y, item["name"], DISPLAY, name_size))
    for line in wrap(BODY, item["title"], 14, tw)[: 3 if wide else 1]:
        y += 22
        out.append(text(tx, y, line, BODY, 14))
    if wide:
        for line in wrap(BODY, item["stack"].replace(" · ", "  ·  "), 13, tw):
            y += 26
            out.append(text(tx, y, line, BOLD, 13, MUTED))

    label = "Watch the video" if item.get("video") else "See the project"
    lw = BOLD.width(label, 14) + 54
    lx, ly = (tx, ch - 62) if wide else (cw - lw - 20, ch - 56)
    if not wide:
        stack = item["stack"].split(" · ")
        shown = []
        for tech in stack:
            if BODY.width("  ·  ".join(shown + [tech]), 12.5) > lx - tx - 14:
                break
            shown.append(tech)
        out.append(text(tx, ly + 24, "  ·  ".join(shown), BOLD, 12.5, MUTED))
    out.append(
        f'<g class="play">'
        + card(lx, ly, lw, 38, INK, WHITE if variant == "light" else INK, radius=10, offset=0)
        + f'<path d="M{lx + 17} {ly + 12}l11 7-11 7z" fill="{tone}"/>'
        + text(lx + 38, ly + 24, label, BOLD, 14, WHITE)
        + "</g>"
    )
    write(f"project-{item['id']}", variant, svg(W, H, f"{item['name']}: {item['title']}", [DISPLAY, BODY, BOLD], css, "".join(out)))


# Toolbox: the same three groups as the site, with chips that pop in.

def toolbox(variant):
    groups = content["about"]["skills"]
    W, gap = 880, 18
    col = (W - 12 - gap * (len(groups) - 1)) / len(groups)
    layouts, tallest = [], 0
    for group in groups:
        chips, x, y = [], 0, 0
        for tech in group["value"].split(" · "):
            w = BOLD.width(tech, 13) + 22
            if x and x + w > col - 32:
                x, y = 0, y + 38
            chips.append((x, y, w, tech))
            x += w + 8
        layouts.append(chips)
        tallest = max(tallest, y + 30)
    H = 60 + tallest + 30
    css = (
        ".chip{transform-box:fill-box;transform-origin:50% 50%;animation:pop .5s cubic-bezier(.3,1.7,.6,1) both}"
        "@keyframes pop{from{opacity:0;transform:scale(.3) rotate(-10deg)}}"
    )
    out = []
    for i, (group, chips) in enumerate(zip(groups, layouts)):
        gx = i * (col + gap)
        out.append(card(gx + 1.5, 1.5, col, H - 12, TONES[i % 3], SHADOW[variant], radius=16, offset=8))
        out.append(text(gx + 18, 38, group["label"], DISPLAY, 22))
        for k, (x, y, w, tech) in enumerate(chips):
            delay = 0.3 + i * 0.25 + k * 0.06
            out.append(
                f'<g class="chip" style="animation-delay:{delay:.2f}s">'
                f'<rect x="{gx + 18 + x:.1f}" y="{56 + y}" width="{w:.1f}" height="28" rx="7" fill="{WHITE}" stroke="{INK}" stroke-width="2"/>'
                + text(gx + 18 + x + 11, 56 + y + 19, tech, BOLD, 13)
                + "</g>"
            )
    title = "Toolbox: " + "; ".join(f"{g['label']}: {g['value'].replace(' · ', ', ')}" for g in groups)
    write("toolbox", variant, svg(W, H, title, [DISPLAY, BOLD], css, "".join(out)))


# Contact buttons. Each one is its own image so each can carry its own link.

def button(name, label, tone, variant, primary=False):
    w = BOLD.width(label, 17) + (70 if primary else 44)
    W, H = round(w + 10), 62
    css = ".arrow{animation:nudge 2.2s ease-in-out infinite}@keyframes nudge{0%,60%,100%{transform:none}75%{transform:translate(4px,-4px)}}"
    out = [card(1.5, 1.5, w, 50, tone, SHADOW[variant], radius=12, offset=6, stroke=3)]
    out.append(text(22, 33, label, BOLD, 17))
    if primary:
        ax = w - 36
        out.append(
            f'<g class="arrow"><path d="M{ax} 34L{ax + 14} 20M{ax + 4} 19H{ax + 15}V30" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g>'
        )
    write(f"button-{name}", variant, svg(W, H, label, [BOLD], css if primary else "", "".join(out)))


OUT.mkdir(exist_ok=True)
for variant in ("light", "dark"):
    header(variant)
    for i, item in enumerate(content["projects"]):
        project(i, item, variant, wide=i == 0)
    toolbox(variant)
    button("portfolio", "Visit my portfolio", YELLOW, variant, primary=True)
    button("email", "Email", WHITE, variant)
    button("linkedin", "LinkedIn", BLUE, variant)
    button("instagram", "Instagram", PINK, variant)
    button("cv", "CV", WHITE, variant)
