# VGPA — project page

Project page for *Learning Global Camera Poses from Noisy View-Graphs for
Structure from Motion* (ECCV 2026).

A static site: hand-written HTML, one stylesheet, two scripts, no build step
and no framework. It can be served from any static host, GitHub Pages
included.

## Running it

```bash
python -m http.server 8000
```

then open <http://localhost:8000>.

It has to be served over `http://` rather than opened from disk: the
interactive viewer fetches its data, and a `file://` page is not allowed to.

## What is here

```
index.html              the whole page
static/css/style.css    one stylesheet; the palette lives at the top
static/js/main.js       theme toggle, tabs, lightbox
static/js/recon-viewer.js   the WebGL reconstruction viewer
static/vendor/three/    three.js r160, vendored (no CDN)
static/recon/           per-scene .vgpa point clouds, stills, animations
static/images/          teaser, architecture and gallery figures
tools/                  regenerates everything in static/recon/
```

`tools/README.md` covers how the reconstruction assets are produced, which
packages are involved and why, and how the scenes are framed.

## Before publishing

One placeholder is left, marked `TODO(placeholder)` in `index.html`: the
**Code** button — set its `href` and delete `data-placeholder`, which is what
draws the "soon" badge. The Paper and arXiv buttons point at arXiv.

## Note

The interactive viewer has never been opened in a browser by its author —
it was written on a machine with no display. Its binary parser and camera
geometry are cross-checked against the Python that generates the same
scenes, and the whole mount path is exercised in Node, but do open a card
once before relying on it.
