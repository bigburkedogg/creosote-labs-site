#!/usr/bin/env python3
"""Build the Creosote Labs site.

content/  (JSON pages, Markdown posts, media)  +  assets/  ->  docs/  (the published folder)

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
MEDIA = CONTENT / "media"

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

# Old paths that now live elsewhere. Each is written as a small noindex page that forwards
# to the new one, keeping any #fragment so existing links keep working. The map beside
# each one renames the fragments whose id changed in the move.
ALIASES = {
    "systems.html": ("projects.html", {
        "client-work": "for-clients",
        "assessment-course-engine": "wild-relating",
        "private-university": "the-university",
        "teaching-apps": "gate-city",
        "internal-systems": "daily-brief",
    }),
    "work-with-us.html": ("contact.html", {}),
}

# Files under content/media/ with these extensions are copied to docs/media/. Anything
# else there (dotfiles, editor backups, a temp file mid-write) stays out of docs/.
MEDIA_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
PNG_START = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"

# Screenshots are 1440x900. The attributes give the browser the 16:10 box before the
# file loads; the stylesheet sets the size it is shown at.
SHOT_SIZE = (1440, 900)

# Writing stays out of the nav, the footer and the home page until this many posts are
# published, unless writing.json sets its own `min_published`.
MIN_PUBLISHED = 3


def jload(path):
    return json.loads(Path(path).read_text())


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def filled(s):
    return bool((s or "").strip()) if isinstance(s, str) else bool(s)


def as_int(value, default):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def placeholder(label):
    """The yellow marker for copy that is still to be written. Loud on purpose."""
    return f'<span class="placeholder">Placeholder — {esc(label)}</span>'


def first_sentence(text):
    """The first sentence of the first paragraph: a card's summary when none is set."""
    para = re.split(r"\n\s*\n", (text or "").strip())[0]
    m = re.match(r"(.+?[.!?])\s+(?=[A-Z])", para, re.S)
    return (m.group(1) if m else para).strip()


def link_label(href):
    """An outside link is labelled with its address: host and path, without the scheme."""
    m = re.match(r"https?://(?:www\.)?([^/?#]+)([^?#]*)", href)
    return (m.group(1) + m.group(2).rstrip("/")) if m else href


# ---------------------------------------------------------------- media
def image_complete(path):
    """True when the file is a whole image. A PNG must open with its signature and close
    with its IEND chunk, so a screenshot caught while it is still being written is never
    published."""
    try:
        data = path.read_bytes()
    except OSError:
        return False
    kind = path.suffix.lower()
    if kind == ".png":
        return data.startswith(PNG_START) and PNG_END in data[-64:]
    if kind in (".jpg", ".jpeg"):
        return data.startswith(b"\xff\xd8") and b"\xff\xd9" in data[-64:]
    return len(data) > 0


def copy_media():
    """Copy the images in content/media/ into docs/media/ and return the paths that made
    it. Each copy is checked after it lands, because the copy is what gets served."""
    kept = []
    if not MEDIA.exists():
        return kept
    for f in sorted(MEDIA.rglob("*")):
        rel = f.relative_to(MEDIA)
        if (not f.is_file() or f.suffix.lower() not in MEDIA_TYPES
                or any(part.startswith(".") for part in rel.parts)):
            continue
        dest = DOCS / "media" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dest)
        if image_complete(dest):
            kept.append(rel.as_posix())
        else:
            dest.unlink()
            print(f"  note: content/media/{rel.as_posix()} is incomplete or not an image — left out")
    return kept


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
    """Every .md file in content/writing/, newest first. Drafts are included here and
    filtered out by main(): a draft is never written to docs/."""
    posts = []
    if not WRITING.exists():
        return posts
    for f in sorted(WRITING.glob("*.md")):
        meta, body = front_matter(f.read_text())
        m = re.match(r"(\d{4}-\d{2}-\d{2})[-_](.+)", f.stem)
        date = meta.get("date", "") or (m.group(1) if m else "")
        slug = meta.get("slug", "") or (m.group(2) if m else f.stem)
        slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
        draft = meta.get("draft", "").strip().lower() in ("true", "yes", "1")
        if not draft and not filled(date):
            print(f"  note: {f.name} has no date (front-matter `date:` or a YYYY-MM-DD- filename)")
        posts.append({
            "file": f.name,
            "slug": slug,
            "date": date,
            "shown": show_date(date),
            "title": meta.get("title", "") or slug.replace("-", " "),
            "standfirst": meta.get("standfirst", ""),
            "canonical": meta.get("canonical", ""),
            "draft": draft,
            "body": body,
        })
    by_slug = {}
    for p in posts:
        if not p["draft"]:
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
        self.pages_out = []      # (path, include_in_sitemap)
        self.planned = set()     # every page this build will write, for link checking
        self.hidden = set()      # pages that are built but kept out of the nav and footer
        self.has_feed = False
        self.writing_listed = False
        self.media = set()       # paths under docs/media/ that this build copied and checked
        self.shots_shown, self.shots_missing = set(), set()

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

    def listed(self, href):
        """A link that may appear in the nav or the footer: it reaches a page, and that page
        is not one being kept out of sight (Writing, until enough posts are published)."""
        if not self.link_ok(href):
            return False
        return href.split("#")[0].split("?")[0].lstrip("/") not in self.hidden

    def dead_links(self):
        out = []
        for key in ("nav", "footer_links"):
            for item in self.cfg.get(key, []):
                if not self.link_ok(item.get("href")):
                    out.append(f'site.json {key}: "{item.get("label")}" -> {item.get("href")}')
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

    # ---- images ----
    def shot(self, project):
        """A project's screenshot, or nothing at all when the file is not there."""
        rel = (project.get("image") or "").strip().lstrip("/")
        if not rel:
            return ""
        if rel not in self.media:
            self.shots_missing.add(rel)
            return ""
        self.shots_shown.add(rel)
        w, h = SHOT_SIZE
        alt = f'{(project.get("name") or "").strip()} screenshot'
        return (f'<img class="shot" src="{esc(self.url("media/" + rel))}" alt="{esc(alt)}" '
                f'width="{w}" height="{h}" loading="lazy" decoding="async">')

    # ---- shared chrome ----
    def header(self, current):
        links = "".join(
            f'<a href="{self.url(n["href"])}"{" aria-current=\"page\"" if n["href"] == current else ""}>{esc(n["label"])}</a>'
            for n in self.cfg.get("nav", []) if self.listed(n.get("href")))
        cta = (f'<a class="btn btn-small" href="{self.url(self.cfg["cta_href"])}">{esc(self.cfg["cta_label"])}</a>'
               if filled(self.cfg.get("cta_label")) and self.link_ok(self.cfg.get("cta_href")) else "")
        brand = esc(self.cfg["brand"])
        return (f'<header class="site-header"><div class="wrap bar">'
                f'<a class="wordmark" href="{self.href("index.html")}" aria-label="{brand} home">{MARK}'
                f'<span>{brand}</span></a>'
                f'<nav class="nav" aria-label="Main">{links}{cta}</nav>'
                f'</div></header>')

    def footer(self):
        """One line (brand · owner · email) and the nav links."""
        items = self.cfg.get("footer_links") or self.cfg.get("nav", [])
        links = "".join(f'<a href="{self.url(n["href"])}">{esc(n["label"])}</a>'
                        for n in items if self.listed(n.get("href")))
        if self.writing_listed and self.has_feed:
            links += f'<a href="{self.url("feed.xml")}">RSS</a>'
        bits = [esc(self.cfg["brand"])]
        if filled(self.cfg.get("owner")):
            bits.append(esc(self.cfg["owner"]))
        if filled(self.cfg.get("email")):
            bits.append(f'<a href="mailto:{esc(self.cfg["email"])}">{esc(self.cfg["email"])}</a>')
        line = " · ".join(bits)
        return (f'<footer class="site-footer"><div class="wrap foot">'
                f'<p class="foot-line">{MARK}<span>{line}</span></p>'
                f'<nav class="foot-nav" aria-label="Footer">{links}</nav>'
                f'</div></footer>')

    def page(self, *, path, title, meta, body, current=None, head="", canonical=None, index=True):
        meta = meta if filled(meta) else self.cfg.get("meta_description", "")
        href = canonical if filled(canonical) else (self.base_url + self.href(path))
        feed = (f'<link rel="alternate" type="application/rss+xml" title="{esc(self.cfg["brand"])}" '
                f'href="{self.url("feed.xml")}">\n' if self.writing_listed and self.has_feed else "")
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

    def redirect(self, path, target, renamed=None):
        """A moved page: a noindex stub that forwards to `target`, keeping any #fragment
        and renaming it when the id it names has changed."""
        to = self.url(target)
        name = self.label_for(target, target)
        if renamed:
            go = (f"var m = {json.dumps(renamed)}, h = location.hash.slice(1);\n"
                  f'location.replace({json.dumps(to)} + (h ? "#" + (m[h] || h) : ""));')
        else:
            go = f"location.replace({json.dumps(to)} + location.hash);"
        doc = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               f'<title>{esc(name)} · {esc(self.cfg["brand"])}</title>\n'
               f'<meta name="robots" content="noindex">\n'
               f'<link rel="canonical" href="{esc(self.base_url + self.href(target))}">\n'
               f'<meta http-equiv="refresh" content="0; url={esc(to)}">\n'
               f'<script>\n{go}\n</script>\n'
               f'<style>body{{margin:0;padding:24px 16px;font:16px/1.6 system-ui,sans-serif;'
               f'background:#faf6ee;color:#0f1a11}}a{{color:#1f3324}}</style>\n</head>\n<body>\n'
               f'<p>This page has moved to <a href="{esc(to)}">{esc(name)}</a>.</p>\n</body>\n</html>\n')
        (DOCS / path).write_text(doc)


# ---------------------------------------------------------------- shared blocks
def section(title, inner, *, sid="", cls=""):
    head = f'<h2 class="sec-title">{esc(title)}</h2>' if filled(title) else ""
    ident = f' id="{esc(sid)}"' if filled(sid) else ""
    return (f'<section class="{esc(("sec " + cls).strip())}"{ident}><div class="wrap">'
            f'{head}{inner}</div></section>')


def page_title(site, h1, lead=""):
    """The top of every page but the home page."""
    ld = f'<p class="lead">{site.inline(lead)}</p>' if filled(lead) else ""
    return f'<div class="page-title"><div class="wrap"><h1>{esc(h1)}</h1>{ld}</div></div>'


def more_link(site, label, href):
    if not (filled(label) and site.link_ok(href)):
        return ""
    return f'<p class="more-link"><a href="{site.url(href)}">{esc(label)}</a></p>'


def project_groups(d):
    """projects.json holds groups of projects; a flat `projects` list also works."""
    if d.get("groups"):
        return d["groups"]
    return [{"heading": "", "projects": d.get("projects") or []}]


def all_projects(d):
    return [s for g in project_groups(d) for s in g.get("projects") or []]


def status_line(s):
    return f'<p class="status">{esc(s["status"])}</p>' if filled(s.get("status")) else ""


def project_tile(site, s):
    """A home-page card: screenshot, name, status line, one sentence. The whole card
    links to the project's entry on projects.html."""
    target = site.url("projects.html") + (f'#{s["id"]}' if filled(s.get("id")) else "")
    summary = s.get("summary") if filled(s.get("summary")) else first_sentence(s.get("text", ""))
    line = f'<p class="summary">{site.inline(summary)}</p>' if filled(summary) else ""
    return (f'<li class="tile">{site.shot(s)}<h3><a href="{esc(target)}">{esc(s["name"])}</a></h3>'
            f'{status_line(s)}{line}</li>')


def project_entry(site, s):
    """An entry on projects.html: the screenshot beside the name, status line, text, one
    detail line and the outside link. With no screenshot the text takes the whole row."""
    shot = site.shot(s)
    ident = f' id="{esc(s["id"])}"' if filled(s.get("id")) else ""
    text = f'<div class="entry-text">{site.rich(s["text"])}</div>' if filled(s.get("text")) else ""
    detail = f'<p class="detail">{site.inline(s["detail"])}</p>' if filled(s.get("detail")) else ""
    visit = ""
    if filled(s.get("href")):
        href = s["href"].strip()
        visit = f'<p class="visit"><a href="{esc(site.url(href))}">{esc(link_label(href))}</a></p>'
    cls = "entry has-shot" if shot else "entry"
    return (f'<li class="{cls}"{ident}>{shot}<div class="entry-body"><h3>{esc(s["name"])}</h3>'
            f'{status_line(s)}{text}{detail}{visit}</div></li>')


def post_list(site, posts, heading="h3"):
    """The writing index: date in mono on the left, title and standfirst on the right."""
    rows = ""
    for p in posts:
        date = (f'<time datetime="{esc(p["date"])}">{esc(p["date"])}</time>'
                if filled(p["shown"]) else placeholder("date"))
        stand = f'<p class="stand">{esc(p["standfirst"])}</p>' if filled(p["standfirst"]) else ""
        rows += (f'<li class="post-row"><p class="post-when">{date}</p><div class="post-main">'
                 f'<{heading} class="post-title"><a href="{site.href(post_path(p))}">{esc(p["title"])}</a></{heading}>'
                 f'{stand}</div></li>')
    return f'<ul class="posts">{rows}</ul>'


# ---------------------------------------------------------------- pages
def build_home(site, d, posts, projects):
    """The two-line hero, six project cards, a short About, the latest writing once
    Writing is listed, and the contact line."""
    h = d.get("hero") or {}
    lead = f'<p class="lead">{site.inline(h["sub"])}</p>' if filled(h.get("sub")) else ""
    body = [f'<section class="hero"><div class="wrap">'
            f'<h1>{esc(h.get("h1") or site.cfg["brand"])}</h1>{lead}</div></section>']

    by_id = {s.get("id"): s for s in projects if filled(s.get("id")) and filled(s.get("name"))}
    wanted = d.get("projects_featured") or []
    for key in wanted:
        if key not in by_id:
            print(f"  note: home.json features project id '{key}', which projects.json does not define")
    featured = [by_id[key] for key in wanted if key in by_id]
    if featured:
        tiles = "".join(project_tile(site, s) for s in featured)
        body.append(section(d.get("projects_heading", "Projects"),
                            f'<ul class="tiles">{tiles}</ul>'
                            + more_link(site, d.get("projects_link_label"), d.get("projects_link_href")),
                            sid="projects"))

    if filled(d.get("about_text")):
        body.append(section(d.get("about_heading", "About"),
                            f'<div class="prose">{site.rich(d["about_text"])}</div>'
                            + more_link(site, d.get("about_link_label"), d.get("about_link_href")),
                            sid="about"))

    if site.writing_listed and posts:
        latest = posts[: as_int(d.get("writing_count"), 3)]
        body.append(section(d.get("writing_heading", "Writing"),
                            post_list(site, latest)
                            + more_link(site, d.get("writing_link_label"), d.get("writing_link_href")),
                            sid="writing"))

    if filled(d.get("contact_text")):
        body.append(section(d.get("contact_heading", "Contact"),
                            f'<div class="prose">{site.rich(d["contact_text"])}</div>',
                            sid="contact", cls="band"))

    site.page(path="index.html", title=d.get("title", site.cfg["brand"]),
              meta=d.get("meta_description", ""), body="\n".join(body), current="index.html")


def build_projects(site, d):
    body = [page_title(site, d.get("h1", "Projects"), d.get("intro", ""))]
    seen = set()
    for g in project_groups(d):
        items = []
        for s in g.get("projects") or []:
            if not filled(s.get("name")):
                print(f"  note: projects.json has an entry with no name in '{g.get('heading', '')}' — skipped")
                continue
            if filled(s.get("id")):
                if s["id"] in seen:
                    print(f"  note: projects.json uses the id '{s['id']}' twice — links will reach the first")
                seen.add(s["id"])
            items.append(s)
        if not items:
            continue
        entries = "".join(project_entry(site, s) for s in items)
        body.append(section(g.get("heading", ""), f'<ul class="entries">{entries}</ul>', sid=g.get("id", "")))
    site.page(path="projects.html", title=d.get("title", "Projects"),
              meta=d.get("meta_description", ""), body="\n".join(body), current="projects.html")


def build_about(site, d):
    inner = site.rich(d.get("text", ""))
    if filled(d.get("contact")):
        inner += f'<p class="contact-line">{site.inline(d["contact"])}</p>'
    body = page_title(site, d.get("h1", "About"), d.get("lead", "")) + \
        section("", f'<div class="prose">{inner}</div>', cls="sec-first")
    site.page(path="about.html", title=d.get("title", "About"),
              meta=d.get("meta_description", ""), body=body, current="about.html")


def build_contact(site, d):
    body = page_title(site, d.get("h1", "Contact"), d.get("lead", "")) + \
        section("", f'<div class="prose">{site.rich(d.get("text", ""))}</div>', cls="sec-first")
    site.page(path="contact.html", title=d.get("title", "Contact"),
              meta=d.get("meta_description", ""), body=body, current="contact.html")


# ---------------------------------------------------------------- writing
def build_writing_index(site, d, posts):
    """The archive of published posts. Drafts never reach it."""
    if posts:
        listing = post_list(site, posts, "h2")
        listing += f'<p class="more-link"><a href="{site.url("feed.xml")}">RSS feed</a></p>' if site.has_feed else ""
    else:
        listing = f'<p class="empty">{esc(d["empty_text"])}</p>' if filled(d.get("empty_text")) else ""
    subscribe = ""
    if filled(d.get("subscribe_action")):
        subscribe = section(d.get("subscribe_heading", "Subscribe"), (
            (f'<p class="sec-intro">{esc(d["subscribe_text"])}</p>' if filled(d.get("subscribe_text")) else "")
            + f'<form class="signup" action="{esc(d["subscribe_action"])}" method="post">'
            f'<input type="email" name="email" aria-label="Email address" autocomplete="email" required>'
            f'<button class="btn" type="submit">{esc(d.get("subscribe_button_label", "Subscribe"))}</button></form>'))
    body = (page_title(site, d.get("h1", "Writing"), d.get("sub", ""))
            + section("", listing, cls="sec-first") + subscribe)
    site.page(path="writing.html", title=d.get("title", f'Writing · {site.cfg["brand"]}'),
              meta=d.get("meta_description", ""), body=body, current="writing.html",
              index=site.writing_listed)


def build_post(site, p):
    source = ""
    if filled(p["canonical"]):
        host = re.sub(r"^https?://(www\.)?", "", p["canonical"]).split("/")[0]
        source = f'<p class="small">First published at <a href="{esc(p["canonical"])}">{esc(host)}</a>.</p>'
    stamp = (f'<p class="post-date"><time datetime="{esc(p["date"])}">{esc(p["shown"])}</time></p>'
             if filled(p["shown"]) else f'<p class="post-date">{placeholder("date")}</p>')
    stand = f'<p class="lead">{esc(p["standfirst"])}</p>' if filled(p["standfirst"]) else ""
    back = (f'<p class="crumbs"><a href="{site.url("writing.html")}">{esc(site.label_for("writing.html", "Writing"))}</a></p>'
            if "writing.html" in site.planned else "")
    rendered = md(p["body"])
    body = f'''<article>
<header class="page-title"><div class="wrap">{back}<h1>{esc(p["title"])}</h1>{stamp}{stand}</div></header>
<section class="sec sec-post"><div class="wrap"><div class="prose">{source}
{rendered}
</div></div></section>
</article>'''
    meta = p["standfirst"] or re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", rendered)).strip()[:180]
    site.page(path=post_path(p), title=f'{p["title"]} · {site.cfg["brand"]}', meta=meta, body=body,
              canonical=p["canonical"], current="writing.html")


def build_feed(site, posts, d):
    """The RSS feed of published posts."""
    now = datetime.datetime.now(datetime.timezone.utc)
    items = ""
    for p in posts:
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
    desc = d.get("meta_description") or site.cfg.get("meta_description") or site.cfg["brand"]
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
    "home": ("index.html", None),          # built first, needs posts + projects
    "writing": ("writing.html", None),     # the writing archive, built from content/writing/
    "projects": ("projects.html", build_projects),
    "about": ("about.html", build_about),
    "contact": ("contact.html", build_contact),
}


def main():
    site = Site()
    posts = load_posts()
    published = [p for p in posts if not p["draft"]]
    drafts = len(posts) - len(published)
    present = {f.stem: f for f in sorted(PAGES.glob("*.json"))} if PAGES.exists() else {}
    for stem in present:
        if stem not in BUILDERS:
            print(f"  note: content/pages/{stem}.json has no builder in build.py — not rendered")

    # Resolve every page this build will write before rendering anything, so nav,
    # footer and inline links can be checked against it. Drafts are not written.
    planned = {out for stem, (out, _) in BUILDERS.items() if stem in present}
    if published:
        planned.add("writing.html")
    planned.update(post_path(p) for p in published)
    planned.update(old for old, (new, _) in ALIASES.items() if new in planned)
    site.planned = planned

    # Writing is built (page and feed) whenever it exists, but it only appears in the
    # nav, the footer and on the home page once enough posts are published.
    writing_cfg = jload(present["writing"]) if "writing" in present else {}
    need = as_int(writing_cfg.get("min_published"), MIN_PUBLISHED)
    site.has_feed = "writing.html" in planned
    site.writing_listed = site.has_feed and len(published) >= need
    if not site.writing_listed:
        site.hidden.add("writing.html")

    for dead in site.dead_links():
        print(f"  note: dropped a link with no page behind it — {dead}")
    if site.bp:
        print(f"  note: base_path is '{site.bp}' — right for a GitHub Pages project site, wrong at a domain root")
    if site.has_feed and not site.base_url:
        print("  note: base_url is empty in content/site.json, so feed and sitemap URLs come out relative; "
              "set it to the deployed origin")

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy(f, DOCS / f.name)
    site.media = set(copy_media())
    (DOCS / ".nojekyll").write_text("")  # only GitHub Pages reads this; harmless elsewhere
    if filled(site.cfg.get("custom_domain")):
        (DOCS / "CNAME").write_text(site.cfg["custom_domain"].strip() + "\n")

    projects = all_projects(jload(present["projects"])) if "projects" in present else []

    if "home" in present:
        build_home(site, jload(present["home"]), published, projects)
    for stem, (_, builder) in BUILDERS.items():
        if builder and stem in present:
            builder(site, jload(present[stem]))
    for old, (new, renamed) in ALIASES.items():
        if new in planned:
            site.redirect(old, new, renamed)
    if "writing.html" in planned:
        build_writing_index(site, writing_cfg, published)
    for p in published:
        build_post(site, p)
    if site.has_feed:
        build_feed(site, published, writing_cfg)

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
    shown, missing = sorted(site.shots_shown), sorted(site.shots_missing)
    listing = "listed" if site.writing_listed else f"kept out of the nav until {need} are published"
    print(f"built {len(site.pages_out)} pages -> {DOCS}")
    print(f"  posts: {len(published)} published, {drafts} draft(s) not built; writing is {listing}")
    print(f"  screenshots shown: {', '.join(shown) if shown else 'none'}")
    if missing:
        print(f"  screenshots not found, entries shown without one: {', '.join(missing)}")
    print(f"  links: {checked} internal href/src checked, {len(bad)} broken")
    return 0


if __name__ == "__main__":
    sys.exit(main())
