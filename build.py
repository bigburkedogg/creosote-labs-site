#!/usr/bin/env python3
"""Build the Creosote Labs site.

content/  (JSON pages, Markdown posts)  +  assets/  ->  docs/  (the published folder)

Standard library only. Run: /opt/homebrew/bin/python3 build.py
"""
import datetime
import html
import json
import re
import shutil
import sys
from email.utils import format_datetime
from pathlib import Path

if sys.version_info < (3, 12):
    sys.exit("build.py needs Python 3.12 or newer (use /opt/homebrew/bin/python3)")

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"
PAGES = CONTENT / "pages"
WRITING = CONTENT / "writing"

# The Creosote Labs mark, copied from the proposals design system
# (assets/marks/creosote_labs_mark_*.svg). Strokes and dots are heavier than in the
# original so it stays legible at header size, and it takes the text colour of its
# container instead of a fixed fill.
MARK = ('<svg viewBox="-120 -120 240 240" aria-hidden="true" focusable="false"><g stroke="currentColor" stroke-width="9" '
        'stroke-linecap="round" fill="none"><path d="M0 85.5V-95"/><path d="M0-55-55-90"/><path d="M0-55 55-90"/>'
        '<path d="M0-10-65-33"/><path d="M0-10 65-33"/><path d="M0 33-57 15"/><path d="M0 33 57 15"/>'
        '<path d="M0 70-38 60"/><path d="M0 70 38 60"/></g><g fill="currentColor"><circle cx="0" cy="-95" r="10"/>'
        '<circle cx="-55" cy="-90" r="8"/><circle cx="55" cy="-90" r="8"/><circle cx="-65" cy="-33" r="8"/>'
        '<circle cx="65" cy="-33" r="8"/><circle cx="-57" cy="15" r="8"/><circle cx="57" cy="15" r="8"/>'
        '<circle cx="-38" cy="60" r="7"/><circle cx="38" cy="60" r="7"/></g>'
        '<circle cx="0" cy="95" r="11" fill="none" stroke="currentColor" stroke-width="8"/></svg>')

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..600'
         '&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">')

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")

OFFSITE = ("http://", "https://", "mailto:", "tel:", "data:", "//")

# Old paths that now live elsewhere: each is written as a small noindex page that
# forwards to the new one, keeping any #fragment, so existing links keep working.
ALIASES = {"projects.html": "systems.html"}


def jload(path):
    return json.loads(Path(path).read_text())


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def filled(s):
    return bool((s or "").strip()) if isinstance(s, str) else bool(s)


def placeholder(label):
    """The yellow marker for copy that is still to be written. Loud on purpose."""
    return f'<span class="placeholder">Placeholder — {esc(label)}</span>'


def num(n):
    return f"{n:02d}"


# ---------------------------------------------------------------- markdown
# A deliberately small subset: ## / ### headings, paragraphs, - and 1. lists,
# > blockquotes, ``` fences, --- rules, **bold**, *italic*, `code`,
# [label](url), and [[placeholder]], which renders as a yellow placeholder chip.
# Posts use all of it; JSON copy uses the inline part (see Site.inline).
def _emph(s):
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<em>\1</em>", s)
    return s


def md_inline(text):
    tokens = []

    def put(fragment):
        tokens.append(fragment)
        return f"\x00{len(tokens) - 1}\x00"

    # Code spans come out of the raw text first so nothing else touches them.
    text = re.sub(r"`([^`\n]+)`",
                  lambda m: put(f'<code class="mono">{html.escape(m.group(1), quote=True)}</code>'), text)
    out = html.escape(text, quote=True)
    out = re.sub(r"\[\[(.+?)\]\]",
                 lambda m: put(f'<span class="placeholder">Placeholder — {_emph(m.group(1))}</span>'), out)
    out = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)",
                 lambda m: put(f'<a href="{m.group(2)}">{_emph(m.group(1))}</a>'), out)
    out = _emph(out)
    for i in range(len(tokens) - 1, -1, -1):  # descending: a link token can hold a code token
        out = out.replace(f"\x00{i}\x00", tokens[i])
    return out


def md(text):
    lines = (text or "").replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append(f"<p>{md_inline(' '.join(para).strip())}</p>")
            para.clear()

    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("```"):
            flush()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append('<pre class="mono"><code>' + html.escape("\n".join(buf), quote=True) + "</code></pre>")
            continue
        if not s:
            flush()
            i += 1
            continue
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        head = re.match(r"(#{2,6})\s+(.*)", s)
        if head:
            flush()
            level = min(len(head.group(1)), 3)
            out.append(f"<h{level}>{md_inline(head.group(2))}</h{level}>")
            i += 1
            continue
        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote><p>{md_inline(' '.join(buf))}</p></blockquote>")
            continue
        ordered = bool(re.match(r"\d+[.)]\s+", s))
        if ordered or re.match(r"[-*]\s+", s):
            flush()
            items = []
            while i < len(lines):
                t = lines[i].strip()
                if ordered and re.match(r"\d+[.)]\s+", t):
                    items.append(re.sub(r"^\d+[.)]\s+", "", t))
                elif not ordered and re.match(r"[-*]\s+", t):
                    items.append(re.sub(r"^[-*]\s+", "", t))
                elif t and items and lines[i][:1] in (" ", "\t"):
                    items[-1] += " " + t  # continuation of the previous item
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{md_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para.append(s)
        i += 1
    flush()
    return "\n".join(out)


# ---------------------------------------------------------------- posts
def front_matter(text):
    """Split a leading --- ... --- block of `key: value` lines off the body."""
    meta = {}
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for line in lines[1:j]:
                    if not line.strip() or line.lstrip().startswith("#"):
                        continue
                    k, sep, v = line.partition(":")
                    if sep:
                        meta[k.strip().lower()] = v.strip()
                return meta, "\n".join(lines[j + 1:])
    return meta, text


def show_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def post_path(post):
    return f'writing/{post["slug"]}/index.html'


def load_posts():
    """Every .md file in content/writing/, newest first."""
    posts = []
    if not WRITING.exists():
        return posts
    for f in sorted(WRITING.glob("*.md")):
        meta, body = front_matter(f.read_text())
        m = re.match(r"(\d{4}-\d{2}-\d{2})[-_](.+)", f.stem)
        date = meta.get("date", "") or (m.group(1) if m else "")
        slug = meta.get("slug", "") or (m.group(2) if m else f.stem)
        slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
        if not filled(date):
            print(f"  note: {f.name} has no date (front-matter `date:` or a YYYY-MM-DD- filename)")
        posts.append({
            "file": f.name,
            "slug": slug,
            "date": date,
            "shown": show_date(date),
            "title": meta.get("title", "") or slug.replace("-", " "),
            "standfirst": meta.get("standfirst", ""),
            "canonical": meta.get("canonical", ""),
            "draft": meta.get("draft", "").strip().lower() in ("true", "yes", "1"),
            "body": body,
        })
    by_slug = {}
    for p in posts:
        by_slug.setdefault(p["slug"], []).append(p["file"])
    for slug, files in by_slug.items():
        if len(files) > 1:
            print(f"  note: slug '{slug}' is claimed by {', '.join(files)} — one will overwrite the other")
    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return posts


# ---------------------------------------------------------------- site
class Site:
    def __init__(self):
        self.cfg = jload(CONTENT / "site.json")
        self.bp = self.cfg.get("base_path", "").rstrip("/")
        self.base_url = self.cfg.get("base_url", "").rstrip("/")
        self.pages_out = []  # (path, include_in_sitemap)
        self.planned = set()  # every page this build will write, for link checking
        self.has_feed = False

    def url(self, path):
        if not path:
            return ""
        if path.startswith(OFFSITE + ("#",)):
            return path
        return f"{self.bp}/{path.lstrip('/')}"

    def abs(self, path):
        return f"{self.base_url}{self.url(path)}"

    def href(self, path):
        """Link form of a path: a directory index links to the directory."""
        return self.url(path).removesuffix("index.html")

    def label_for(self, path, default):
        """The nav label of a page, so links elsewhere call it by the same name."""
        return next((n.get("label") for n in self.cfg.get("nav", []) if n.get("href") == path), default)

    # ---- links ----
    def link_ok(self, href):
        """True for external and anchor links, and for internal links this build writes."""
        if not filled(href):
            return False
        if href.startswith(OFFSITE + ("#",)):
            return True
        target = href.split("#")[0].split("?")[0].lstrip("/")
        if target == "" or target.endswith("/"):
            target += "index.html"
        return target in self.planned

    def dead_links(self):
        out = []
        for key in ("nav", "footer_links"):
            for item in self.cfg.get(key, []):
                if not self.link_ok(item.get("href")):
                    out.append(f'site.json {key}: "{item.get("label")}" -> {item.get("href")}')
        c = self.cfg.get("contact") or {}
        if filled(c.get("link_href")) and not self.link_ok(c.get("link_href")):
            out.append(f'site.json contact: "{c.get("link_label")}" -> {c.get("link_href")}')
        return out

    # ---- copy ----
    def inline(self, text):
        """One line of JSON copy: inline Markdown, with internal links given the base path."""
        def fix(m):
            ref = html.unescape(m.group(1))
            return m.group(0) if ref.startswith(OFFSITE + ("#",)) else f'href="{esc(self.url(ref))}"'
        return re.sub(r'href="([^"]*)"', fix, md_inline((text or "").strip()))

    def rich(self, text, cls=""):
        """A block of JSON copy: a blank line starts a new paragraph."""
        c = f' class="{cls}"' if cls else ""
        return "".join(f"<p{c}>{self.inline(p)}</p>" for p in re.split(r"\n\s*\n", text or "") if p.strip())

    # ---- shared chrome ----
    def header(self, current):
        links = "".join(
            f'<a href="{self.url(n["href"])}"{" aria-current=\"page\"" if n["href"] == current else ""}>{esc(n["label"])}</a>'
            for n in self.cfg.get("nav", []) if self.link_ok(n.get("href")))
        cta = (f'<a class="btn btn-small" href="{self.url(self.cfg["cta_href"])}">{esc(self.cfg["cta_label"])}</a>'
               if filled(self.cfg.get("cta_label")) and self.link_ok(self.cfg.get("cta_href")) else "")
        brand = esc(self.cfg["brand"])
        return (f'<header class="site-header"><div class="wrap bar">'
                f'<a class="wordmark" href="{self.href("index.html")}" aria-label="{brand} home">{MARK}'
                f'<span>{brand}</span></a>'
                f'<nav class="nav" aria-label="Main">{links}{cta}</nav>'
                f'</div></header>')

    def contact_line(self):
        bits = []
        if filled(self.cfg.get("phone")):
            bits.append(f'<a href="tel:{esc(self.cfg.get("phone_tel", self.cfg["phone"]))}">{esc(self.cfg["phone"])}</a>')
        if filled(self.cfg.get("email")):
            bits.append(f'<a href="mailto:{esc(self.cfg["email"])}">{esc(self.cfg["email"])}</a>')
        return " · ".join(bits)

    def footer(self):
        items = self.cfg.get("footer_links") or self.cfg.get("nav", [])
        links = "".join(f'<a href="{self.url(n["href"])}">{esc(n["label"])}</a>'
                        for n in items if self.link_ok(n.get("href")))
        if self.has_feed:
            links += f'<a href="{self.url("feed.xml")}">RSS</a>'
        brand = esc(self.cfg["brand"])
        year = datetime.date.today().year
        contact = self.contact_line()
        return (f'<footer class="site-footer"><div class="wrap foot">'
                f'<p class="foot-brand">{MARK}<span>{brand}</span></p>'
                f'<nav class="foot-nav" aria-label="Footer">{links}</nav>'
                f'<p class="foot-meta">{contact + "<br>" if contact else ""}© {year} {brand}</p>'
                f'</div></footer>')

    def band(self, number=""):
        """The closing invitation. Plain by design: no pricing, no scheduler, no urgency."""
        c = self.cfg.get("contact") or {}
        if not filled(c.get("heading")) and not filled(c.get("text")):
            return ""
        link = ""
        if filled(c.get("link_label")) and self.link_ok(c.get("link_href")):
            link = (f'<p class="actions"><a class="btn" href="{self.url(c["link_href"])}">'
                    f'{esc(c["link_label"])}</a></p>')
        line = self.contact_line()
        contact = f'<p class="band-contact">{line}</p>' if line else ""
        return section(number, c.get("heading", ""), self.rich(c.get("text", "")) + link + contact,
                       sid="contact", cls="band")

    def page(self, *, path, title, meta, body, current=None, head="", canonical=None, index=True):
        href = canonical if filled(canonical) else (self.base_url + self.href(path))
        feed = (f'<link rel="alternate" type="application/rss+xml" title="{esc(self.cfg["brand"])}" '
                f'href="{self.url("feed.xml")}">\n' if self.has_feed else "")
        robots = '<meta name="robots" content="noindex">\n' if not index else ""
        doc = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(meta)}">\n'
               f'{robots}<link rel="canonical" href="{esc(href)}">\n{feed}'
               f'<link rel="icon" href="{self.url("favicon.svg")}" type="image/svg+xml">\n'
               f'<meta name="theme-color" content="#faf6ee" media="(prefers-color-scheme: light)">\n'
               f'<meta name="theme-color" content="#0f1a11" media="(prefers-color-scheme: dark)">\n'
               f'{FONTS}\n<link rel="stylesheet" href="{self.url("styles.css")}">\n{head}</head>\n<body>\n'
               f'{self.header(current)}\n<main id="main">\n{body}\n</main>\n{self.footer()}\n'
               f'<script src="{self.url("site.js")}"></script>\n</body>\n</html>\n')
        out = DOCS / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc)
        self.pages_out.append((path, index))

    def redirect(self, path, target):
        """A moved page: a noindex stub that forwards to `target`, keeping any #fragment."""
        to = self.url(target)
        name = self.label_for(target, target)
        doc = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               f'<title>{esc(name)} · {esc(self.cfg["brand"])}</title>\n'
               f'<meta name="robots" content="noindex">\n'
               f'<link rel="canonical" href="{esc(self.base_url + self.href(target))}">\n'
               f'<meta http-equiv="refresh" content="0; url={esc(to)}">\n'
               f'<script>location.replace({json.dumps(to)} + location.hash);</script>\n'
               f'<style>body{{margin:0;padding:24px 16px;font:16px/1.6 system-ui,sans-serif;'
               f'background:#faf6ee;color:#0f1a11}}a{{color:#1f3324}}</style>\n</head>\n<body>\n'
               f'<p>This page has moved to <a href="{esc(to)}">{esc(name)}</a>.</p>\n</body>\n</html>\n')
        (DOCS / path).write_text(doc)


# ---------------------------------------------------------------- shared blocks
def section(number, title, inner, *, sid="", cls=""):
    """A numbered section. On wide screens the number sits in the left rail."""
    rail = f'<p class="sec-num">{esc(number)}</p>' if filled(number) else ""
    head = f'<h2 class="sec-title">{esc(title)}</h2>' if filled(title) else ""
    ident = f' id="{esc(sid)}"' if filled(sid) else ""
    return (f'<section class="{esc(("sec " + cls).strip())}"{ident}><div class="wrap grid">'
            f'<div class="rail">{rail}</div><div class="main">{head}{inner}</div></div></section>')


def page_title(h1, lead="", eyebrow=""):
    """The top of every page but the home page. An eyebrow that only repeats the h1 is dropped."""
    eb = ""
    if filled(eyebrow) and eyebrow.strip().lower() != (h1 or "").strip().lower():
        eb = f'<p class="eyebrow">{esc(eyebrow)}</p>'
    ld = f'<p class="lead">{esc(lead)}</p>' if filled(lead) else ""
    return (f'<div class="page-title"><div class="wrap grid"><div class="rail"></div>'
            f'<div class="main">{eb}<h1>{esc(h1)}</h1>{ld}</div></div></div>')


def system_card(site, s, *, full):
    """A system as a card: status line, name, then either the full write-up or a summary."""
    status = f'<p class="status">{esc(s["status"])}</p>' if filled(s.get("status")) else ""
    name = esc(s.get("name", ""))
    if full:
        ident = f' id="{esc(s["id"])}"' if filled(s.get("id")) else ""
        detail = f'<p class="detail">{site.inline(s["detail"])}</p>' if filled(s.get("detail")) else ""
        visit = (f'<p class="visit"><a href="{esc(s["href"])}">Visit {name}</a></p>'
                 if filled(s.get("href")) else "")
        return (f'<li class="card"{ident}>{status}<h3>{name}</h3>'
                f'<div class="card-text">{site.rich(s.get("text", ""))}</div>{detail}{visit}</li>')
    target = site.url("systems.html") + (f'#{s["id"]}' if filled(s.get("id")) else "")
    summary = s.get("summary") if filled(s.get("summary")) else s.get("text", "")
    return (f'<li class="card card-link">{status}<h3><a href="{esc(target)}">{name}</a></h3>'
            f'<p>{site.inline(summary)}</p><p class="more" aria-hidden="true">Read more</p></li>')


def system_groups(d):
    """systems.json holds groups of systems; a flat `systems` list also works."""
    if d.get("groups"):
        return d["groups"]
    return [{"heading": "", "systems": d.get("systems") or []}]


def all_systems(d):
    return [s for g in system_groups(d) for s in g.get("systems") or []]


def post_list(site, posts, heading="h3"):
    """The notes index: date in mono on the left, title and standfirst on the right."""
    rows = ""
    for p in posts:
        date = (f'<time datetime="{esc(p["date"])}">{esc(p["date"])}</time>'
                if filled(p["shown"]) else placeholder("date"))
        if p["draft"]:
            date += ' <span class="tag">Draft</span>'
        stand = f'<p class="stand">{esc(p["standfirst"])}</p>' if filled(p["standfirst"]) else ""
        rows += (f'<li class="note"><p class="date">{date}</p><div class="note-main">'
                 f'<{heading} class="note-title"><a href="{site.href(post_path(p))}">{esc(p["title"])}</a></{heading}>'
                 f'{stand}</div></li>')
    return f'<ul class="notes">{rows}</ul>'


def more_link(site, label, href):
    if not (filled(label) and site.link_ok(href)):
        return ""
    return f'<p class="more-link"><a href="{site.url(href)}">{esc(label)}</a></p>'


# ---------------------------------------------------------------- pages
def build_home(site, d, posts, systems):
    """The description, the four areas, six systems, the latest notes, and the invitation."""
    h = d.get("hero") or {}
    lead = f'<p class="lead">{esc(h["sub"])}</p>' if filled(h.get("sub")) else ""
    body = [f'<section class="hero"><div class="wrap grid"><div class="rail"></div><div class="main">'
            f'<h1>{esc(h.get("h1") or site.cfg["brand"])}</h1>{lead}</div></div></section>']
    n = 0

    areas = [a for a in d.get("areas") or [] if filled(a.get("name"))]
    if areas:
        n += 1
        items = "".join(f'<li class="area"><p class="area-num">{n}.{i}</p><h3>{esc(a["name"])}</h3>'
                        f'{site.rich(a.get("text", ""))}</li>' for i, a in enumerate(areas, 1))
        body.append(section(num(n), d.get("areas_heading", "What we work on"),
                            f'<ol class="areas">{items}</ol>', sid="areas"))

    by_id = {s.get("id"): s for s in systems if filled(s.get("id")) and filled(s.get("name"))}
    wanted = d.get("systems_featured") or []
    for key in wanted:
        if key not in by_id:
            print(f"  note: home.json features system id '{key}', which systems.json does not define")
    featured = [by_id[key] for key in wanted if key in by_id]
    if featured:
        n += 1
        cards = "".join(system_card(site, s, full=False) for s in featured)
        body.append(section(num(n), d.get("systems_heading", "Systems"),
                            f'<ul class="cards cards-3">{cards}</ul>'
                            + more_link(site, d.get("systems_link_label"), d.get("systems_link_href")),
                            sid="systems"))

    if "writing.html" in site.planned:
        n += 1
        live = [p for p in posts if not p["draft"]][: int(d.get("notes_count", 3) or 3)]
        listing = post_list(site, live) if live else \
            f'<p class="empty">{esc(d.get("notes_empty_text", "Nothing published yet."))}</p>'
        body.append(section(num(n), d.get("notes_heading", "Notes"),
                            listing + more_link(site, d.get("notes_link_label"), d.get("notes_link_href")),
                            sid="notes"))

    body.append(site.band(num(n + 1)))
    site.page(path="index.html", title=d.get("title", site.cfg["brand"]),
              meta=d.get("meta_description", site.cfg.get("meta_description", "")),
              body="\n".join(body), current="index.html")


def build_systems(site, d):
    body = [page_title(d.get("h1", "Systems"), d.get("intro", ""), d.get("eyebrow", ""))]
    seen, n = set(), 0
    for g in system_groups(d):
        items = []
        for s in g.get("systems") or []:
            if not filled(s.get("name")):
                print(f"  note: systems.json has an entry with no name in '{g.get('heading', '')}' — skipped")
                continue
            if filled(s.get("id")):
                if s["id"] in seen:
                    print(f"  note: systems.json uses the id '{s['id']}' twice — links will reach the first")
                seen.add(s["id"])
            items.append(s)
        if not items:
            continue
        n += 1
        intro = f'<p class="sec-intro">{esc(g["intro"])}</p>' if filled(g.get("intro")) else ""
        cards = "".join(system_card(site, s, full=True) for s in items)
        body.append(section(num(n), g.get("heading", ""), f'{intro}<ul class="cards cards-2">{cards}</ul>',
                            sid=g.get("id", "")))
    body.append(site.band())
    site.page(path="systems.html", title=d.get("title", "Systems"),
              meta=d.get("meta_description", ""), body="\n".join(body), current="systems.html")


def build_about(site, d):
    body = [page_title(d.get("h1", "About"), d.get("lead", ""), d.get("eyebrow", ""))]
    n = 0
    for s in d.get("sections") or []:
        if not (filled(s.get("heading")) or filled(s.get("text"))):
            continue
        n += 1
        body.append(section(num(n), s.get("heading", ""), f'<div class="prose">{site.rich(s.get("text", ""))}</div>'))
    if filled(d.get("leadership")):
        # leadership_sentence is Brian's to write; until he does, the page says so in yellow.
        extra = (site.inline(d["leadership_sentence"]) if filled(d.get("leadership_sentence"))
                 else placeholder("one sentence from Brian"))
        body.append(section("", "", f'<div class="prose"><p>{site.inline(d["leadership"])} {extra}</p></div>',
                            cls="sec-quiet"))
    site.page(path="about.html", title=d.get("title", "About"),
              meta=d.get("meta_description", ""), body="\n".join(body), current="about.html")


def build_contact_page(site, d):
    f = d.get("form") or {}
    fields = ""
    for fld in f.get("fields") or []:
        name, label = esc(fld.get("name", "")), esc(fld.get("label", ""))
        req = " required" if fld.get("required") else ""
        auto = {"name": ' autocomplete="name"', "email": ' autocomplete="email"'}.get(fld.get("name", ""), "")
        if fld.get("type") == "textarea":
            control = f'<textarea id="f-{name}" name="{name}" rows="6"{req}></textarea>'
        else:
            control = f'<input id="f-{name}" name="{name}" type="{esc(fld.get("type", "text"))}"{auto}{req}>'
        fields += f'<p class="field"><label for="f-{name}">{label}</label>{control}</p>'
    action = f.get("action", "")
    if filled(action):
        note, disabled, act = "", "", f' action="{esc(action)}"'
    else:
        note = ('<p class="form-note">' + placeholder(
            "form endpoint not set. Put one in content/pages/work-with-us.json at form.action; "
            "until then, the email address below is the working route.") + "</p>")
        disabled, act = " disabled", ""
    form = (f'<form class="form" method="{esc(f.get("method", "post"))}"{act} '
            f'data-success="{esc(f.get("success_text", ""))}" data-error="{esc(f.get("error_text", ""))}">'
            f'{fields}<p class="actions"><button class="btn" type="submit"{disabled}>'
            f'{esc(f.get("submit_label", "Send"))}</button></p></form>') if fields else ""
    fallback = site.inline(d["fallback"]) if filled(d.get("fallback")) else site.contact_line()
    inner = (f'<div class="prose">{site.rich(d.get("intro", ""))}</div>{note}{form}'
             + (f'<p class="fallback">{fallback}</p>' if fallback else ""))
    body = page_title(d.get("h1", "Work with us"), d.get("lead", ""), d.get("eyebrow", "")) + section("", "", inner)
    site.page(path="work-with-us.html", title=d.get("title", "Work with us"),
              meta=d.get("meta_description", ""), body=body, current="work-with-us.html")


# ---------------------------------------------------------------- notes
def build_writing_index(site, d, posts):
    listing = post_list(site, posts, "h2") if posts else \
        f'<p class="empty">{esc(d.get("empty_text", "Nothing published yet."))}</p>'
    feed_line = f'<p class="more-link"><a href="{site.url("feed.xml")}">RSS feed</a></p>' if site.has_feed else ""
    subscribe = ""
    if filled(d.get("subscribe_action")):
        subscribe = section("", d.get("subscribe_heading", "Subscribe"), (
            f'<p class="sec-intro">{esc(d.get("subscribe_text", ""))}</p>'
            f'<form class="signup" action="{esc(d["subscribe_action"])}" method="post">'
            f'<input type="email" name="email" placeholder="Email address" aria-label="Email address" autocomplete="email" required>'
            f'<button class="btn" type="submit">{esc(d.get("subscribe_button_label", "Subscribe"))}</button></form>'))
    body = (page_title(d.get("h1", "Notes"), d.get("sub", ""), d.get("eyebrow", ""))
            + section("", "", listing + feed_line, cls="sec-list") + subscribe + site.band())
    site.page(path="writing.html", title=d.get("title", f'Notes · {site.cfg["brand"]}'),
              meta=d.get("meta_description", ""), body=body, current="writing.html")


def build_post(site, p):
    banner = ('<p class="draft-banner">Draft: scaffolding, not a finished post. Replace it or finish it, then set '
              '<code class="mono">draft: false</code> in the front matter.</p>') if p["draft"] else ""
    source = ""
    if filled(p["canonical"]):
        host = re.sub(r"^https?://(www\.)?", "", p["canonical"]).split("/")[0]
        source = f'<p class="small">First published at <a href="{esc(p["canonical"])}">{esc(host)}</a>.</p>'
    stamp = (f'<p class="post-date"><time datetime="{esc(p["date"])}">{esc(p["shown"])}</time></p>'
             if filled(p["shown"]) else f'<p class="post-date">{placeholder("date")}</p>')
    stand = f'<p class="lead">{esc(p["standfirst"])}</p>' if filled(p["standfirst"]) else ""
    back = (f'<p class="crumbs"><a href="{site.url("writing.html")}">{esc(site.label_for("writing.html", "Notes"))}</a></p>'
            if "writing.html" in site.planned else "")
    rendered = md(p["body"])
    body = f'''<article>
<header class="page-title"><div class="wrap grid"><div class="rail"></div><div class="main">{back}<h1>{esc(p["title"])}</h1>{stamp}{stand}</div></div></header>
<section class="sec sec-post"><div class="wrap grid"><div class="rail"></div><div class="main prose">{banner}{source}
{rendered}
</div></div></section>
</article>
{site.band()}'''
    meta = p["standfirst"] or re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", rendered)).strip()[:180]
    site.page(path=post_path(p), title=f'{p["title"]} · {site.cfg["brand"]}', meta=meta, body=body,
              canonical=p["canonical"], index=not p["draft"], current="writing.html")


def build_feed(site, posts, d):
    live = [p for p in posts if not p["draft"]]
    now = datetime.datetime.now(datetime.timezone.utc)
    items = ""
    for p in live:
        try:
            dt = datetime.datetime.fromisoformat(p["date"]).replace(tzinfo=datetime.timezone.utc)
        except (TypeError, ValueError):
            dt = now
        link = site.base_url + site.href(post_path(p))
        content = md(p["body"]).replace("]]>", "]]&gt;")
        items += (f"<item><title>{esc(p['title'])}</title><link>{esc(link)}</link>"
                  f'<guid isPermaLink="true">{esc(link)}</guid>'
                  f"<pubDate>{format_datetime(dt)}</pubDate>"
                  + (f"<description>{esc(p['standfirst'])}</description>" if filled(p["standfirst"]) else "")
                  + f"<content:encoded><![CDATA[{content}]]></content:encoded></item>")
    desc = d.get("meta_description") or site.cfg.get("meta_description") or f'Notes from {site.cfg["brand"]}.'
    (DOCS / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n<channel>\n'
        f'<title>{esc(site.cfg["brand"])}</title>\n'
        f'<link>{esc(site.abs("writing.html"))}</link>\n'
        f'<description>{esc(desc)}</description>\n<language>en-us</language>\n'
        f'<atom:link href="{esc(site.abs("feed.xml"))}" rel="self" type="application/rss+xml"/>\n'
        f'<lastBuildDate>{format_datetime(now)}</lastBuildDate>\n'
        f'{items}\n</channel>\n</rss>\n')
    return len(live)


# ---------------------------------------------------------------- link check
def check_links(site):
    """Every internal href and src in docs/ must reach a file this build wrote, and a
    #fragment must name an id on the page it points at."""
    root = DOCS.resolve()
    pages = {f.resolve(): f.read_text() for f in sorted(DOCS.rglob("*.html"))}
    ids = {f: set(re.findall(r'\sid="([^"]+)"', text)) for f, text in pages.items()}
    bad, checked = [], 0
    for f, text in pages.items():
        for attr, ref in re.findall(r'\s(href|src)="([^"]*)"', text):
            ref = html.unescape(ref)
            if ref.startswith(OFFSITE):
                continue
            checked += 1
            path, _, frag = ref.partition("#")
            path = path.split("?")[0]
            if not path:
                target = f
            elif path.startswith("/"):
                if site.bp and (path == site.bp or path.startswith(site.bp + "/")):
                    path = path[len(site.bp):] or "/"
                target = root / path.lstrip("/")
            else:
                target = f.parent / path
            if path.endswith("/") or target.is_dir():
                target = target / "index.html"
            target = target.resolve()
            where = f'{f.relative_to(root)}: {attr}="{ref}"'
            if not (target == root or root in target.parents) or not target.is_file():
                bad.append(f"{where} reaches no file")
            elif frag and target in ids and frag not in ids[target]:
                bad.append(f'{where} names no id "{frag}" on that page')
    return checked, bad


# ---------------------------------------------------------------- build
BUILDERS = {  # content/pages/<stem>.json -> (output path, builder)
    "home": ("index.html", None),          # built first, needs posts + systems
    "writing": ("writing.html", None),     # the notes archive, built from content/writing/
    "systems": ("systems.html", build_systems),
    "about": ("about.html", build_about),
    "work-with-us": ("work-with-us.html", build_contact_page),
}


def main():
    site = Site()
    posts = load_posts()
    present = {f.stem: f for f in sorted(PAGES.glob("*.json"))} if PAGES.exists() else {}
    for stem in present:
        if stem not in BUILDERS:
            print(f"  note: content/pages/{stem}.json has no builder in build.py — not rendered")

    # Resolve every page this build will write before rendering anything, so nav,
    # footer and inline links can be checked against it.
    planned = {out for stem, (out, _) in BUILDERS.items() if stem in present}
    if posts:
        planned.add("writing.html")
    planned.update(post_path(p) for p in posts)
    planned.update(old for old, new in ALIASES.items() if new in planned)
    site.planned = planned
    site.has_feed = bool(posts)

    for dead in site.dead_links():
        print(f"  note: dropped a link with no page behind it — {dead}")
    if site.bp:
        print(f"  note: base_path is '{site.bp}' — right for a GitHub Pages project site, wrong at a domain root")
    if posts and not site.base_url:
        print("  note: base_url is empty in content/site.json, so feed and sitemap URLs come out relative; "
              "set it to the deployed origin")

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy(f, DOCS / f.name)
    media = CONTENT / "media"
    if media.exists():
        shutil.copytree(media, DOCS / "media")
    (DOCS / ".nojekyll").write_text("")  # only GitHub Pages reads this; harmless elsewhere
    if filled(site.cfg.get("custom_domain")):
        (DOCS / "CNAME").write_text(site.cfg["custom_domain"].strip() + "\n")

    systems = all_systems(jload(present["systems"])) if "systems" in present else []
    writing_cfg = jload(present["writing"]) if "writing" in present else {}

    if "home" in present:
        build_home(site, jload(present["home"]), posts, systems)
    for stem, (_, builder) in BUILDERS.items():
        if builder and stem in present:
            builder(site, jload(present[stem]))
    for old, new in ALIASES.items():
        if new in planned:
            site.redirect(old, new)
    if "writing.html" in planned:
        build_writing_index(site, writing_cfg, posts)
    for p in posts:
        build_post(site, p)

    live = build_feed(site, posts, writing_cfg) if posts else 0

    today = datetime.date.today().isoformat()
    urls = "".join(f"<url><loc>{esc(site.base_url + site.href(path))}</loc><lastmod>{today}</lastmod></url>"
                   for path, indexed in site.pages_out if indexed)
    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                      f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    sm = f"Sitemap: {site.abs('sitemap.xml')}\n" if site.base_url else ""  # must be absolute or omitted
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\n{sm}")

    checked, bad = check_links(site)
    for b in bad:
        print(f"  note: broken link — {b}")
    drafts = sum(1 for p in posts if p["draft"])
    print(f"built {len(site.pages_out)} pages -> {DOCS}")
    print(f"  {len(posts)} post(s): {live} published, {drafts} draft(s) kept out of the feed and sitemap")
    print(f"  links: {checked} internal href/src checked, {len(bad)} broken")
    return 0


if __name__ == "__main__":
    sys.exit(main())
