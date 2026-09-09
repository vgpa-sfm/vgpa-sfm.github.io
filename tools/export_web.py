#!/usr/bin/env python3
"""Pack COLMAP reconstructions into a compact binary the web viewer reads.

A points3D.txt is 5-12 MB of ASCII for what is really 9 bytes of information
per point.  Positions are quantised to 16 bits inside the scene's own
bounding box, which at these scene sizes is far below the noise in the
reconstruction itself, and colours stay 8-bit.  Cameras ride along as a
rotation and a centre so the viewer can draw the frusta.

Layout, little-endian throughout:

    magic       4s      "VGPA"
    version     u32     1
    n_points    u32
    n_cams      u32
    bbox_min    3f32    quantisation origin
    bbox_step   3f32    world units per quantisation step
    centre      3f32    what the viewer should orbit
    radius      f32     of the framing box
    up          3f32
    az0         f32     opening azimuth, degrees
    fscale      f32     frustum size in world units
    positions   u16 * 3 * n_points
    colours     u8  * 3 * n_points
    cameras     f32 * 12 * n_cams    (rotation row-major, then centre)
"""
import argparse
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import colmap_io as C            # noqa: E402
import scenes as SC              # noqa: E402

MAGIC = b"VGPA"
VERSION = 1


def thin(scene, cap):
    """Cap the cloud, keeping the best-observed points.

    0141 has 258k points, which is a 2.4 MB download and a lot of geometry
    for a session that turns out to be software-rendering.  Points seen in
    more images are both more reliable and more structural, so the cut falls
    on the short tracks; the shape survives, the haze goes.
    """
    n = len(scene["xyz"])
    if cap is None or n <= cap:
        return scene, n
    order = np.argsort(-scene["track"])          # longest tracks first
    keep = np.sort(order[:cap])
    out = dict(scene)
    for k in ("xyz", "rgb", "track"):
        out[k] = scene[k][keep]
    return out, n


def pack(scene):
    xyz = scene["xyz"].astype(np.float64)
    lo = xyz.min(0)
    step = np.maximum((xyz.max(0) - lo) / 65535.0, 1e-12)
    q = np.clip(np.round((xyz - lo) / step), 0, 65535).astype("<u2")

    cams = np.concatenate([scene["rot"].reshape(-1, 9),
                           scene["centre"].reshape(-1, 3)], axis=1)

    head = struct.pack("<4sII", MAGIC, VERSION, len(q))
    head += struct.pack("<I", len(cams))
    head += struct.pack("<3f", *lo.astype(np.float32))
    head += struct.pack("<3f", *step.astype(np.float32))
    head += struct.pack("<3f", *scene["frame_centre"].astype(np.float32))
    head += struct.pack("<f", float(scene["radius"]))
    head += struct.pack("<3f", *scene["up"].astype(np.float32))
    head += struct.pack("<f", float(scene["az0"]))
    head += struct.pack("<f", float(scene["frustum_scale"]))
    return (head + q.tobytes() + scene["rgb"].astype(np.uint8).tobytes()
            + cams.astype("<f4").tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.path.join(HERE, "..", ".."))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "static", "recon"))
    ap.add_argument("--max-points", type=int, default=150000,
                    help="cap per scene; 0 keeps every point")
    ap.add_argument("--only", default=None, help="comma-separated scene keys")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None
    os.makedirs(args.out, exist_ok=True)

    manifest = []
    for sc in SC.SCENES:
        if only and sc["key"] not in only:
            continue
        src = SC.path_for(args.root, sc)
        if not os.path.isdir(src):
            print("  ! missing %s" % src)
            continue
        S = C.load_scene(src)
        S, n_full = thin(S, args.max_points or None)
        blob = pack(S)
        path = os.path.join(args.out, sc["key"] + ".vgpa")
        with open(path, "wb") as fh:
            fh.write(blob)
        manifest.append(dict(
            key=sc["key"], label=sc["label"], dataset=sc["dataset"],
            n_input=sc["n_input"], n_registered=S["n_images"],
            n_points=len(S["xyz"]), n_points_full=n_full, bytes=len(blob),
            grid=sc.get("grid", True)))
        print("  %-14s %6d pts%s  %4d cams  %6.2f MB"
              % (sc["key"], len(S["xyz"]),
                 (" (of %d)" % n_full) if n_full != len(S["xyz"]) else " " * 11,
                 len(S["centre"]), len(blob) / 1e6))

    with open(os.path.join(args.out, "scenes.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)


if __name__ == "__main__":
    main()
