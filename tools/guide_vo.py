#!/usr/bin/env python3
"""Guide-voice takes: an expressive stock voice reads each line, to be converted into the cast
voice afterwards with tools/voice_changer.mjs.

    python3 tools/guide_vo.py <plan.json> <out-dir> (--voice-id ID | --voice-env NAME)
        [--stabilities 0,0.5] [--speed 1.15] [--language id] [--model eleven_v3] [--force]

plan.json = [{"id": "scene-03", "text": "[curious] Apa yang menahannya?"}, ...]
Writes <out-dir>/<id>-pemandu-take<N>.mp3, one per stability value.

Why not gen_vo.mjs: that tool speaks the FINAL narration in the cast's locked voice, on
eleven_multilingual_v2 (v3 drifts a cloned identity), one take per layer. A guide voice is the
opposite: a stock voice on eleven_v3 with audio tags ([excited], [whispers]) for delivery, several
takes at different stabilities, picked afterwards with `vidkit prosody` and tightened with
`vidkit tighten`. The cast's timbre comes later from speech-to-speech, which keeps this
performance. A take that already exists is never requested (or billed) again unless --force.

Stdlib only. The API key and voice id are read from the environment and never printed.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
EM_DASH_MESSAGE = "em dash in spoken text: the audio engine mistranslates it. Use ',' or '. ' instead"


def _check(lines):
    for line in lines:
        if not line.get("id") or not line.get("text"):
            raise ValueError(f"every line needs an id and a text: {line!r}")
        if "—" in line["text"]:
            raise ValueError(f"{line['id']}: {EM_DASH_MESSAGE}")


def generate(lines, voice_id, api_key, out_dir, stabilities=(0.0, 0.5), speed=None,
             language=None, model="eleven_v3", force=False, urlopen=urllib.request.urlopen, log=print):
    """Request every missing take. Returns all take paths in order (existing ones included)."""
    _check(lines)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for line in lines:
        for n, stability in enumerate(stabilities, 1):
            path = out / f"{line['id']}-pemandu-take{n}.mp3"
            paths.append(str(path))
            if path.exists() and not force:
                log(f"  {path.name}: exists, not requested")
                continue
            settings = {"stability": stability, "similarity_boost": 0.8}
            if speed is not None:
                settings["speed"] = speed
            body = {"text": line["text"], "model_id": model, "voice_settings": settings}
            if language:
                body["language_code"] = language
            req = urllib.request.Request(API.format(voice=voice_id), data=json.dumps(body).encode(),
                                         method="POST", headers={"xi-api-key": api_key,
                                                                 "Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=120) as resp:
                    path.write_bytes(resp.read())
            except urllib.error.HTTPError as e:
                raise RuntimeError(f"{path.name}: ElevenLabs returned {e.code} {e.read()[:300]!r}") from e
            log(f"  {path.name}: written")
    return paths


def main(argv=None, env=os.environ):
    ap = argparse.ArgumentParser(prog="guide_vo", description=__doc__.split("\n")[0])
    ap.add_argument("plan")
    ap.add_argument("out_dir")
    ap.add_argument("--voice-id", help="a stock voice id (public, safe to pass literally)")
    ap.add_argument("--voice-env", help="name of the env var that holds the voice id")
    ap.add_argument("--stabilities", default="0,0.5", help="one take per value, comma separated")
    ap.add_argument("--speed", type=float)
    ap.add_argument("--language", default="id")
    ap.add_argument("--model", default="eleven_v3")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    voice = a.voice_id or (env.get(a.voice_env) if a.voice_env else None)
    if not voice:
        print("guide_vo: give --voice-id or a --voice-env that is set", file=sys.stderr)
        return 2
    key = env.get("ELEVENLABS_API_KEY")
    if not key:
        print("guide_vo: ELEVENLABS_API_KEY not set", file=sys.stderr)
        return 2
    try:
        generate(json.loads(Path(a.plan).read_text()), voice, key, a.out_dir,
                 tuple(float(s) for s in a.stabilities.split(",")), a.speed, a.language, a.model, a.force)
    except (ValueError, RuntimeError) as exc:
        print(f"guide_vo: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
