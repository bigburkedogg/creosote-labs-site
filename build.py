#!/usr/bin/env python3
"""Build the Creosote Labs site.

content/  (JSON pages, Markdown posts)  +  assets/  ->  docs/  (published by Render)

Standard library only. Run: python3 build.py
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

MARK = ('<svg viewBox="-120 -120 240 240" aria-hidden="true"><g stroke="currentColor" stroke-width="9" '
        'stroke-linecap="round" fill="none"><path d="M0 85.5V-95"/><path d="M0-55-55-90"/><path d="M0-55 55-90"/>'
        '<path d="M0-10-65-33"/><path d="M0-10 65-33"/><path d="M0 33-57 15"/><path d="M0 33 57 15"/>'
        '<path d="M0 70-38 60"/><path d="M0 70 38 60"/></g><g fill="currentColor"><circle cx="0" cy="-95" r="10"/>'
        '<circle cx="-55" cy="-90" r="8"/><circle cx="55" cy="-90" r="8"/><circle cx="-65" cy="-33" r="8"/>'
        '<circle cx="65" cy="-33" r="8"/><circle cx="-57" cy="15" r="8"/><circle cx="57" cy="15" r="8"/>'
        '<circle cx="-38" cy="60" r="7"/><circle cx="38" cy="60" r="7"/></g>'
        '<circle cx="0" cy="95" r="11" fill="none" stroke="currentColor" stroke-width="8"/></svg>')

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500'
         '&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">')

MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")

# Field styling for the contact form. Inline because assets/styles.css has no
# stacked-form rules; move these into the stylesheet when it is next touched.
FIELD = ("font:inherit;font-size:15px;padding:10px 12px;border:1px solid var(--border-strong);"
         "border-radius:4px;background:var(--bg-elev);color:var(--fg);width:100%;box-sizing:border-box")
LABEL = "display:block;font-size:15px;font-weight:500;margin:0 0 6px"


def jload(path):
    return json.loads(Path(path).read_text())


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def filled(s):
    return bool((s or "").strip()) if isinstance(s, str) else bool(s)


def tk(label):
    return f'<span class="tk">{esc(label)}</span>'


def paras(text, cls=""):
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", text or "") if p.strip())


# ---------------------------------------------------------------- markdown (posts)
# A deliberately small subset: ## / ### headings, paragraphs, - and 1. lists,
# > blockquotes, ``` fences, --- rules, **bold**, *italic*, `code`,
# [label](url), and [[placeholder]], which renders as a yellow placeholder chip.
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
    out = re.sub(r"\[\[(.+?)\]\]", lambda m: put(f'<span class="tk">{_emph(m.group(1))}</span>'), out)
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
            out.append('<pre class="mono" style="overflow-x:auto"><code>'
                       + html.escape("\n".join(buf), quote=True) + "</code></pre>")
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
        if path.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            return path
        return f"{self.bp}/{path.lstrip('/')}"

    def abs(self, path):
        return f"{self.base_url}{self.url(path)}"

    def href(self, path):
        """Link form of a path: a directory index links to the directory."""
        return self.url(path).removesuffix("index.html")

    # ---- links ----
    def link_ok(self, href):
        """True for external and anchor links, and for internal links this build writes."""
        if not filled(href):
            return False
        if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
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

    # ---- shared chrome ----
    def header(self, current):
        links = "".join(
            f'<a href="{self.url(n["href"])}"{" aria-current=\"page\"" if n["href"] == current else ""}>{esc(n["label"])}</a>'
            for n in self.cfg.get("nav", []) if self.link_ok(n.get("href")))
        cta = (f'<a class="btn" href="{self.url(self.cfg["cta_href"])}">{esc(self.cfg["cta_label"])}</a>'
               if filled(self.cfg.get("cta_label")) and self.link_ok(self.cfg.get("cta_href")) else "")
        return (f'<header class="site-header"><div class="wrap bar">'
                f'<a class="wordmark" href="{self.url("index.html")}" aria-label="{esc(self.cfg["brand"])} home">{MARK}'
                f'<span>{esc(self.cfg["brand"])}</span></a>'
                f'<button class="nav-toggle" aria-expanded="false" aria-controls="nav">Menu</button>'
                f'<nav id="nav" class="nav">{links}{cta}</nav>'
                f'</div></header>')

    def contact_line(self):
        bits = []
        if filled(self.cfg.get("phone")):
            bits.append(f'<a href="tel:{esc(self.cfg.get("phone_tel", self.cfg["phone"]))}">{esc(self.cfg["phone"])}</a>')
        if filled(self.cfg.get("email")):
            bits.append(f'<a href="mailto:{esc(self.cfg["email"])}">{esc(self.cfg["email"])}</a>')
        return " · ".join(bits)

    def footer(self):
        links = [l for l in self.cfg.get("footer_links", []) if self.link_ok(l.get("href"))]
        extra = " · ".join(f'<a href="{self.url(l["href"])}">{esc(l["label"])}</a>' for l in links)
        if self.has_feed:
            extra = (extra + " · " if extra else "") + f'<a href="{self.url("feed.xml")}">RSS</a>'
        return (f'<footer class="site-footer"><div class="wrap"><p><strong>{esc(self.cfg["brand"])}</strong></p>'
                f'<p>{self.contact_line()}</p>' + (f'<p>{extra}</p>' if extra else "") + '</div></footer>')

    def contact_block(self):
        """The closing panel. Vague by design: no pricing, no scheduler, no urgency."""
        c = self.cfg.get("contact") or {}
        if not filled(c.get("heading")) and not filled(c.get("text")):
            return ""
        link = ""
        if filled(c.get("link_label")) and self.link_ok(c.get("link_href")):
            link = (f'<p class="actions"><a class="btn" href="{self.url(c["link_href"])}">'
                    f'{esc(c["link_label"])}</a></p>')
        return (f'<section class="book" id="contact"><div class="wrap"><h2>{esc(c.get("heading", ""))}</h2>'
                f'<p>{esc(c.get("text", ""))}</p>{link}'
                f'<p class="contact">{self.contact_line()}</p></div></section>')

    def page(self, *, path, title, meta, body, current=None, head="", canonical=None, index=True):
        href = canonical if filled(canonical) else (self.base_url + self.href(path))
        feed = (f'<link rel="alternate" type="application/rss+xml" title="{esc(self.cfg["brand"])}" '
                f'href="{self.url("feed.xml")}">\n' if self.has_feed else "")
        robots = '<meta name="robots" content="noindex">\n' if not index else ""
        doc = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(meta)}">\n'
               f'{robots}<link rel="canonical" href="{esc(href)}">\n{feed}{FONTS}\n'
               f'<link rel="stylesheet" href="{self.url("styles.css")}">\n{head}</head>\n<body>\n'
               f'{self.header(current)}\n<main>\n{body}\n</main>\n{self.footer()}\n'
               f'<script src="{self.url("site.js")}"></script>\n</body>\n</html>\n')
        out = DOCS / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc)
        self.pages_out.append((path, index))


# ---------------------------------------------------------------- shared blocks
def post_list(site, posts, heading="h2"):
    rows = ""
    for p in posts:
        date = (f'<time datetime="{esc(p["date"])}">{esc(p["shown"])}</time>'
                if filled(p["shown"]) else tk("date"))
        if p["draft"]:
            date += " · <strong>Draft</strong>"
        stand = f'<p class="small">{esc(p["standfirst"])}</p>' if filled(p["standfirst"]) else ""
        rows += (f'<li class="post"><p class="date">{date}</p>'
                 f'<{heading}><a href="{site.href(post_path(p))}">{esc(p["title"])}</a></{heading}>'
                 f'{stand}</li>')
    return f'<ul class="posts">{rows}</ul>'


def project_list(site, projects, anchors=False):
    rows = ""
    for p in projects:
        status = esc(p.get("status", ""))
        if filled(p.get("href")):
            status += f' · <a href="{esc(p["href"])}">Visit</a>'
        pid = f' id="{esc(p["id"])}"' if anchors and filled(p.get("id")) else ""
        rows += (f'<li class="entry"{pid}><div><h3>{esc(p.get("name", ""))}</h3>'
                 f'<p class="status">{status}</p></div>'
                 f'<div><p>{esc(p.get("text", ""))}</p></div></li>')
    return f'<ul class="entries">{rows}</ul>'


def more_link(site, label, href):
    if not (filled(label) and site.link_ok(href)):
        return ""
    return f'<p class="actions"><a class="btn btn-quiet" href="{site.url(href)}">{esc(label)}</a></p>'


# ---------------------------------------------------------------- pages
def build_home(site, d, posts, projects):
    """The homepage is the writing and the work. Everything else is navigation."""
    h = d.get("hero", {})
    body = [f'<section class="hero"><div class="wrap"><h1>{esc(h.get("h1", site.cfg["brand"]))}</h1>'
            f'<p class="sub">{esc(h.get("sub", ""))}</p></div></section>']

    live = [p for p in posts if not p["draft"]][: int(d.get("writing_count", 3) or 3)]
    listing = post_list(site, live, "h3") if live else \
        f'<p class="muted">{esc(d.get("writing_empty_text", "Nothing published yet."))}</p>'
    body.append(f'<section class="block" id="writing"><div class="wrap">'
                f'<h2>{esc(d.get("writing_heading", "Writing"))}</h2>{listing}'
                f'{more_link(site, d.get("writing_link_label"), d.get("writing_link_href"))}</div></section>')

    featured = [p for key in d.get("projects_featured") or [] for p in projects if p.get("id") == key]
    if featured:
        body.append(f'<section class="block" id="projects"><div class="wrap">'
                    f'<h2>{esc(d.get("projects_heading", "Projects"))}</h2>{project_list(site, featured)}'
                    f'{more_link(site, d.get("projects_link_label"), d.get("projects_link_href"))}</div></section>')
        missing = [k for k in d.get("projects_featured") or [] if not any(p.get("id") == k for p in projects)]
        for k in missing:
            print(f"  note: home.json features project id '{k}', which projects.json does not define")

    body.append(site.contact_block())
    site.page(path="index.html", title=d.get("title", site.cfg["brand"]),
              meta=d.get("meta_description", site.cfg.get("meta_description", "")),
              body="\n".join(body), current="index.html")


def build_projects(site, d):
    intro = f'<p class="intro">{esc(d["intro"])}</p>' if filled(d.get("intro")) else ""
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d.get("eyebrow", "Projects"))}</p><h1>{esc(d.get("h1", "Projects"))}</h1></div></section>
<section class="block"><div class="wrap">{intro}{project_list(site, d.get("projects") or [], anchors=True)}</div></section>
{site.contact_block()}'''
    site.page(path="projects.html", title=d.get("title", "Projects"),
              meta=d.get("meta_description", ""), body=body, current="projects.html")


def build_about(site, d):
    work = ""
    if d.get("work"):
        items = "".join(f'<li class="service"><h3>{esc(w.get("name", ""))}</h3><p>{esc(w.get("text", ""))}</p></li>'
                        for w in d["work"])
        work = (f'<section class="block"><div class="wrap"><h2>{esc(d.get("work_heading", "What we work on"))}</h2>'
                f'<ul class="services">{items}</ul></div></section>')
    closing = (f'<section class="block"><div class="wrap prose">{paras(d["closing"])}</div></section>'
               if filled(d.get("closing")) else "")
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d.get("eyebrow", "About"))}</p><h1>{esc(d.get("h1", "About"))}</h1></div></section>
<section class="block"><div class="wrap prose">{paras(d.get("intro"))}</div></section>
{work}{closing}
{site.contact_block()}'''
    site.page(path="about.html", title=d.get("title", "About"),
              meta=d.get("meta_description", ""), body=body, current="about.html")


def build_contact_page(site, d):
    f = d.get("form") or {}
    fields = ""
    for fld in f.get("fields") or []:
        name, label = esc(fld.get("name", "")), esc(fld.get("label", ""))
        req = " required" if fld.get("required") else ""
        if fld.get("type") == "textarea":
            control = f'<textarea id="{name}" name="{name}" rows="6" style="{FIELD};resize:vertical"{req}></textarea>'
        else:
            control = f'<input id="{name}" name="{name}" type="{esc(fld.get("type", "text"))}" style="{FIELD}"{req}>'
        fields += f'<p style="margin:0 0 16px"><label for="{name}" style="{LABEL}">{label}</label>{control}</p>'
    action = f.get("action", "")
    if filled(action):
        note, disabled = "", ""
    else:
        note = (f'<p>{tk("form endpoint not set — put one in content/pages/work-with-us.json at form.action; "
                        "until then the email address below is the working route")}</p>')
        disabled = " disabled"
    form = (f'<form method="{esc(f.get("method", "post"))}" action="{esc(action) if filled(action) else ""}" '
            f'style="max-width:460px;margin-top:24px" '
            f'data-success="{esc(f.get("success_text", ""))}" data-error="{esc(f.get("error_text", ""))}">'
            f'{fields}<p style="margin:0"><button class="btn" type="submit"{disabled}>'
            f'{esc(f.get("submit_label", "Send"))}</button></p></form>') if fields else ""
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d.get("eyebrow", "Work with us"))}</p><h1>{esc(d.get("h1", "Work with us"))}</h1></div></section>
<section class="block"><div class="wrap prose">{paras(d.get("intro"))}{note}{form}
<p class="contact">{site.contact_line()}</p></div></section>'''
    site.page(path="work-with-us.html", title=d.get("title", "Work with us"),
              meta=d.get("meta_description", ""), body=body, current="work-with-us.html")


# ---------------------------------------------------------------- writing
def build_writing_index(site, d, posts):
    listing = post_list(site, posts) if posts else \
        f'<p class="muted">{esc(d.get("empty_text", "Nothing published yet."))}</p>'
    feed_line = f'<p class="small" style="margin-top:24px"><a href="{site.url("feed.xml")}">RSS feed</a></p>' \
        if site.has_feed else ""
    subscribe = ""
    if filled(d.get("subscribe_action")):
        subscribe = f'''
<section class="block"><div class="wrap prose"><h2 class="h3" style="margin-top:0">{esc(d.get("subscribe_heading", "Subscribe"))}</h2>
<p class="muted">{esc(d.get("subscribe_text", ""))}</p>
<form class="signup" action="{esc(d["subscribe_action"])}" method="post"><input type="email" name="email" placeholder="Email address" aria-label="Email address" required><button class="btn" type="submit">{esc(d.get("subscribe_button_label", "Subscribe"))}</button></form></div></section>'''
    sub = f'<p class="sub">{esc(d["sub"])}</p>' if filled(d.get("sub")) else ""
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d.get("eyebrow", "Writing"))}</p><h1>{esc(d.get("h1", "Writing"))}</h1>{sub}</div></section>
<section class="block"><div class="wrap">{listing}{feed_line}</div></section>
{subscribe}
{site.contact_block()}'''
    site.page(path="writing.html", title=d.get("title", f'Writing · {site.cfg["brand"]}'),
              meta=d.get("meta_description", ""), body=body, current="writing.html")


def build_post(site, p):
    banner = ('<p class="tk-box">Draft — scaffolding, not a finished post. Replace it or finish it, then set '
              '<code class="mono">draft: false</code> in the front matter.</p>') if p["draft"] else ""
    source = ""
    if filled(p["canonical"]):
        host = re.sub(r"^https?://(www\.)?", "", p["canonical"]).split("/")[0]
        source = f'<p class="small">First published at <a href="{esc(p["canonical"])}">{esc(host)}</a>.</p>'
    date = (f'<p class="small mono"><time datetime="{esc(p["date"])}">{esc(p["shown"])}</time></p>'
            if filled(p["shown"]) else f'<p class="small">{tk("date")}</p>')
    stand = f'<p class="sub">{esc(p["standfirst"])}</p>' if filled(p["standfirst"]) else ""
    back = (f'<p class="crumbs"><a href="{site.url("writing.html")}">Writing</a></p>'
            if "writing.html" in site.planned else "")
    rendered = md(p["body"])
    body = f'''
<article>
<section class="page-title"><div class="wrap">{back}<h1>{esc(p["title"])}</h1>{date}{stand}</div></section>
<section class="block"><div class="wrap prose">{banner}{source}
{rendered}
</div></section>
</article>
{site.contact_block()}'''
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
    desc = d.get("meta_description") or site.cfg.get("meta_description") or f'Writing from {site.cfg["brand"]}.'
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


# ---------------------------------------------------------------- build
BUILDERS = {  # content/pages/<stem>.json -> (output path, builder)
    "home": ("index.html", None),          # built first, needs posts + projects
    "writing": ("writing.html", None),     # built from content/writing/
    "projects": ("projects.html", build_projects),
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
    site.planned = planned
    site.has_feed = bool(posts)

    for dead in site.dead_links():
        print(f"  note: dropped a link with no page behind it — {dead}")
    if site.bp:
        print(f"  note: base_path is '{site.bp}' — right for a GitHub Pages project site, wrong at a domain root")
    if posts and not site.base_url:
        print("  note: base_url is empty in content/site.json, so feed and sitemap URLs come out relative; "
              "set it to the deployed origin (https://<name>.onrender.com, or the custom domain)")

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

    projects = (jload(present["projects"]).get("projects") or []) if "projects" in present else []
    writing_cfg = jload(present["writing"]) if "writing" in present else {}

    if "home" in present:
        build_home(site, jload(present["home"]), posts, projects)
    for stem, (_, builder) in BUILDERS.items():
        if builder and stem in present:
            builder(site, jload(present[stem]))
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
    drafts = sum(1 for p in posts if p["draft"])
    print(f"built {len(site.pages_out)} pages -> {DOCS}")
    print(f"  {len(posts)} post(s): {live} published, {drafts} draft(s) kept out of the feed and sitemap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
