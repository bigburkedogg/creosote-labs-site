# Creosote Labs — website

Static site, five pages, no framework. Creosote design system (forest / cream / tan;
Fraunces, Inter, JetBrains Mono).

```
index.html      Offerings (home) — review, rebuilds, on-site days, training, proof, promises
training.html   Team training — prices, before the day, agenda, what each person leaves with
work.html       Client work (Canyon REO) + lab builds
writing.html    Notes and videos, email signup
about.html      Brian
styles.css      all styles; tokens at the top
site.js         mobile nav + current-page marker
tools/build_preview.py   assembles dist/preview.html (single file, hash routing) for artifacts/email
serve.command   double-click to serve locally at http://localhost:8785
```

## Placeholders

Anything wrapped in `<span class="tk">…</span>` or a `.tk-box` is a placeholder and renders
yellow. Remove the class when the real thing goes in. Current list:

- Booking link (every page's "Pick a time" button and the header button, which points at `#book`)
- Ben Dove's quote and permission to name Canyon REO; link to the live meal planner; two screenshots
- One-page training PDF
- Live links for Longtable and Modern Lyceum; Scenario screenshots on demo data; receipt-pipeline start month
- "Now building" line on Work
- Three writing entries (draft titles in place), YouTube link, list-tool hookup for the signup form
- Photo and the one-sentence COO line on About

## Run locally

`./serve.command` or `python3 -m http.server 8785` from this folder.

## Preview file

`python3 tools/build_preview.py` writes `dist/preview.html` (ignored by git). Pages are the
source of truth; never edit the preview directly.

## Deploy

Any static host works (Cloudflare Pages, Netlify, Vercel, GitHub Pages). Brian picks.
Point the domain at the host; no build step required.
