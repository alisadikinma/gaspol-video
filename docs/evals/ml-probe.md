# ML probe: TAPNext++ and SAM 2.1 on Apple M5 Pro (GV-24 Phase A)

Machine: Apple M5 Pro, macOS 26 (Darwin 25.6.0), 48 GB. Run 2026-10-17 in a scratch venv outside the repo.
Clip: synthetic 48 frames, 512x512 RGB, seeded noise texture (128x128 cubic-upscaled) shifted +2 px/frame in x.

python: 3.14.6 (/opt/homebrew/bin/python3.14)
torch: 2.14.1
mps_available: true
tapnextpp_sha256: cb96a43444ccb4fbdb25d800b88c7ba196179a526e78f01b021a16b1c1eff6da
sam2_sha256: 6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38
tapnext_fps: mps=10.33 cpu=1.94 err_median=0.315px err_max=1.095px
sam2_fps: mps=2.81 cpu=1.14 iou_min=0.986
licence_tapnet: Apache-2.0 (code, LICENSE file); README: "All pre-trained model checkpoints released in this repository and linked from this README (including TAP-Net, TAPIR, BootsTAPIR, TAPNext, TAPNext++, and TRAJAN weights) are also licensed under Apache 2.0."
licence_sam2: Apache-2.0 (LICENSE file); README: "The SAM 2 model checkpoints, SAM 2 demo code (front-end and back-end), and SAM 2 training code are licensed under Apache 2.0" (demo fonts are OFL-1.1, not used).

Both weights allow commercial use. Checkpoints: `tapnextpp_ckpt.pt` is 2415 MB (256x256 model), `sam2.1_hiera_small.pt` is 176 MB.

Notes on the numbers: TAPNext++ fps is the 48-frame online loop after a 2-frame warmup, 64 query points (8x8 grid, x 40..400, y 40..470), with the device synchronised. SAM 2 fps is wall time for `init_state` + prompt + 48-frame propagate (steady state on mps is about 3.1 frames/s; cpu about 1.1). Same error on mps and cpu for TAPNext++ (median 0.315 px, max 1.095 px). All 64 points stayed visible. SAM 2 IoU is against the known disc, min 0.986, mean 0.988, same on both devices.

## Working install commands

```bash
/opt/homebrew/bin/python3.14 -m venv venv-ml
. venv-ml/bin/activate
pip install torch torchvision
pip install "tapnet[torch] @ git+https://github.com/google-deepmind/tapnet.git"
SAM2_BUILD_CUDA=0 pip install "git+https://github.com/facebookresearch/sam2.git"
pip install einops     # NOT pulled in by tapnet[torch]; import fails without it
curl -L -o tapnextpp_ckpt.pt https://storage.googleapis.com/dm-tapnet/tapnextpp/tapnextpp_ckpt.pt
curl -L -o sam2.1_hiera_small.pt https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt
```

Versions (`pip freeze`):

```
torch==2.14.1
torchvision==0.29.1
numpy==2.5.4
opencv-python==5.0.0.93
einops==0.8.2
tapnet @ git+https://github.com/google-deepmind/tapnet.git@730cda1c730877cfedbe01bf87fb1cadb78a565d
SAM-2 @ git+https://github.com/facebookresearch/sam2.git@2b90b9f5ceec907a1c18123530e92e794ad901a4
```

`tapnet[torch]` also pulls jax 0.11.2, jaxlib 0.11.2, jaxline 0.0.8 (extra weight; not used by the torch path). Python 3.14 has torch wheels, so no separate Python was needed. A python3.12 also exists at /opt/homebrew/bin/python3.12 but was not used.

## TAPNext++ API

The pip package ships the high-level wrapper `TAPNextPP` (module `votsp2026`). Online, frame by frame, display pixels in and out.

```python
import numpy as np
from tapnet.tapnextpp.votsp2026.model import TAPNextPP

model = TAPNextPP.from_checkpoint("tapnextpp_ckpt.pt", device="mps")  # or "cpu"; input_resolution=256 default
q = np.array([[x, y], ...], dtype=np.float32)            # [Q, 2], x then y, display pixels of the frame given
pos, vis, state = model.track_frame(frame0_bgr, q)       # frame0: [H, W, 3] uint8 BGR
for f in frames[1:]:
    pos, vis, state = model.track_frame(f, state=state)
# pos: [Q, 2] float32, x then y, display pixels. vis: [Q] bool. state: carry to next call.
```

Query frame is always the first frame passed (time index 0). Frames of any size are resized internally to 256 (`display_to_model`, `model_to_display` convert back). The BGR layout is the OpenCV default; the synthetic probe passed BGR arrays. `autocast` only applies on cuda. Inner model: `model._model(video=[1,T,H,W,3], query_points=[1,Q,3] as (t, y, x), state=...)`, only needed for batch use. Not tried: the 512 checkpoint `tapnextpp_512.ckpt`.

## SAM 2.1 API

```python
import numpy as np, torch
from sam2.build_sam import build_sam2_video_predictor

pred = build_sam2_video_predictor(
    "configs/sam2.1/sam2.1_hiera_s.yaml", "sam2.1_hiera_small.pt", device="mps")  # or "cpu"
with torch.inference_mode():
    st = pred.init_state(video_path="dir_of_jpgs")       # files 00000.jpg, 00001.jpg, ...
    pred.add_new_points_or_box(st, frame_idx=0, obj_id=1,
        points=np.array([[x, y]], np.float32), labels=np.array([1], np.int32))
    for frame_idx, obj_ids, mask_logits in pred.propagate_in_video(st):
        mask = (mask_logits[0, 0] > 0).cpu().numpy()      # [H, W] bool at original frame size
```

Points are x, y in original frame pixels. `mask_logits` is `[n_obj, 1, H, W]`. The config name is resolved by Hydra inside the sam2 package, so pass it as above (not a file path). `init_state` loads every JPEG into memory; JPEG order is by integer file stem.

## Problems seen

- `tapnet[torch]` misses `einops`: `ModuleNotFoundError: No module named 'einops'` on first import. Install it explicitly.
- SAM 2 on this install prints a UserWarning on every propagate: `cannot import name '_C' from 'sam2'` ... "Skipping the post-processing step". The CUDA connected-components extension is not built (`SAM2_BUILD_CUDA=0`). Masks are still correct (IoU 0.986), only hole filling is skipped. Harmless.
- No MPS error on either model. MPS gave 5.3x (TAPNext++) and 2.5x (SAM 2) over cpu.
- The probe is a translation of a noise texture, an easy case. The numbers show the install works and set a speed floor; they do not show accuracy on real footage.
