# Creosote Labs — website

A static site. `build.py` reads `content/` and writes `docs/`; Render publishes `docs/`.
Standard library only, no dependencies, no build step on the server.

```
content/site.json            brand, contact details, nav, base path/URL, custom domain
content/pages/*.json         one file per page — all page copy lives here
content/writing/*.md         one file per post — the essay archive
content/media/               images referenced from the JSON
assets/                      styles.css, site.js — copied to docs/ as-is
build.py                     content + assets -> docs/
docs/                        generated output. Never edit by hand; it is deleted and
                             rewritten on every build, and it is committed so Render
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
footer link pointing at it — links are checked against the pages the build actually
writes, and dead ones are dropped with a note in the build output.

## Writing

One Markdown file per post in `content/writing/`. The admin app edits JSON, not posts;
posts are written in a text editor.

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
| `draft` | `true` keeps the post out of the feed, the sitemap and the homepage, marks it "Draft" in the archive, and sets `noindex` on its page. It is still built, so you can read it. |
| `canonical` | Only when the piece ran somewhere else first. Points the page's canonical link there and prints "First published at …" above the body. Leave it out and this site is the canonical home, which is the default and the intent. |

Posts are published at `/writing/<slug>/`. The archive is `/writing.html`, the feed is
`/feed.xml`, and every page links to the feed in its `<head>`.

**Cross-posting to Substack:** publish here first, leave `canonical` out, then paste the
post into Substack. Substack's own canonical tag will point back here if you set it in
its post settings. Only use the `canonical` key for the reverse case — something that
went out on Substack before it went up here.

### Markdown supported

A small subset, on purpose: `##` and `###` headings, paragraphs, `-` and `1.` lists,
`>` quotes, ` ``` ` fenced code, `---` rules, `**bold**`, `*italic*`, `` `code` ``, and
`[label](url)`.

One addition: `[[text in double brackets]]` renders as a yellow placeholder chip, the
same marker the JSON pages use for unfinished copy. Use it for a figure or a citation
you have not confirmed yet — it is loud on the page and impossible to publish by
accident without noticing.

## Build and preview

```
/opt/homebrew/bin/python3 build.py      # system python3 is too old
```

`serve.command` builds and serves `docs/` at http://localhost:8785. It still opens the
old GitHub Pages path in the browser; go to http://localhost:8785/ instead.

The build prints a note for anything that needs attention: a post with no date, two
posts claiming one slug, a nav link with no page behind it, a featured project id that
`projects.json` does not define, an unset `base_url`.

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
