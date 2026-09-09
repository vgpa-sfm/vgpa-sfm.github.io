"""Minimal reader for COLMAP's text model format.

pycolmap is not installed here and is not needed: the text format is three
whitespace-separated files, and we only want camera centres and the point
cloud.  Everything below is numpy only.
"""
import os

import numpy as np


def qvec2rotmat(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * z * w, 2 * x * z + 2 * y * w],
        [2 * x * y + 2 * z * w, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * x * w],
        [2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x * x - 2 * y * y]])


def read_points3D(path, max_error=None):
    """-> xyz (N,3) float64, rgb (N,3) uint8, track_len (N,) int32"""
    xyz, rgb, tl = [], [], []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.split()
            err = float(f[7])
            if max_error is not None and err > max_error:
                continue
            xyz.append((float(f[1]), float(f[2]), float(f[3])))
            rgb.append((int(f[4]), int(f[5]), int(f[6])))
            tl.append((len(f) - 8) // 2)
    return (np.asarray(xyz, np.float64), np.asarray(rgb, np.uint8),
            np.asarray(tl, np.int32))


def read_images(path):
    """-> dict name -> (R (3,3), t (3,), centre (3,)); one entry per image.

    COLMAP writes two lines per image; the second holds the 2D points, which
    we skip."""
    out = {}
    with open(path) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        f = lines[i].split()
        q = np.array([float(v) for v in f[1:5]])
        t = np.array([float(v) for v in f[5:8]])
        R = qvec2rotmat(q)
        out[f[9] if len(f) > 9 else f[0]] = (R, t, -R.T @ t)
        i += 2                       # skip the POINTS2D line
    return out


def read_cameras(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.split()
            out[int(f[0])] = dict(model=f[1], w=int(f[2]), h=int(f[3]),
                                  params=[float(v) for v in f[4:]])
    return out


# ---------------------------------------------------------------- framing --
def robust_frame(xyz, centres, keep=98.0):
    """Centre and radius that ignore the far-flung stray points.

    Every reconstruction has a handful of points hundreds of units from the
    model.  Framing on the true bounding box would shrink the interesting
    part to nothing, so the box is taken from percentiles of the points that
    the cameras actually look at, unioned with the camera centres.
    """
    lo = np.percentile(xyz, (100.0 - keep) / 2.0, axis=0)
    hi = np.percentile(xyz, 100.0 - (100.0 - keep) / 2.0, axis=0)
    if len(centres):
        # Only the bulk of the cameras gets a say.  A scene shot as a long
        # walk has a camera trail far longer than the structure, and framing
        # on all of it shrinks the subject to nothing.
        lo = np.minimum(lo, np.percentile(centres, 10.0, axis=0))
        hi = np.maximum(hi, np.percentile(centres, 90.0, axis=0))
    centre = (lo + hi) / 2.0
    radius = float(np.max(hi - lo)) / 2.0
    return centre, max(radius, 1e-6)


def inliers(xyz, centre, radius, factor=1.6):
    """Points inside `factor` radii of the frame centre."""
    return np.linalg.norm(xyz - centre, axis=1) <= radius * factor


def up_vector(rotations):
    """Estimate which way is up from the cameras themselves.

    Row 1 of a world-to-camera rotation is the world direction of the
    camera's +Y, which points down the image.  People hold cameras roughly
    level, so averaging that over a photo collection recovers world "down"
    far more reliably than fitting a plane to the camera centres -- on these
    scenes the individual cameras agree with the mean to within 45 degrees
    94 to 98 per cent of the time.  Note it comes out near -X here, not
    COLMAP's usual -Y, so it is worth measuring rather than assuming.
    """
    down = np.asarray(rotations)[:, 1, :]
    m = down.mean(0)
    n = np.linalg.norm(m)
    if n < 0.3:                       # no consensus; fall back to COLMAP's
        return np.array([0.0, -1.0, 0.0])
    return -m / n


def start_azimuth(rotations, up, fwd, side):
    """Azimuth that puts the viewer where the photographers stood.

    Row 2 of a world-to-camera rotation is the world direction the camera
    looks along.  Averaging it gives the direction the collection faces, so
    the orbit opens on the view the scene was actually shot from instead of
    an arbitrary one.
    """
    look = np.asarray(rotations)[:, 2, :].mean(0)
    look -= up * (look @ up)
    n = np.linalg.norm(look)
    if n < 1e-6:
        return 0.0
    look /= n
    return float(np.degrees(np.arctan2(-look @ side, -look @ fwd)))


def orbit_basis(up):
    """Two unit vectors spanning the plane the orbit runs in."""
    fwd = np.cross(up, np.array([up[1], up[2], up[0]]))
    fwd /= np.linalg.norm(fwd)
    return fwd, np.cross(up, fwd)


def load_scene(path, trim_pct=98.0):
    """Read a COLMAP text model and put it in a frame fit to look at."""
    xyz, rgb, track = read_points3D(os.path.join(path, "points3D.txt"))
    imgs = read_images(os.path.join(path, "images.txt"))
    rot = np.array([v[0] for v in imgs.values()])
    cen = np.array([v[2] for v in imgs.values()])

    centre, radius = robust_frame(xyz, cen)
    d = np.linalg.norm(xyz - centre, axis=1)
    keep = d <= np.percentile(d, trim_pct)          # shed the stray points
    xyz, rgb, track = xyz[keep], rgb[keep], track[keep]
    centre, radius = robust_frame(xyz, cen)         # reframe on what is left

    # Frusta big enough to read individually in a 200-camera scene merge into
    # a solid slab in a 1000-camera one, so shrink them as the count grows.
    fscale = radius * 0.030 * float(np.clip(np.sqrt(260.0 / max(len(cen), 1)),
                                            0.42, 1.0))
    up = up_vector(rot)
    fwd, side = orbit_basis(up)
    return dict(xyz=xyz, rgb=rgb, track=track, rot=rot, centre=cen,
                frame_centre=centre, radius=radius, up=up, fwd=fwd, side=side,
                az0=start_azimuth(rot, up, fwd, side), frustum_scale=fscale,
                n_images=len(imgs), n_points=int(keep.sum()))
