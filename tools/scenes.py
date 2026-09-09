"""Which reconstructions go on the project page.

Paths are relative to RUN, the fine-tuning run the paper's numbers come
from.  `grid=False` keeps a scene exported -- its .vgpa and stills are still built --
without giving it a card in the interactive grid. 0141 uses this because it is
shown in the teaser instead.

`label` is what the page shows.  `n_input` is the number of images the scene
was given, which lets the page say "registered N of M" -- it is set only
where the paper reports it; the two MegaDepth scenes here are the full
collections, not the 300-image subsets the tables use, so their input count
is left out rather than guessed.
"""
import os

RUN = ("results/GNN_check_batch16_4layers_dense2/2026_06_30_11_56_05")

SCENES = [
    dict(key="0141", label="MegaDepth 0141", dataset="MegaDepth",
         group="FINE_TUNE", n_input=None, grid=False),
    dict(key="0493", label="MegaDepth 0493", dataset="MegaDepth",
         group="FINE_TUNE", n_input=None, grid=False),
    dict(key="0455", label="MegaDepth 0455", dataset="MegaDepth",
         group="FINE_TUNE", n_input=None),
    dict(key="0023", label="MegaDepth 0023", dataset="MegaDepth",
         group="FINE_TUNE", n_input=None),
    dict(key="Notre_Dame", label="Notre Dame", dataset="1DSfM",
         group="FINE_TUNE_1dsfm_regular", n_input=549),
    dict(key="Ellis_Island", label="Ellis Island", dataset="1DSfM",
         group="FINE_TUNE_1dsfm_regular", n_input=227),
    dict(key="NYC_Library", label="NYC Library", dataset="1DSfM",
         group="FINE_TUNE_1dsfm_regular", n_input=330),
    dict(key="Yorkminster", label="Yorkminster", dataset="1DSfM",
         group="FINE_TUNE_1dsfm_regular", n_input=432),
]


def path_for(root, scene, recon="recon_Ep200"):
    return os.path.join(root, RUN, scene["group"],
                        "%s new_ba" % scene["key"], "colmap_reconstructions", recon)
