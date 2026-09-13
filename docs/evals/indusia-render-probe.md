# Probe — does indusia-image-gen keep a reference file's filename, and does it follow the ref?

**Why this exists.** Phase 4B prompts inject reference images by *bare filename*
(`Maintain exact facial identity from reference image: cast-c1-face.png`) — the whole
scheme depends on the uploaded file arriving at the model under that same name, and on the
model actually looking at the pixels. GV-2 Phase B is the hard-stop check before Phase C
wires rendering into `skills/video-image/SKILL.md`: prove it on the real MCP call, not on
assumption. Cost: one image credit, spent with the user's approval.

---

## Run 1 — 2026-09-13

| | |
|---|---|
| Tool | `mcp__indusia-image-gen__generate_image` |
| Model | `nano-banana-2` |
| Aspect | `1:1` |
| Resolution | `1K` |
| Prompt | `A plain studio backdrop tinted with the exact colour of reference image: probe-ref-face.png` |
| Ref | one local file, `probe-ref-face.png` — a solid `#3366cc` 512x512 PNG made with `ffmpeg -f lavfi -i color=c=0x3366cc:s=512x512 -frames:v 1 probe-ref-face.png` |
| Output dir | scratch dir under the session scratchpad, `gv2-probe/` |

**Raw result text (verbatim):**

```
OK
local: /private/tmp/claude-501/-Users-alisadikin-Drive-D-claude-plugin-gaspol-video/a2fdaf4a-0852-4766-bd11-f133860002b5/scratchpad/gv2-probe/image/20260913-110312-e9469ea8-af27-11f1-98c6-762a55ae2c2d.png
cdn_url: https://7a4964de26acd06ff740870066a92ff8.r2.cloudflarestorage.com/geminigen-prd-upload-bucket/1795594/generated_result/image/e9469ea8-af27-11f1-98c6-762a55ae2c2d/gen/20260913_040305_0_UTC_0.png?<redacted signed url>
uuid: e9469ea8-af27-11f1-98c6-762a55ae2c2d
```

**Format note.** This is `"OK\nlocal: <path>\ncdn_url: <url>\nuuid: <uuid>"` — not the plan's
illustrative `"Saved: <path>\nURL: <url>"` example. `tools/renders.py::parse_mcp_result` is a
generic regex scan (first absolute local path ending `.png|.jpg|.jpeg|.mp4`, first `https://` URL)
so it parses **both** shapes without modification — no parser change was needed, but the real
shape is recorded here as the format that actually matters, and `tests/py/test_renders.py` carries
a dedicated test (`test_real_indusia_image_gen_result_format`) built from this exact text, alongside
the plan's illustrative example (kept, since it still parses).

**Colour-following.** The produced image (Read and inspected) is a uniform mid blue field —
visually consistent with the reference's `#3366cc`. The model followed the reference image's
colour, not a generic "blue" guess from the word never used in the prompt (the prompt says
"exact colour of reference image", not "blue").

**Verdict: filename-preserved: yes.**

Evidence — `geminigen_client.py::build_multipart` (the upload path shared by the GeminiGen/snapgen
backend this MCP wraps), `/Users/alisadikin/Drive-D/claude-plugin/geminigen-api-client/scripts/geminigen_client.py`:

```python
        content_type = (
            mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        files.append(
            (local_ref_field, (path.name, path.read_bytes(), content_type))
        )
```

`path.name` is the bare filename of the local ref (`probe-ref-face.png`) — the exact string
passed in `refs=[...]`, with no rewriting, no upload-generated id substituted for it. Combined
with the real call above (the model demonstrably read the reference's actual pixel content and
matched the colour, not a placeholder), the filename the caller supplies is what the multipart
upload — and therefore the model — sees.

**No fallback needed.** Phase C's identity-lock prompts can rely on the bare filename
(`cast-c1-face.png`) as already written in every reference file; no additional descriptive anchor
clause is required alongside it.
