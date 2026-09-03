#!/usr/bin/env python3
"""Build the Creosote Labs site.

content/  (JSON, edited in the admin app)  +  assets/  ->  docs/  (served by GitHub Pages)

Standard library only. Run: python3 build.py
"""
import datetime
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"

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


def jload(path):
    return json.loads(Path(path).read_text())


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def filled(s):
    return bool((s or "").strip()) if isinstance(s, str) else bool(s)


def tk(label):
    return f'<span class="tk">{esc(label)}</span>'


def val(s, label):
    return esc(s) if filled(s) else tk(label)


def paras(text, cls=""):
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", text or "") if p.strip())


def ul(items, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f"<ul{c}>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


class Site:
    def __init__(self):
        self.cfg = jload(CONTENT / "site.json")
        self.bp = self.cfg.get("base_path", "").rstrip("/")
        self.base_url = self.cfg.get("base_url", "").rstrip("/")
        self.pages_out = []  # (path, lastmod) for the sitemap

    def url(self, path):
        if not path:
            return ""
        if path.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            return path
        return f"{self.bp}/{path.lstrip('/')}"

    # ---- shared chrome ----
    def header(self, current):
        links = "".join(
            f'<a href="{self.url(n["href"])}"{" aria-current=\"page\"" if n["href"] == current else ""}>{esc(n["label"])}</a>'
            for n in self.cfg["nav"])
        return (f'<header class="site-header"><div class="wrap bar">'
                f'<a class="wordmark" href="{self.url("index.html")}" aria-label="{esc(self.cfg["brand"])} home">{MARK}'
                f'<span>{esc(self.cfg["brand"])}</span></a>'
                f'<button class="nav-toggle" aria-expanded="false" aria-controls="nav">Menu</button>'
                f'<nav id="nav" class="nav">{links}<a class="btn" href="#book">{esc(self.cfg["cta_label"])}</a></nav>'
                f'</div></header>')

    def contact(self):
        c = self.cfg
        return (f'<a href="tel:{esc(c["phone_tel"])}">{esc(c["phone"])}</a> · '
                f'<a href="mailto:{esc(c["email"])}">{esc(c["email"])}</a>')

    def footer(self):
        extra = " · ".join(f'<a href="{self.url(l["href"])}">{esc(l["label"])}</a>' for l in self.cfg.get("footer_links", []))
        return (f'<footer class="site-footer"><div class="wrap"><p><strong>{esc(self.cfg["brand"])}</strong></p>'
                f'<p>{self.contact()}</p>' + (f'<p>{extra}</p>' if extra else "") + '</div></footer>')

    def book(self, text=None):
        b = self.cfg["book"]
        link = self.cfg.get("booking_url", "")
        if filled(link):
            button = f'<a class="btn btn-lg" href="{esc(link)}">{esc(b["heading"])}</a>'
        else:
            button = f'<a class="btn btn-lg" href="#">{esc(b["heading"])}</a> {tk("booking link goes here (Google Calendar appointment page, Cal.com, or Calendly)")}'
        return (f'<section class="book" id="book"><div class="wrap"><h2>{esc(b["heading"])}</h2>'
                f'<p>{esc(text or b["text"])}</p><p class="actions">{button}</p>'
                f'<p class="contact">{self.contact()}</p></div></section>')

    def page(self, *, path, title, meta, body, current=None, head=""):
        canonical = f"{self.base_url}{self.url(path)}" if self.base_url else self.url(path)
        doc = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
               f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(meta)}">\n'
               f'<link rel="canonical" href="{esc(canonical)}">\n{FONTS}\n'
               f'<link rel="stylesheet" href="{self.url("styles.css")}">\n{head}</head>\n<body>\n'
               f'{self.header(current)}\n<main>\n{body}\n</main>\n{self.footer()}\n'
               f'<script src="{self.url("site.js")}"></script>\n</body>\n</html>\n')
        out = DOCS / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc)
        self.pages_out.append(path)


# ---------------------------------------------------------------- main pages
def build_home(site, d):
    h = d["hero"]
    body = [f'<section class="hero"><div class="wrap"><h1>{esc(h["h1"])}</h1><p class="sub">{esc(h["sub"])}</p>'
            f'<p class="actions"><a class="btn" href="#book">{esc(h["primary_label"])}</a> '
            f'<a class="btn btn-quiet" href="#pricing">{esc(h["secondary_label"])}</a></p></div></section>']
    svc = "".join(
        f'<li class="service"><h3>{esc(s["name"])}</h3><p>{esc(s["text"])}'
        + (f' <a href="{site.url(s["link_href"])}">{esc(s["link_label"])}</a>' if filled(s.get("link_href")) else "")
        + '</p></li>' for s in d["services"])
    body.append(f'<section class="block" id="services"><div class="wrap"><h2>{esc(d["services_heading"])}</h2>'
                f'<ul class="services">{svc}</ul></div></section>')
    tiers = "".join(
        f'<li class="tier"><h3>{esc(t["name"])}</h3><p class="amt">{esc(t["amount"])}'
        + (f' <small>{esc(t["unit"])}</small>' if filled(t.get("unit")) else "") + '</p>'
        f'<p>{esc(t["text"])}</p>' + (f'<p class="small">{esc(t["note"])}</p>' if filled(t.get("note")) else "")
        + '</li>' for t in d["pricing"])
    body.append(f'<section class="block" id="pricing"><div class="wrap"><h2>{esc(d["pricing_heading"])}</h2>'
                f'<p class="intro">{esc(d["pricing_intro"])}</p><ul class="tiers">{tiers}</ul></div></section>')
    steps = "".join(f'<li><span><strong>{esc(s["name"])}</strong> {esc(s["text"])}</span></li>' for s in d["process"])
    body.append(f'<section class="block" id="process"><div class="wrap"><h2>{esc(d["process_heading"])}</h2>'
                f'<ol class="steps">{steps}</ol></div></section>')
    body.append(f'<section class="block" id="clients"><div class="wrap"><h2>{esc(d["clients_heading"])}</h2>'
                f'<p class="prose">{esc(d["clients_text"])} <a href="{site.url("work.html")}">{esc(d["clients_link_label"])}</a>.</p>'
                f'</div></section>')
    body.append(f'<section class="quote"><div class="wrap"><blockquote>'
                f'{val(d.get("testimonial_quote"), "client testimonial, two or three sentences, pending client approval")}'
                f'</blockquote><cite>{val(d.get("testimonial_cite"), "name, title, company, pending consent to be named")}</cite>'
                f'</div></section>')
    body.append(site.book())
    site.page(path="index.html", title=d["title"], meta=d["meta_description"], body="\n".join(body), current="index.html")


def tiers_html(items):
    return "<ul class=\"tiers\">" + "".join(
        f'<li class="tier"><h3>{esc(t["name"])}</h3><p class="amt">{esc(t["amount"])}'
        + (f' <small>{esc(t["unit"])}</small>' if filled(t.get("unit")) else "") + '</p>'
        f'<p>{esc(t["text"])}</p>' + (f'<p class="small">{esc(t["note"])}</p>' if filled(t.get("note")) else "")
        + '</li>' for t in items) + "</ul>"


def build_training(site, d):
    included = ul(d["included"])
    fmt = d.get("followup_format", "")
    included = included[:-5] + (f'<li>Follow-up session format: {esc(fmt)}</li>' if filled(fmt)
                                else f'<li>{tk("follow-up session: remote or on site")}</li>') + "</ul>"
    agenda = "".join(f'<li><span class="t">{esc(a["time"])}</span><span>{esc(a["text"])}</span></li>' for a in d["agenda"])
    faqs = "".join(f'<li><strong>{esc(f["q"])}</strong><p>{val(f["a"], "answer pending")}</p></li>' for f in d["faqs"])
    pdf = (f'<a class="btn btn-quiet" href="{esc(d["pdf_url"])}">One-page PDF</a>' if filled(d.get("pdf_url"))
           else f'<a class="btn btn-quiet" href="#">{tk("one-page PDF of this page")}</a>')
    terms = (f'<p class="small">{esc(d["payment_terms"])}</p>' if filled(d.get("payment_terms"))
             else f'<p class="small">{tk("payment terms: when invoiced, when due, rescheduling")}</p>')
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d["eyebrow"])}</p><h1>{esc(d["h1"])}</h1><p class="sub">{esc(d["sub"])}</p></div></section>
<section class="block"><div class="wrap"><div class="two-col">
<div><h2 class="h3">{esc(d["format_heading"])}</h2>{ul(d["format"])}</div>
<div><h2 class="h3">{esc(d["included_heading"])}</h2>{included}</div>
</div></div></section>
<section class="block"><div class="wrap"><h2 class="h3" style="margin-top:0">{esc(d["agenda_heading"])}</h2><ul class="agenda">{agenda}</ul></div></section>
<section class="block"><div class="wrap"><div class="two-col">
<div><h2 class="h3">{esc(d["requirements_heading"])}</h2>{ul(d["requirements"])}</div>
<div><h2 class="h3">{esc(d["security_heading"])}</h2>{ul(d["security"])}</div>
</div></div></section>
<section class="block"><div class="wrap"><h2 class="h3" style="margin-top:0">{esc(d["pricing_heading"])}</h2>{tiers_html(d["pricing"])}{terms}</div></section>
<section class="block"><div class="wrap"><h2 class="h3" style="margin-top:0">{esc(d["faq_heading"])}</h2><ul class="faq">{faqs}</ul><p class="actions">{pdf}</p></div></section>
{site.book(d.get("book_text"))}'''
    site.page(path="training.html", title=d["title"], meta=d["meta_description"], body=body, current="training.html")


def build_work(site, d):
    c = d["case"]
    name = f'<strong>{esc(c["client_name"])}.</strong> ' if filled(c.get("client_name")) else tk("client name, pending consent to be named") + " "
    work_items = list(c["work"])
    work_html = "<ul>" + "".join(f"<li>{esc(w)}</li>" for w in work_items) + "</ul>"
    app = (f'<p><a href="{esc(c["app_url"])}">See the application</a></p>' if filled(c.get("app_url"))
           else f'<p>{tk("link to the live application, pending consent")}</p>')
    results = paras(c["results"]) if filled(c.get("results")) else f'<p>{tk("results and figures, pending client approval")}</p>'
    shots = c.get("screenshots") or []
    if shots:
        shots_html = "".join(f'<img src="{site.url("media/" + s["file"])}" alt="{esc(s.get("alt", ""))}">' for s in shots)
    else:
        shots_html = ('<div class="tk-box">Screenshot: application (pending consent)</div>'
                      '<div class="tk-box">Screenshot: tracker (pending consent)</div>')
    projects = ""
    for p in d["projects"]:
        status = esc(p["status"])
        if filled(p.get("href")):
            status += f' · <a href="{esc(p["href"])}">Visit</a>'
        elif not re.search(r"internal|personal", p["status"], re.I):
            status += " · " + tk("live link")
        projects += (f'<li class="entry"><div><h3>{esc(p["name"])}</h3><p class="status">{status}</p></div>'
                     f'<div><p>{esc(p["text"])}</p></div></li>')
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d["eyebrow"])}</p><h1>{esc(d["h1"])}</h1></div></section>
<section class="block" id="client-work"><div class="wrap"><h2>{esc(d["client_heading"])}</h2><div class="prose case">
<h3>Client</h3><p>{name}{esc(c["client_text"])}</p>
<h3>{esc(c["situation_heading"])}</h3>{paras(c["situation"])}
<h3>{esc(c["work_heading"])}</h3>{work_html}{app}
<h3>{esc(c["results_heading"])}</h3>{results}{paras(c.get("ongoing"))}
</div><div class="shots">{shots_html}</div></div></section>
<section class="block" id="projects"><div class="wrap"><h2>{esc(d["projects_heading"])}</h2><p class="intro">{esc(d["projects_intro"])}</p><ul class="entries">{projects}</ul></div></section>
{site.book()}'''
    site.page(path="work.html", title=d["title"], meta=d["meta_description"], body=body, current="work.html")


def build_writing(site, d):
    posts = ""
    for p in d["posts"]:
        title = f'<a href="{site.url(p["href"])}">{esc(p["title"])}</a>' if filled(p.get("href")) else esc(p["title"])
        posts += (f'<li class="post"><p class="date">{val(p.get("date"), "date")}</p><h2>{title}</h2>'
                  f'<p class="small">{esc(p["text"])}</p></li>')
    video = (f'<a href="{esc(d["video_url"])}">{esc(d["video_label"])}</a>' if filled(d.get("video_url"))
             else f'{esc(d["video_label"])}: {tk("YouTube channel link")}')
    action = esc(d["newsletter_action"]) if filled(d.get("newsletter_action")) else "#"
    note = "" if filled(d.get("newsletter_action")) else tk("connect to a list tool of your choosing")
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d["eyebrow"])}</p><h1>{esc(d["h1"])}</h1><p class="sub">{esc(d["sub"])}</p></div></section>
<section class="block"><div class="wrap"><ul class="posts prose">{posts}</ul><p class="small" style="margin-top:24px">{video}</p></div></section>
<section class="block"><div class="wrap prose"><h2 class="h3" style="margin-top:0">{esc(d["newsletter_heading"])}</h2><p class="muted">{esc(d["newsletter_text"])}</p>
<form class="signup" action="{action}" method="post"{' onsubmit="return false"' if action == "#" else ""}><input type="email" name="email" placeholder="Email address" aria-label="Email address"><button class="btn" type="submit">Subscribe</button> {note}</form></div></section>
{site.book()}'''
    site.page(path="writing.html", title=d["title"], meta=d["meta_description"], body=body, current="writing.html")


def build_about(site, d):
    photo = (f'<img class="photo" src="{site.url("media/" + d["photo"])}" alt="Brian Burke">' if filled(d.get("photo"))
             else '<div class="tk-box photo">Photo</div>')
    role = esc(d["founder_role_sentence"]) if filled(d.get("founder_role_sentence")) else tk("one or two sentences on the role and what you were responsible for; do not name the company")
    body = f'''
<section class="page-title"><div class="wrap"><p class="eyebrow">{esc(d["eyebrow"])}</p><h1>{esc(d["h1"])}</h1></div></section>
<section class="block"><div class="wrap about-grid">{photo}<div class="prose">{paras(d["intro"])}
<h2 class="h3">{esc(d["founder_heading"])}</h2><p>{esc(d["founder_text"])} {role}</p>
<p class="contact">{site.contact()}</p></div></div></section>
{site.book()}'''
    site.page(path="about.html", title=d["title"], meta=d["meta_description"], body=body, current="about.html")


# ---------------------------------------------------------------- landing pages
def landing_path(p):
    if p["kind"] == "service-segment":
        return f'{p["service"]}/{p["segment"]}/index.html'
    if p["kind"] == "service-location":
        return f'{p["service"]}/{p["location"]}/index.html'
    return f'{p["location"]}/{p["segment"]}/index.html'


def jsonld(data):
    return f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'


def build_landing(site, pages, services, segments, locations, home):
    S = {s["slug"]: s for s in services}
    G = {g["slug"]: g for g in segments}
    L = {l["slug"]: l for l in locations}
    by_key = {(p["kind"], p.get("service"), p.get("segment"), p.get("location")): p for p in pages}

    def link(path, label):
        return f'<a href="{site.url(path)}">{esc(label)}</a>'

    for p in pages:
        path = landing_path(p)
        svc = S.get(p.get("service") or "")
        seg = G.get(p.get("segment") or "")
        loc = L.get(p.get("location") or "")
        crumbs = [link("index.html", "Home")]
        if p["kind"] == "service-segment":
            crumbs += [link("industries/", "Industries"), link(f'industries/#{seg["slug"]}', seg["name"]), esc(svc["name"])]
        elif p["kind"] == "service-location":
            crumbs += [link("locations/", "Locations"), link(f'{loc["slug"]}/', loc["name"]), esc(svc["name"])]
        else:
            crumbs += [link("locations/", "Locations"), link(f'{loc["slug"]}/', loc["name"]), esc(seg["name"])]
        crumb_html = '<p class="crumbs">' + " › ".join(crumbs) + "</p>"

        if svc:
            what = f'<h2 class="h3">What we do</h2>{ul(svc["what_we_do"])}'
            pricing = f'<h2 class="h3">Pricing</h2><p>{esc(svc["pricing_summary"])}</p>'
        else:  # segment-location: all services
            what = '<h2 class="h3">Services</h2><ul>' + "".join(
                f'<li><strong>{esc(s["name"])}.</strong> {esc(s["summary"])} {link(f"{s["slug"]}/{loc["slug"]}/", "Details")}</li>'
                for s in services) + "</ul>"
            pricing = ('<h2 class="h3">Pricing</h2><p>Engagements begin with a one-day operations review at $3,000, which produces '
                       'a written assessment and a quote for each recommendation. Team training is $1,000 per person. '
                       f'{link("index.html#pricing", "Full pricing")}.</p>')
        projects = f'<h2 class="h3">Common projects</h2>{ul(p["projects"])}'
        steps = "".join(f'<li><span><strong>{esc(s["name"])}</strong> {esc(s["text"])}</span></li>' for s in home["process"])
        process = f'<h2 class="h3">How it works</h2><ol class="steps">{steps}</ol>'
        faqs = '<h2 class="h3">Frequently asked questions</h2><ul class="faq">' + "".join(
            f'<li><strong>{esc(f["q"])}</strong><p>{esc(f["a"])}</p></li>' for f in p["faqs"]) + "</ul>"

        # related links
        rel = []
        if p["kind"] == "service-segment":
            others = [link(f'{s["slug"]}/{seg["slug"]}/', f'{s["name"]} for {seg["name"].lower()}') for s in services if s["slug"] != svc["slug"]]
            rel.append(f'<h2 class="h3">Other services for {esc(seg["name"].lower())}</h2><ul>' + "".join(f"<li>{o}</li>" for o in others) + "</ul>")
            sib = [g for g in segments if g["group"] == seg["group"] and g["slug"] != seg["slug"]][:5]
            if sib:
                rel.append(f'<h2 class="h3">{esc(svc["name"])} for related businesses</h2><ul>' + "".join(
                    f'<li>{link(f"{svc["slug"]}/{g["slug"]}/", g["name"])}</li>' for g in sib) + "</ul>")
        elif p["kind"] == "service-location":
            others = [link(f'{s["slug"]}/{loc["slug"]}/', f'{s["name"]} in {loc["name"]}') for s in services if s["slug"] != svc["slug"]]
            rel.append(f'<h2 class="h3">Other services in {esc(loc["name"])}</h2><ul>' + "".join(f"<li>{o}</li>" for o in others) + "</ul>")
        else:
            others = [link(f'{s["slug"]}/{loc["slug"]}/', f'{s["name"]} in {loc["name"]}') for s in services]
            rel.append(f'<h2 class="h3">Services in {esc(loc["name"])}</h2><ul>' + "".join(f"<li>{o}</li>" for o in others) + "</ul>")
            svc_links = [link(f'{s["slug"]}/{seg["slug"]}/', f'{s["name"]} for {seg["name"].lower()}') for s in services]
            rel.append(f'<h2 class="h3">{esc(seg["name"])} anywhere</h2><ul>' + "".join(f"<li>{o}</li>" for o in svc_links) + "</ul>")
        related = "".join(rel)

        head = jsonld({"@context": "https://schema.org", "@type": "FAQPage",
                       "mainEntity": [{"@type": "Question", "name": f["q"],
                                       "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in p["faqs"]]})
        body = f'''
<section class="page-title"><div class="wrap">{crumb_html}<h1>{esc(p["h1"])}</h1></div></section>
<section class="block"><div class="wrap prose">{"".join(f"<p>{esc(t)}</p>" for t in p["intro"])}{what}{projects}{pricing}</div></section>
<section class="block"><div class="wrap prose">{process}{faqs}</div></section>
<section class="block"><div class="wrap prose related">{related}</div></section>
{site.book()}'''
        site.page(path=path, title=p["title"], meta=p["meta_description"], body=body, head=head)

    # ---- hubs ----
    groups = {}
    for g in segments:
        groups.setdefault(g["group"], []).append(g)
    ind = ""
    for grp, items in groups.items():
        ind += f'<h2 class="h3">{esc(grp)}</h2><ul class="hub">'
        for g in items:
            svcs = " · ".join(link(f'{s["slug"]}/{g["slug"]}/', s["name"]) for s in services
                              if ("service-segment", s["slug"], g["slug"], None) in by_key)
            ind += f'<li id="{esc(g["slug"])}"><strong>{esc(g["name"])}</strong><br><span class="small">{svcs}</span></li>'
        ind += "</ul>"
    site.page(path="industries/index.html", title="Industries · Creosote Labs",
              meta="AI consulting, systems and automation, website development, and team AI training for specific kinds of small businesses.",
              body=f'<section class="page-title"><div class="wrap"><p class="eyebrow">Industries</p><h1>Services by type of business</h1>'
                   f'<p class="sub">What Creosote Labs does for each kind of business, with typical projects and pricing.</p></div></section>'
                   f'<section class="block"><div class="wrap prose">{ind}</div></section>{site.book()}')

    locs = '<ul class="hub">' + "".join(
        f'<li><strong>{link(f"{l["slug"]}/", l["name"])}</strong><br><span class="small">' +
        " · ".join(link(f'{s["slug"]}/{l["slug"]}/', s["name"]) for s in services
                   if ("service-location", s["slug"], None, l["slug"]) in by_key) + "</span></li>"
        for l in locations) + "</ul>"
    site.page(path="locations/index.html", title="Locations · Creosote Labs",
              meta="Creosote Labs serves businesses across Arizona, on site in northern Arizona and remotely statewide.",
              body=f'<section class="page-title"><div class="wrap"><p class="eyebrow">Locations</p><h1>Services by location</h1></div></section>'
                   f'<section class="block"><div class="wrap prose">{locs}</div></section>{site.book()}')

    for s in services:
        segs = "".join(f'<li>{link(f"{s["slug"]}/{g["slug"]}/", g["name"])}</li>' for g in segments
                       if ("service-segment", s["slug"], g["slug"], None) in by_key)
        towns = "".join(f'<li>{link(f"{s["slug"]}/{l["slug"]}/", l["name"])}</li>' for l in locations
                        if ("service-location", s["slug"], None, l["slug"]) in by_key)
        site.page(path=f'{s["slug"]}/index.html', title=f'{s["name"]} · Creosote Labs', meta=s["summary"],
                  body=f'<section class="page-title"><div class="wrap"><p class="eyebrow">Services</p><h1>{esc(s["name"])}</h1>'
                       f'<p class="sub">{esc(s["summary"])}</p></div></section>'
                       f'<section class="block"><div class="wrap prose"><h2 class="h3">What we do</h2>{ul(s["what_we_do"])}'
                       f'<h2 class="h3">Pricing</h2><p>{esc(s["pricing_summary"])}</p>'
                       f'<h2 class="h3">By type of business</h2><ul class="hub cols">{segs}</ul>'
                       f'<h2 class="h3">By location</h2><ul class="hub cols">{towns}</ul></div></section>{site.book()}')

    for l in locations:
        svcs = "".join(f'<li>{link(f"{s["slug"]}/{l["slug"]}/", f"{s["name"]} in {l["name"]}")}</li>' for s in services
                       if ("service-location", s["slug"], None, l["slug"]) in by_key)
        segs = "".join(f'<li>{link(f"{l["slug"]}/{g["slug"]}/", g["name"])}</li>' for g in segments
                       if ("segment-location", None, g["slug"], l["slug"]) in by_key)
        seg_block = f'<h2 class="h3">By type of business</h2><ul class="hub cols">{segs}</ul>' if segs else ""
        site.page(path=f'{l["slug"]}/index.html', title=f'Business services in {l["name"]}, {l["state"]} · Creosote Labs',
                  meta=f'AI consulting, systems and automation, website development, and team AI training for businesses in {l["name"]}, {l["state"]}.',
                  body=f'<section class="page-title"><div class="wrap"><p class="eyebrow">Locations</p><h1>Business services in {esc(l["name"])}</h1></div></section>'
                       f'<section class="block"><div class="wrap prose"><h2 class="h3">Services</h2><ul class="hub cols">{svcs}</ul>{seg_block}</div></section>{site.book()}')


# ---------------------------------------------------------------- build
def main():
    site = Site()
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy(f, DOCS / f.name)
    media = CONTENT / "media"
    if media.exists():
        shutil.copytree(media, DOCS / "media")
    (DOCS / ".nojekyll").write_text("")
    if filled(site.cfg.get("custom_domain")):
        (DOCS / "CNAME").write_text(site.cfg["custom_domain"].strip() + "\n")

    pages = CONTENT / "pages"
    home = jload(pages / "home.json")
    build_home(site, home)
    build_training(site, jload(pages / "training.json"))
    build_work(site, jload(pages / "work.json"))
    build_writing(site, jload(pages / "writing.json"))
    build_about(site, jload(pages / "about.json"))

    landing_dir = CONTENT / "landing" / "pages"
    landing = [jload(f) for f in sorted(landing_dir.glob("*.json"))] if landing_dir.exists() else []
    if landing:
        build_landing(site, landing,
                      jload(CONTENT / "landing" / "services.json"),
                      jload(CONTENT / "landing" / "segments.json"),
                      jload(CONTENT / "landing" / "locations.json"), home)

    today = datetime.date.today().isoformat()
    urls = "".join(f"<url><loc>{esc(site.base_url + site.url(p).replace('index.html', ''))}</loc><lastmod>{today}</lastmod></url>"
                   for p in site.pages_out)
    (DOCS / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n'
                                      f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site.base_url}{site.url('sitemap.xml')}\n")
    print(f"built {len(site.pages_out)} pages -> {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
