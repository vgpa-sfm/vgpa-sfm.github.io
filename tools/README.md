# Reconstruction media for the project page

Turns the COLMAP models our pipeline writes into what the page shows: an
orbit animation, a poster still, and a compact binary the in-page 3D viewer
reads.

## What runs

```bash
cd webpage
python tools/export_web.py      # COLMAP -> static/recon/<scene>.vgpa + scenes.json
python tools/make_media.py      # COLMAP -> <scene>.webp, .gif, .jpg + media.json
python tools/render_section.py  # scenes.json -> the cards in index.html
```

`tools/scenes.py` says which reconstructions are used; edit it and re-run all
three. `render_section.py` rewrites only what sits between the
`BEGIN/END recon-cards` markers, so the rest of `index.html` is untouched.

## Packages

Deliberately almost none, because the machine this was built on has no
pycolmap, no Open3D, no ffmpeg and no GPU:

- **Reading COLMAP** — nothing. `tools/colmap_io.py` parses the text format
  in about a hundred lines of numpy. pycolmap would only be needed for the
  `.bin` variant.
- **Rendering the orbit** — **numpy** and **Pillow**. Points are projected
  through a pinhole camera and splatted back-to-front; the camera frusta are
  scatter-rasterised into a coverage buffer and alpha-composited. No OpenGL,
  so it runs on any headless box.
- **Encoding** — **Pillow**. Animated WebP for the page, GIF for slides and
  READMEs, JPEG for the poster. There is no ffmpeg here, so no MP4; if you
  want one, `ffmpeg -i frame%04d.png -crf 24 out.mp4` on a machine that has
  it will be about a fifth the size of the WebP.
- **The 3D viewer** — **three.js r160**, vendored into
  `static/vendor/three/` rather than pulled from a CDN, so the page works
  offline, behind a firewall, and from a copied folder. It is imported only
  when a reader presses *Explore in 3D*. To move to another release, drop in
  `build/three.module.js` and `examples/jsm/controls/OrbitControls.js` from
  the same version and leave the import map alone.

**Not viser.** viser is a Python server: it is excellent for looking at a
reconstruction on your own machine, and `request_share_url()` gives a link
that dies with the process. A project page has to keep working with nothing
running behind it, so the cloud is exported once and drawn by three.js.

## The `.vgpa` files

A `points3D.txt` is 5–12 MB of ASCII for what is really nine bytes per point.
`export_web.py` quantises positions to 16 bits inside each scene's bounding
box — far below the noise in the reconstruction itself — and keeps colours at
8 bits, which brings a scene to 0.4–0.9 MB. The exact layout is in that
file's docstring.

## Framing

Three things are measured rather than assumed, because guessing them gets
every scene wrong:

- **Up** is the mean of each camera's local down axis. People hold cameras
  level, so this recovers world up from the collection itself. On these
  scenes it comes out near **−X**, not COLMAP's usual −Y, and 94–98 % of the
  individual cameras agree with the mean to within 45°.
- **The opening view** is the mean direction the cameras look along, so a
  scene opens on the view it was photographed from instead of an arbitrary
  one.
- **The frame** ignores stray points (every model has a few hundreds of units
  out) and lets only the middle 80 % of cameras influence it, so a scene shot
  as a long walk is not shrunk to nothing by its own camera trail.

Frustum size shrinks as the camera count grows, and frusta composite with
density-aware alpha, so a lone camera reads as an outline while a
thousand-camera trail stays legible instead of turning into a red slab.

## Caveats

- CSS and JS are referenced with a `?v=<hash>` so a stale browser cache
  cannot serve an old build. `index.html` itself has no such guard, so after
  deploying, reload it once with Ctrl/Cmd-Shift-R.
- The viewer fetches its data, so **the page must be served over http://**.
  Opening `index.html` from disk shows the animation and a note saying so.
  `python -m http.server` from `webpage/` is enough to check it.
- There is no browser on the build machine, so **the 3D viewer has never been
  run**. Its binary parser and frustum geometry were cross-checked in Node
  against the numpy code that produced the animations, and they agree to
  float32 precision — but nobody has watched it paint pixels. Open one card
  before publishing.
