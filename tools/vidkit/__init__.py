"""vidkit: reusable animation / video-assembly helpers distilled from finished productions.

Stdlib + ffmpeg except ``bond`` (cv2, numpy). Run the CLI from the plugin root:
``python3 -m tools.vidkit --help``.
"""
from . import beats, color, colormatch, encoder, ff, gates, join, loudness, patch, sheet, speech, stages, synth, track  # noqa: F401
