# Physical Plausibility Gate (v3.4.0)

Read before writing Phase 4B keyframe prompts and Phase 5 platform prompts. Loaded by
`video-image`, `video-gen` and `video-script`; enforced by `video-prompt-reviewer` checks K1-K7
and C12.

## Why this file exists

Every defect below was found by the user **after** the render was paid for, in one production
(a 4-minute B2B film, catalog-2 and catalog-4, Sept 2026). None of them were caught by the
existing checks, because the prompts were *compliant* — correct refs, correct costume, correct
aspect ratio, correct negatives. They were simply not *possible*, or not *readable*.

Compliance asks "does the prompt follow the rules?". This gate asks two different questions:

1. **If this were a real object, could it be like this?**
2. **If the viewer only saw this shot, would they know what changed?**

| # | Defect class | What actually happened | Cost |
|---|---|---|---|
| 1 | Impossible mechanism | Fuel filler hole drawn on the SIDE of a truck tank (a full tank would spill); tank cap still closed while the nozzle was filling it | 3 keyframes + 2 clips |
| 2 | Duplicated / ghost objects | Two boom barriers and two RFID antennas at one gate; the fuel nozzle became two nozzles at 3.5s; a telephone handset vanished and reappeared on a stapler | 3 clips |
| 3 | Wrong orientation | Phone upside down (rear camera facing the viewer), then screen face-down; proof-photo shot from the wrong side of the subject | 2 keyframes + 3 clips |
| 4 | Unreadable direction | Truck *entering* the yard framed exactly like the truck *leaving* it — same gate, same nose-to-camera angle. The viewer cannot tell a return trip from a departure | caught pre-render, once the rule existed |
| 5 | Characters read as the same person | A male admin in a cream shirt, back to camera, read as the protagonist seen from another angle. Rejected in scene 13, then repeated in scene 15 | 2 keyframes + 2 clips |
| 6 | Overlay cannot attach | Panel mapped to an upright rectangle while the screen was a trapezoid (left edge 524px, right edge 375px); a panel tracked onto a monitor that faces away from camera grew *behind* the monitor; a guard-post screen measured 60x45px in a 1920x1080 frame | 4 re-renders (free, but a full day) |
| 7 | Continuity break across a pair | The same sensor drawn with a different body in the paired shot; a clip rendered from an evening keyframe drifting back to midday while its overlay card says 16:05 | 1 clip + 1 grading pass |
| 8 | Story logic hole | "Parts leave the store" with the clerk walking out empty-handed; a fuel sensor that reads the tank but never produces a consumption number, and a truck that never comes back | 1 clip + a whole act reflowed |
| 9 | Sound/picture mismatch | A number spoken at 6.34s while its on-screen text finished appearing at 6.8s; narration 6.87s long cut into a 6.0s clip | measurable, see scripts |

Classes 1-5 and 8 are all answerable **from the prompt alone**, before any credit is spent. That
is what this gate is for. Class 9 is measurable, and is handled by two scripts instead of prose
(`scripts/check-vo-duration.py`, `scripts/check-overlay-strings.py`).

## The Plausibility Block

Every Phase 4B scene keyframe and every Phase 5 platform prompt carries a `PLAUSIBILITY:` block
in the prompt **document** (not inside the text sent to the model). Seven questions, answered in
one line each. An unanswered question is a FAIL, not a default.

```
PLAUSIBILITY:
1. MECHANISM — <what the object is in the real world, which part opens/moves, what state it is in>
2. COUNT — <count of every story-critical object: "1 boom barrier, 1 RFID antenna, 1 sensor, 1 nozzle">
3. FLOW — <where liquid / power / load goes, and what contains it; "none" if nothing flows>
4. FACING — <which way each device, screen, lens and vehicle points, relative to camera AND to its user>
5. PAIR — <the scene this one is paired with: what must be IDENTICAL, what must DIFFER>
6. PEOPLE — <who is in frame, and the two visible axes that keep each of them distinct>
7. OVERLAY SURFACE — <target surface, its size in px at delivery resolution, frontal or oblique>
```

Each answer must then be **visible in the prompt text itself**. An answer that exists only in the
block is a note to nobody: the model never reads it.

### 1. MECHANISM → write the state, not just the object

The model draws the *category*, not the *operation*. "Refuelling a truck tank" gets you a tank,
a hose and a cap in whatever arrangement is statistically common — including a closed cap on a
tank being filled.

Write: where the opening is, whether it is open or closed right now, what holds the cap, and what
is inserted into what.

> one round filler opening on TOP of the tank, cap hanging open on its chain, the nozzle inserted
> into that opening; the side of the tank is plain metal with no second opening

Ask a domain question before writing it: *why* is it built that way? A side filler cannot fill a
tank to the top — that single question would have prevented three renders.

### 2. COUNT → count locks, with a negative

Video and image models duplicate the salient object under motion: a second barrier, a second
antenna, a second nozzle. Give an explicit count for every story-critical object, and a negative
naming the duplicate:

> exactly one boom barrier and exactly one RFID antenna pole; no second barrier, no duplicate
> antenna, no repeated reader box

Objects that appear in the previous shot must not silently appear or disappear in this one. In
motion prompts add: `no object on the desk appears, disappears or moves between shots`.

### 3. FLOW → liquids and mechanisms are usually cheaper to imply

Fluid simulation is where models fail most visibly (fuel spraying onto tarmac in three successive
renders). Either state the containment explicitly, or avoid showing the flow and prove it another
way — a close insert, an indicator LED, an instrument reading.

### 4. FACING → screens, lenses, vehicles

For every device with a front and a back, say where each side points, in relation to **the camera
and its user**:

> the phone lies flat on the paper, screen facing UP toward the man, rear lens facing DOWN toward
> the sheet

For vehicles: `driving away from the camera, rear of the trailer toward us`. "Truck at gate" is
where wrong-direction shots come from.

### 5. PAIR → what is identical, what must differ

Any location or object shown twice (departure/return, before/after, open/close) is a pair. Record
the pair in `scene-plan.md` and in both prompts:

| Axis | Rule |
|---|---|
| Hardware | IDENTICAL. Same sensor body, same gate, same post. Name the shared reference image in both prompts |
| Camera side / travel direction | MUST DIFFER, and the difference must be legible without text |
| Light | MUST DIFFER if the story says a day passed. State Kelvin and shadow direction in both |
| Framing | MAY differ. A second visit at a different shot size reads as a new moment, not an error |

A pair where only the overlay text differs is a defect: the viewer reads it as the same moment
repeated.

### 6. PEOPLE → two visible axes of separation

Two characters of the same gender and build in one frame read as one person seen twice, especially
when one has their back to camera. Separate them on **two** axes that survive a back view: headwear,
uniform colour, build, hair, seated vs standing. State both in the prompt.

When a face is not needed, frame it out. A shot specified as "hands only" or "partial face" cannot
drift off-model, which is why the tank and phone shots were reframed closer instead of re-rendered
again.

### 7. OVERLAY SURFACE → decide before the clip is rendered

Measure the intended surface in the keyframe, in pixels at delivery resolution, and check its angle:

| Surface | Decision |
|---|---|
| Frontal, ≥ 300px wide | Track the panel onto the screen (per-frame corners) |
| Oblique > 15°, or 120-300px | Track only if the corners are measurable; otherwise floating card |
| < 120px wide, or facing away from camera | **Floating card.** Never attempt to attach |

A tracked panel needs the four screen corners per frame, from edge lines fitted by least squares —
not from extreme x+y points, which jump tens of pixels on a tilted screen. A screen is rarely a
rectangle: measure all four corners, they will not agree.

If the surface is a phone or monitor the *character* is looking at, check whether it faces the
camera at all. A panel composited onto a screen that faces away from camera renders behind the
device.

## Flow Gate (Phase 2-3, before any prompt exists)

Three rules on the script, checked by `video-prompt-reviewer` C12.

1. **Close the loop.** Any claim that a system measures something must show: reading before →
   the event → reading after → the resulting number. A sensor that reads but never produces a
   figure is a dangling claim. In the production above, the fuel story only became an argument
   once it read 184 L on departure, 139 L on return, and stated the 45 L difference.
2. **What changed?** Every scene must answer, in one sentence, what is different from the scene
   before it. "Nothing" means the scene is decoration — cut it or merge it.
3. **Show the object.** If a character takes, carries, delivers or removes something, the thing is
   visible in frame. "Parts leave the store" with empty hands proves the opposite of the claim.

## Post-render frame audit (Phase 5, after each clip)

Sample three frames — around 1s, mid-clip, and 0.5s before the end — and read them:

- [ ] COUNT holds in all three frames (nothing duplicated mid-motion)
- [ ] FACING holds (nothing flipped)
- [ ] MECHANISM holds (the nozzle stays in the hole, the cap stays where it was)
- [ ] Nothing appeared, vanished or teleported between frames
- [ ] Light matches the time of day the overlay claims. Platform models drift toward midday in the
      second half of a clip rendered from an evening keyframe; fix in assembly with a colour grade
      rather than re-rendering
- [ ] Direction is still legible against the paired scene

A clip that fails COUNT, FACING or MECHANISM is re-rendered. A clip that only fails light is
graded in the assembly step — that is a filter, not a credit.

## Archive, never delete

Every rejected paid artefact goes to `_arsip/` with the reason in the filename
(`keyframe-DITOLAK-S19-hp-terbalik.png`). The reason is what makes the next prompt better; a
deleted reject teaches nothing and costs the same money twice.
