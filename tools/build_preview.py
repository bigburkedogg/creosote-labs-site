#!/usr/bin/env python3
"""Assemble the five static pages into one self-contained preview file
(dist/preview.html) with hash routing, so the draft can be published as a
single artifact or emailed as one file. The pages themselves stay the source
of truth; never edit the preview by hand."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [("index.html", "offerings"), ("training.html", "training"),
         ("work.html", "work"), ("writing.html", "writing"), ("about.html", "about")]
HASH = {name: "#" + slug for name, slug in PAGES}

css = (ROOT / "styles.css").read_text()
header = footer = None
mains = []
for name, slug in PAGES:
    html = (ROOT / name).read_text()
    if header is None:
        header = re.search(r"<header.*?</header>", html, re.S).group(0)
        footer = re.search(r"<footer.*?</footer>", html, re.S).group(0)
    main = re.search(r"<main>(.*?)</main>", html, re.S).group(1)
    # in-page anchors collide across pages; scope the book block by page
    main = main.replace('id="book"', f'id="book-{slug}"')
    mains.append(f'<section class="page" data-page="{slug}" hidden>{main}</section>')

def rewrite(fragment: str) -> str:
    for name, h in HASH.items():
        fragment = fragment.replace(f'href="{name}"', f'href="{h}"')
    return fragment.replace('href="#book"', 'href="#" data-book')

header = rewrite(header)
body = rewrite("\n".join(mains))

router = """
<script>
(function(){
  var pages=document.querySelectorAll('.page');
  var links=document.querySelectorAll('.nav a[href^="#"]');
  function show(){
    var slug=(location.hash||'#offerings').slice(1);
    if(!document.querySelector('.page[data-page="'+slug+'"]')) slug='offerings';
    pages.forEach(function(p){p.hidden=p.dataset.page!==slug;});
    links.forEach(function(a){ if(a.getAttribute('href')==='#'+slug) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',show); show();
  document.addEventListener('click',function(e){
    var a=e.target.closest('a'); if(!a) return;
    if(a.hasAttribute('data-book')){ e.preventDefault(); var p=document.querySelector('.page:not([hidden]) .book'); if(p) p.scrollIntoView({behavior:'smooth'}); return; }
    if(a.getAttribute('href')==='#') e.preventDefault();
  });
  var t=document.querySelector('.nav-toggle'),n=document.getElementById('nav');
  if(t&&n){t.addEventListener('click',function(){var o=n.classList.toggle('open');t.setAttribute('aria-expanded',o?'true':'false');});
    n.addEventListener('click',function(e){ if(e.target.tagName==='A') n.classList.remove('open'); });}
})();
</script>"""

out = f"""<title>Creosote Labs Site Draft</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
{css}
.draft-note {{ font-family: var(--font-mono); font-size: 12px; color: var(--tk-fg); background: var(--tk-bg); text-align: center; padding: 6px 12px; }}
</style>
<div class="draft-note">Rough draft · yellow TK markers are placeholders · pages switch by the nav</div>
{header}
<main>
{body}
</main>
{footer}
{router}
"""
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "preview.html").write_text(out)
print(f"wrote {dist / 'preview.html'} ({len(out):,} bytes)")
