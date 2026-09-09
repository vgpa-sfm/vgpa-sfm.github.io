#!/usr/bin/env python3
"""Render an orbit around a COLMAP reconstruction to an animated WebP/GIF.

There is no ffmpeg, no OpenGL and no Open3D on this machine, so this does
the whole thing in numpy: project the points through a pinhole camera,
splat them back-to-front, then draw the camera frusta over the top with
Pillow.  For sparse SfM clouds that is all a renderer needs to be, and it
runs anywhere numpy does.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import colmap_io as C                                          # noqa: E402

ACCENT = (184, 55, 31)          # the frustum vermilion used across the paper
BG = (255, 255, 255)


def look_at(eye, target, up):
    """World-to-camera rotation, COLMAP style: +Z forward, +Y down."""
    z = target - eye
    z /= np.linalg.norm(z)
    x = np.cross(z, up)
    nx = np.linalg.norm(x)
    if nx < 1e-8:                                   # up is parallel to view
        x = np.cross(z, np.array([1.0, 0.0, 0.0]))
        nx = np.linalg.norm(x)
    x /= nx
    y = np.cross(z, x)
    return np.stack([x, y, z])


def project(pts, R, eye, f, cx, cy):
    cam = (pts - eye) @ R.T
    z = cam[:, 2]
    ok = z > 1e-6
    u = np.full(len(pts), -1e9)
    v = np.full(len(pts), -1e9)
    u[ok] = f * cam[ok, 0] / z[ok] + cx
    v[ok] = f * cam[ok, 1] / z[ok] + cy
    return u, v, z, ok


def build_frusta(rots, centres, scale, aspect=1.5):
    """All camera pyramids as one vertex array plus an edge index list.

    The frusta do not move between frames, so they are built once: five
    vertices per camera (apex and four image corners) and eight edges.
    """
    d = scale
    w, h = d * 0.6 * aspect, d * 0.6
    corners = np.array([[-w, -h, d], [w, -h, d], [w, h, d], [-w, h, d]])
    n = len(centres)
    verts = np.empty((n, 5, 3))
    verts[:, 0] = centres
    for k in range(4):
        verts[:, k + 1] = centres + corners[k] @ rots       # rows are the axes
    base = np.arange(n)[:, None] * 5
    e = np.array([[0, 1], [0, 2], [0, 3], [0, 4],
                  [1, 2], [2, 3], [3, 4], [4, 1]])
    edges = (base[:, :, None] + e[None]).reshape(-1, 2)
    return verts.reshape(-1, 3), edges


def draw_edges(img, verts, edges, R, eye, f, cx, cy, colour, samples=28,
               opacity=0.88, k=0.75):
    """Scatter-rasterise line segments and composite them with alpha.

    Eight edges per camera and a thousand cameras is eight thousand Pillow
    line calls a frame; sampling each segment and scattering the samples is
    one vectorised pass instead.  The samples accumulate into a coverage
    buffer rather than being written straight down, so a lone camera reads as
    a light outline while a dense trail of them saturates -- which keeps the
    thousand-image scenes from turning into a solid red slab.
    """
    H, W = img.shape[:2]
    u, v, z, ok = project(verts, R, eye, f, cx, cy)
    a, b = edges[:, 0], edges[:, 1]
    good = ok[a] & ok[b]
    if not good.any():
        return
    a, b = a[good], b[good]
    t = np.linspace(0.0, 1.0, samples)[None, :]
    px = (u[a][:, None] * (1 - t) + u[b][:, None] * t).ravel()
    py = (v[a][:, None] * (1 - t) + v[b][:, None] * t).ravel()
    xi, yi = np.round(px).astype(np.int64), np.round(py).astype(np.int64)
    cov = np.zeros((H, W), np.float32)
    for dx, dy in ((0, 0), (1, 0), (0, 1)):
        X, Y = xi + dx, yi + dy
        m = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
        np.add.at(cov, (Y[m], X[m]), 1.0)
    alpha = (1.0 - np.exp(-cov * k))[:, :, None] * opacity
    np.copyto(img, (img * (1.0 - alpha) + np.array(colour, np.float32) * alpha
                    ).astype(np.uint8))


def render(xyz, rgb, frusta, centre, radius, up, azimuth, elevation=12.0,
           size=(900, 620), ss=2, fov=42.0, dist=2.35, point_px=1):
    W, H = size[0] * ss, size[1] * ss
    a, e = np.radians(azimuth), np.radians(elevation)
    fwd = np.cross(up, np.array([up[1], up[2], up[0]]))         # any ⟂ to up
    fwd /= np.linalg.norm(fwd)
    side = np.cross(up, fwd)
    offset = (np.cos(a) * fwd + np.sin(a) * side) * np.cos(e) + up * np.sin(e)
    eye = centre + offset * radius * dist
    R = look_at(eye, centre, up)
    f = 0.5 * H / np.tan(np.radians(fov) / 2.0)
    cx, cy = W / 2.0, H / 2.0

    img = np.empty((H, W, 3), np.uint8)
    img[:] = BG
    u, v, z, ok = project(xyz, R, eye, f, cx, cy)
    px, py = np.round(u).astype(np.int64), np.round(v).astype(np.int64)
    r = point_px * ss // 2 + 1
    vis = ok & (px >= r) & (px < W - r) & (py >= r) & (py < H - r)
    idx = np.nonzero(vis)[0]
    idx = idx[np.argsort(-z[idx])]                 # far first, near overwrites
    if len(idx):
        offs = [(dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1)
                if dx * dx + dy * dy <= r * r]
        cols = rgb[idx]
        for dx, dy in offs:
            img[py[idx] + dy, px[idx] + dx] = cols

    if frusta is not None:
        draw_edges(img, frusta[0], frusta[1], R, eye, f, cx, cy, ACCENT)
    return Image.fromarray(img).resize(size, Image.LANCZOS)
