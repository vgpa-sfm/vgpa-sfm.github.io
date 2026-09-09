#!/usr/bin/env python3
"""Render an orbit of each scene to an animated WebP, a GIF and a poster.

WebP is the one the page uses: it carries full colour at a fraction of a
GIF's size.  The GIF is there for anywhere WebP is not an option, and the
poster JPEG is what shows before either has loaded.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import colmap_io as C            # noqa: E402
import render_orbit as RO        # noqa: E402
import scenes as SC              # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.path.join(HERE, "..", ".."))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "static", "recon"))
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--width", type=int, default=560)
    ap.add_argument("--height", type=int, default=380)
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--gif-width", type=int, default=400,
                    help="GIFs are for slides and READMEs, so they are smaller")
    ap.add_argument("--no-gif", action="store_true")
    ap.add_argument("--only", default=None, help="comma-separated scene keys")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    manifest = []

    for sc in SC.SCENES:
        if only and sc["key"] not in only:
            continue
        src = SC.path_for(args.root, sc)
        if not os.path.isdir(src):
            print("  ! missing %s" % src)
            continue
        t0 = time.time()
        S = C.load_scene(src)
        frusta = RO.build_frusta(S["rot"], S["centre"], S["frustum_scale"])
        size = (args.width, args.height)
        frames = []
        for i in range(args.frames):
            az = S["az0"] + 360.0 * i / args.frames
            frames.append(RO.render(S["xyz"], S["rgb"], frusta, S["frame_centre"],
                                    S["radius"], S["up"], az, size=size))
        dur = int(round(1000.0 / args.fps))
        stem = os.path.join(args.out, sc["key"])
        frames[0].save(stem + ".webp", "WEBP", save_all=True,
                       append_images=frames[1:], duration=dur, loop=0,
                       quality=60, method=5)
        frames[0].convert("RGB").save(stem + ".jpg", quality=86, optimize=True)
        gsize = 0
        if not args.no_gif:
            gw = args.gif_width
            gh = int(round(gw * args.height / float(args.width)))
            small = [f.resize((gw, gh), Image.LANCZOS) for f in frames[::2]]
            gif = [f.convert("P", palette=Image.ADAPTIVE, colors=64)
                   for f in small]
            gif[0].save(stem + ".gif", save_all=True, append_images=gif[1:],
                        duration=dur * 2, loop=0, optimize=True, disposal=2)
            gsize = os.path.getsize(stem + ".gif")

        rec = dict(sc, n_registered=S["n_images"], n_points=S["n_points"],
                   webp=os.path.getsize(stem + ".webp"), gif=gsize)
        manifest.append(rec)
        of = "/%d" % sc["n_input"] if sc.get("n_input") else ""
        print("  %-14s %4d%-5s imgs  %6d pts  webp %5.1fMB  gif %5.1fMB  %5.1fs"
              % (sc["key"], S["n_images"], of, S["n_points"],
                 rec["webp"] / 1e6, rec["gif"] / 1e6, time.time() - t0))

    # A --only run must not wipe the entries for the scenes it skipped.
    path = os.path.join(args.out, "media.json")
    merged = {}
    if os.path.exists(path):
        with open(path) as fh:
            for rec in json.load(fh):
                merged[rec["key"]] = rec
    for rec in manifest:
        merged[rec["key"]] = rec
    order = [s["key"] for s in SC.SCENES]
    with open(path, "w") as fh:
        json.dump(sorted(merged.values(),
                         key=lambda r: order.index(r["key"])
                         if r["key"] in order else 99), fh, indent=2)


if __name__ == "__main__":
    main()
