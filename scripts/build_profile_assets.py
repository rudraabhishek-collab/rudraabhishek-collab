#!/usr/bin/env python3
"""Build the static monochrome SVGs for the profile README (no network needed).
Run once, or whenever you edit the text below:  python3 scripts/build_profile_assets.py
Outputs (repo root): header.svg about.svg stack.svg badge-linkedin.svg badge-github.svg badge-email.svg
"""
from xml.sax.saxutils import escape

BG, FG, DIM, LINE = "#0b0b0b", "#d4d4d4", "#777777", "#333333"
FONT = "JetBrains Mono,DejaVu Sans Mono,Menlo,Consolas,monospace"
CW = 0.6  # monospace glyph width as a fraction of font size


def svg(w, h, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(title)}">\n<rect width="{w}" height="{h}" fill="{BG}"/>\n'
            f'<g font-family="{FONT}" font-size="12">\n{body}\n</g>\n</svg>\n')


def t(x, y, s, size=12, fill=FG, weight="normal", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'xml:space="preserve" {extra}>{escape(s)}</text>')


def save(name, content):
    with open(name, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("wrote", name)


# ---------------------------------------------------------------- header (typing loop)
def header():
    lines = ["Hi, I'm Rudraabhishek Sharma",
             "Aspiring AI Engineer",
             "Open Source Contributor · CSE Student"]
    W, H, size = 760, 96, 24
    n, dur = len(lines), 4.0 * len(lines)
    body = [t(380, 22, "~/rudraabhishek-collab  $  whoami", 10, DIM, extra='text-anchor="middle"')]
    for k, s in enumerate(lines):
        tw = len(s) * size * CW
        x = (W - tw) / 2
        y = 66
        a, b, c, d = k / n, (k + 0.40) / n, (k + 0.80) / n, (k + 0.95) / n  # type, hold, erase
        kt = sorted({0, a, b, c, d, 1})
        def val(p):
            if p <= a: return 0
            if p <= b: return tw * (p - a) / (b - a)
            if p <= c: return tw
            if p <= d: return tw * (1 - (p - c) / (d - c))
            return 0
        vals = ";".join(f"{val(p):.1f}" for p in kt)
        kts = ";".join(f"{p:.4f}" for p in kt)
        body.append(f'<clipPath id="h{k}"><rect x="{x:.1f}" y="36" width="0" height="42">'
                    f'<animate attributeName="width" values="{vals}" keyTimes="{kts}" dur="{dur}s" repeatCount="indefinite"/></rect></clipPath>')
        body.append(f'<g clip-path="url(#h{k})">' + t(x, y, s, size, FG, "bold", f'textLength="{tw:.1f}" lengthAdjust="spacing"') + '</g>')
        # block cursor that follows the typed text
        cx = ";".join(f"{x + val(p):.1f}" for p in kt)
        op = ";".join("1" if (a <= p < d - 1e-9) else "0" for p in kt)
        body.append(f'<rect y="42" width="10" height="26" fill="{FG}" opacity="0"><animate attributeName="x" values="{cx}" keyTimes="{kts}" dur="{dur}s" repeatCount="indefinite"/>'
                    f'<animate attributeName="opacity" values="{op}" keyTimes="{kts}" dur="{dur}s" calcMode="discrete" repeatCount="indefinite"/></rect>')
    body.append(f'<line x1="24" y1="{H-4}" x2="{W-24}" y2="{H-4}" stroke="{LINE}"/>')
    save("header.svg", svg(W, H, "Rudraabhishek Sharma - typing intro", "\n".join(body)))


# ---------------------------------------------------------------- about card
def about():
    W, H = 760, 232
    code = [
        ("const", "rudra", " = {"),
        None,
    ]
    rows = [
        '  location: "Pune, Maharashtra, India",',
        '  education: "B.Tech CSE · PW IOI, Pune",',
        '  currentRole: "Frontend AI Eng. Intern",',
        '  focus: [',
        '    "AI / LLM Applications",',
        '    "Frontend (React, Next.js)",',
        '    "Open Source",',
        '  ],',
        '  funFact: "Building in public.",',
    ]
    b = [f'<rect x="16" y="16" width="{W-32}" height="{H-32}" rx="6" fill="none" stroke="{LINE}"/>',
         f'<line x1="372" y1="16" x2="372" y2="{H-16}" stroke="{LINE}"/>',
         t(32, 42, "const rudra = {", 11, FG, "bold")]
    for i, r in enumerate(rows):
        b.append(t(32, 62 + i * 15, r, 10.5, FG if i % 2 == 0 else "#a8a8a8"))
    b.append(t(32, 62 + len(rows) * 15, "};", 11, FG, "bold"))
    bullets = [
        "B.Tech CSE student, PW Institute of Innovation",
        "Frontend AI Engineering Intern, FlyRank AI",
        "Graphic Design Intern, Elite Coders Community",
        "ECSoc 2026 contributor · rank 97 of ~3,000",
        "AI for Sustainability intern, 1M1B x IBM SkillsBuild",
        "Exploring generative AI, NLP & LLM applications",
        "Core Member, Sports Club",
    ]
    for i, s in enumerate(bullets):
        y = 44 + i * 25
        b.append(f'<rect x="392" y="{y-8}" width="6" height="6" fill="{FG}"/>')
        b.append(t(408, y, s, 10.5))
    save("about.svg", svg(W, H, "About me", "\n".join(b)))


# ---------------------------------------------------------------- tech stack
def stack():
    groups = [
        ("FRONTEND", ["HTML", "CSS", "JavaScript", "React", "Next.js", "Tailwind CSS", "Bootstrap", "REST APIs"]),
        ("LANGUAGES", ["Java", "Python", "C", "C++", "SQL"]),
        ("AI", ["Generative AI", "LLM Apps", "NLP", "Prompt Engineering", "Responsible AI"]),
        ("TOOLS", ["Git", "GitHub", "MySQL", "Prisma", "AI-assisted Dev"]),
    ]
    W, fs, gap, pad = 760, 11, 8, 12
    y, b = 30, []
    for name, items in groups:
        b.append(t(W / 2, y, name, 10, DIM, extra='text-anchor="middle"'))
        widths = [len(s) * fs * CW + pad * 2 for s in items]
        x = (W - (sum(widths) + gap * (len(items) - 1))) / 2
        for s, w in zip(items, widths):
            b.append(f'<rect x="{x:.1f}" y="{y+10}" width="{w:.1f}" height="24" rx="4" fill="none" stroke="{FG}"/>')
            b.append(t(x + w / 2, y + 26, s, fs, FG, extra='text-anchor="middle"'))
            x += w + gap
        y += 62
    save("stack.svg", svg(W, y - 10, "Tech stack", "\n".join(b)))


# ---------------------------------------------------------------- connect badges
def badge(name, label):
    w = len(label) * 11 * CW + 36
    body = (f'<rect x="1" y="1" width="{w-2:.1f}" height="30" rx="4" fill="{FG}"/>'
            + t(w / 2, 21, label, 11, "#0b0b0b", "bold", 'text-anchor="middle" letter-spacing="1"'))
    save(f"badge-{name}.svg", f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="32" viewBox="0 0 {w:.0f} 32" role="img" aria-label="{label}">\n<g font-family="{FONT}">{body}</g>\n</svg>\n')


if __name__ == "__main__":
    header(); about(); stack()
    badge("linkedin", "LINKEDIN"); badge("github", "GITHUB"); badge("email", "EMAIL")
