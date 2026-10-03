# Creosote Labs — website

Brian Burke's software studio, shown through the things it has built. A static site:
`build.py` reads `content/` and writes `docs/`, which is what gets published. Standard
library only, no dependencies, no build step on the server.

```
content/site.json            brand, owner, email, nav, base path/URL, custom domain
content/pages/*.json         one file per page — all page copy lives here
content/writing/*.md         one file per post — the writing archive
content/media/               images; project screenshots live in content/media/projects/
assets/                      styles.css, site.js, favicon.svg — copied to docs/ as-is
build.py                     content + assets -> docs/, then checks every internal link
docs/                        generated output. Never edit by hand; it is deleted and
                             rewritten on every build, and it is committed so the host
                             has something to serve.
admin/                       the JSON editing app (server.py + ui.html)
admin.command                double-click: opens http://localhost:8786
serve.command                double-click: builds and serves at http://localhost:8785
```

## Pages

Each `content/pages/<name>.json` maps to `<name>.html`, except `home.json`, which
becomes `index.html`. `build.py` has one renderer per page and a table (`BUILDERS`)
that wires them up; a JSON file with no renderer is skipped with a note rather than
silently ignored. Delete a page's JSON and the page disappears, along with any nav or
footer link pointing at it.

| File | Page | What it holds |
|---|---|---|
| `home.json` | `index.html` | The two-line hero (`hero.h1`, `hero.sub`), the ids of the six projects shown as cards (`projects_featured`), the short About (`about_text`) and the Contact line (`contact_text`). The latest writing appears between About and Contact once Writing is listed (see below). |
| `projects.json` | `projects.html` | Every project, in `groups` (*For clients*, *Products*, *Teaching software*, *Tools*). |
| `about.json` | `about.html` | `h1`, `text` (a blank line starts a new paragraph) and the closing `contact` line. |
| `contact.json` | `contact.html` | `h1` and `text`. There is no form. |
| `writing.json` | `writing.html` | The writing archive. See *Writing*. |

The nav and footer come from `nav` in `site.json`. The footer is one line (`brand` ·
`owner` · `email`) and the nav links.

Two old addresses forward to their replacements, keeping any `#anchor`:
`systems.html` → `projects.html` and `work-with-us.html` → `contact.html`. The v2
anchors whose project id changed (`private-university`, `assessment-course-engine`,
`teaching-apps`, `internal-systems`, `client-work`) are renamed on the way. Both are in
`ALIASES` in `build.py`.

### Projects

```
{
  "id": "sigmap",                   anchor on projects.html; home.json features by id
  "name": "sigmap",
  "status": "In use",               the mono status line under the name
  "summary": "One sentence.",       the home card; empty = the first sentence of text
  "text": "The write-up.",          projects.html; a blank line starts a new paragraph
  "detail": "One line.",            the line at the foot of the entry (optional)
  "image": "projects/sigmap.png",   a file under content/media/ (optional)
  "href": ""                        outside link, labelled with its address (optional)
}
```

Screenshots are 1440x900 PNGs in `content/media/projects/`, shown at 16:10 with a thin
border, beside the text on wide screens and above it on phones. The build copies every
image in `content/media/` to `docs/media/` and checks each copy; a PNG that does not end
in its IEND chunk (still being written, or cut short) is left out with a note. An entry
whose image is missing is shown without one: no empty box and no broken image. The
build's output lists the screenshots it showed and the ones it could not find.

Client work is described by what it does. Do not put a client's name, the practice
owner's name, personal finance figures or a child's name in any of these fields, and
check a screenshot for the same before pointing an entry at it.

### Copy in the JSON files

Long text fields (`text`, `intro`, `about_text` and the like) are plain text with a
little inline Markdown: a blank line starts a new paragraph, and `[label](href)`,
`**bold**`, `*italic*` and `` `code` `` work. Internal links are written as page paths
(`projects.html`) and get the base path added at build time. An empty field is left off
the page.

## Writing

One Markdown file per post in `content/writing/`. The admin app edits JSON, not posts;
posts are written in a text editor.

Writing is always built (`writing.html` and `feed.xml`), but it stays out of the nav,
the footer and the home page until `min_published` posts are published (`writing.json`,
default 3). Until then `writing.html` is `noindex`, it is left out of the sitemap, and no
page links to the feed. Once the count is reached, Writing appears in the nav and the
footer, the footer gains an RSS link, and the home page lists the latest posts.

Name the file `YYYY-MM-DD-some-slug.md`. The date and slug are read from the filename
unless the front matter overrides them.

```
---
title: What the source actually says
slug: what-the-source-actually-says
date: 2026-09-22
standfirst: One sentence under the headline. Optional.
draft: false
canonical: https://example.substack.com/p/what-the-source-actually-says
---

Body starts here.
```

| Key | |
|---|---|
| `title` | Required in practice; falls back to the slug. |
| `slug` | URL segment. Defaults to the filename minus the date. |
| `date` | `YYYY-MM-DD`. Sorts the archive and sets the feed's `pubDate`. |
| `standfirst` | Optional. Shown under the headline, used as the meta description and the feed summary. |
| `draft` | `true` keeps the post out of `docs/` entirely: it is not built, listed, put in the feed or the sitemap, and it does not count toward `min_published`. `docs/` is public, so a draft exists only in `content/writing/` until it is published. |
| `canonical` | Only when the piece ran somewhere else first. Points the page's canonical link there and prints "First published at …" above the body. Leave it out and this site is the canonical home, which is the default and the intent. |

Posts are published at `/writing/<slug>/`, the archive is `/writing.html` and the feed
is `/feed.xml`.

**Cross-posting to Substack:** publish here first, leave `canonical` out, then paste the
post into Substack. Substack's own canonical tag will point back here if you set it in
its post settings. Only use the `canonical` key for the reverse case — something that
went out on Substack before it went up here.

### Markdown supported

A small subset, on purpose: `##` and `###` headings, paragraphs, `-` and `1.` lists,
`>` quotes, ` ``` ` fenced code, `---` rules, `**bold**`, `*italic*`, `` `code` ``, and
`[label](url)`.

One addition: `[[text in double brackets]]` renders as a yellow `Placeholder —` chip.
Use it in a post for a figure or a citation you have not confirmed yet — it is loud on
the page and impossible to publish by accident without noticing. A search of `docs/`
for "Placeholder" finds every one.

## Build and preview

```
/opt/homebrew/bin/python3 build.py      # system python3 is too old
```

`serve.command` builds and serves `docs/` at
http://localhost:8785/creosote-labs-site/index.html.

The build prints a note for anything that needs attention: a post with no date, two
posts claiming one slug, a nav link with no page behind it, a featured project id that
`projects.json` does not define, an image that is incomplete, an unset `base_url`. After
writing `docs/` it checks every internal `href` and `src` on every page, including
`#anchors`, and prints a note for each one that does not resolve; the last line of
output gives the count.

## Deploying on Render

The repo is `bigburkedogg/creosote-labs-site` on GitHub. Render watches `main` and
redeploys on every push.

**Before the first deploy**, in `content/site.json`:

- `base_path` → `""` (it exists only for GitHub Pages project sites, which serve the
  site under a subdirectory; Render serves it at the root)
- `base_url` → the origin Render gives you, e.g. `https://creosote-labs.onrender.com`,
  or the custom domain once it is live. Absolute URLs in `sitemap.xml` and `feed.xml`
  come from this, and both are wrong without it. The build warns when it is empty.

Then rebuild (`python3 build.py`), commit `docs/`, and push.

**In the Render dashboard:**

1. **New** → **Static Site**.
2. Connect the GitHub account if it is not already connected, then pick
   `bigburkedogg/creosote-labs-site`.
3. **Name**: `creosote-labs`. This becomes `creosote-labs.onrender.com`, so take
   something you would not mind seeing in a link.
4. **Branch**: `main`.
5. **Root Directory**: leave empty.
6. **Build Command**: leave empty. The site is committed pre-built.
7. **Publish Directory**: `docs`
8. **Create Static Site**. The first deploy takes a minute or two; the URL is at the
   top of the service page.

Static sites are free on Render, and auto-deploy on push is on by default.

`render.yaml` in this repo describes the same service as a Blueprint, with the security
headers filled in. If you would rather create it that way: **New** → **Blueprint** →
pick the repo → **Apply**. Either route produces one static site; do not do both.

## Custom domain

`creosotelabs.com` does not resolve today, so this is for whenever the domain is bought.

1. Buy the domain.
2. Render dashboard → the static site → **Settings** → **Custom Domains** → **Add
   Custom Domain**. Add both `creosotelabs.com` and `www.creosotelabs.com`.
3. Render then shows the exact DNS records for each one — typically an `A` record for
   the apex and a `CNAME` to `<name>.onrender.com` for `www`. **Use the values Render
   displays**, not values written down here; they are the authoritative ones and they
   have changed before.
4. Create those records at the registrar. Render verifies them and issues a TLS
   certificate automatically, usually within the hour. The dashboard shows the state of
   both the DNS check and the certificate.
5. Set `base_url` in `content/site.json` to `https://creosotelabs.com`, rebuild, commit
   `docs/`, push. This is what updates the canonical tags, the sitemap and the feed.

`custom_domain` in `site.json` writes `docs/CNAME`, which only GitHub Pages reads.
Render ignores it. Harmless to leave empty.
