# Creosote Labs — website

Live: https://bigburkedogg.github.io/creosote-labs-site/ (GitHub Pages, serving `docs/` from `main`).
Every push to `main` redeploys in about a minute.

## How it's built

```
content/site.json            brand, contact, nav, booking link, base path, custom domain
content/pages/*.json         Home, Training, Work, Writing, About — all copy lives here
content/landing/             SEO landing pages: services.json, segments.json, locations.json, pages/*.json
content/media/               uploaded images (photo, screenshots)
content/notes.md             notes from the admin app for Claude
assets/                      styles.css, site.js
build.py                     content + assets -> docs/   (standard library only)
docs/                        generated output — never edit by hand, it is overwritten
admin/                       the editing app (server.py + ui.html)
admin.command                double-click: opens http://localhost:8786
serve.command                double-click: builds and serves the site at http://localhost:8785
```

## Editing copy

Double-click `admin.command`. Pick a page on the left, edit the fields, **Save** (rebuilds the
preview; the Preview button opens it), **Publish** (commits and pushes; live in about a minute).
Yellow fields are placeholders that still need real content; filling them clears the yellow on the site.

Images: upload next to the field (photo, screenshots) and Save.

Notes for Claude: the box at the bottom left saves to `content/notes.md`; Claude reads it next session.

## Landing pages

`content/landing/pages/` holds one JSON per page. URL shapes:

- `/<service>/<business-type>/`   e.g. `/ai-consulting/dental-practices/`
- `/<service>/<town>/`            e.g. `/website-development/sedona/`
- `/flagstaff/<business-type>/`   Flagstaff-only pages
- hubs: `/industries/`, `/locations/`, `/<service>/`, `/<town>/`

`build.py` also writes `sitemap.xml` and `robots.txt`.

## Custom domain

1. Buy the domain. Put it in `content/site.json` as `custom_domain`, set `base_path` to `""` and
   `base_url` to `https://<domain>`, then Publish (this writes `docs/CNAME`).
2. GitHub: `gh api -X PUT repos/bigburkedogg/creosote-labs-site/pages -f cname=<domain>`, then
   `-f https_enforced=true` once the certificate is issued.
3. DNS at the registrar: apex `A` records to 185.199.108.153, 185.199.109.153, 185.199.110.153,
   185.199.111.153; `www` `CNAME` to `bigburkedogg.github.io`.

`render.yaml` is included if the site ever moves to Render (publish path `docs`).
