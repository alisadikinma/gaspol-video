# Eval — Render Path routing (Phase 3)

**What it tests:** whether Phase 3 assigns `Render Path` correctly per scene. This is LLM behaviour,
so a unit test cannot verify it; these fixtures are the success contract.

**Rule under test:** `reference/script-to-scene-bridge.md` > "Render Path".

**Success threshold:** capability set 5/5 correct. Regression set 4/4 correct. A wrong label on the
mixed case (fixture 5) is the expensive failure — it either wastes NB2 credits or drops a human
performance — so it counts double when judging a change to the rule.

**How to run:** give a fresh session the scene description alone, plus the assignment rule, and ask
for the `Render Path` value with one sentence of reasoning. No other context.

---

## Capability set

| # | Scene description (input) | Expected | Why |
|---|---|---|---|
| 1 | "Full-screen: gate waiting time drops from 42 minutes to 6 minutes, two big numbers side by side, arrow between them" | `explainer` | The whole scene IS the numbers. No platform renders those legibly. |
| 2 | "Operator in a hi-vis vest walks along the conveyor, checks a shell batch, wipes his forehead" | `live-action` | Human performance, no readable information on screen. |
| 3 | "Screen recording style walkthrough of the ANPR dashboard: plate number appears, status changes to CLEARED, timestamp updates" | `explainer` | UI text must be readable, and the text changing IS the point. |
| 4 | "Wide drone shot of the port yard at dawn, trucks queueing at the gate, mist over the containers" | `live-action` | Atmosphere and place. Nothing to read. |
| 5 | "Presenter stands beside a screen showing the three-step process and points at step two while explaining it" | `live-action + overlay:<shot-id>` | Needs a real performance AND readable steps. The performance drives the scene; the diagram is composited on top in Phase 6. |

## Regression set

Cases that were labelled wrong at least once during design, or that sit closest to the boundary.

| # | Scene description (input) | Expected | The trap |
|---|---|---|---|
| R1 | "Close-up of the product box, logo facing camera, slow rotation" | `live-action` | A logo is text-shaped, which invites `explainer`. But the logo is a real object being filmed, not information to read, and Phase 3.5 already requires a user-supplied logo reference. |
| R2 | "Timeline of the rollout: 2024, 2025, 2026, with one milestone label under each year" | `explainer` | Looks like B-Roll of a calendar; it is a labelled diagram. |
| R3 | "Supervisor points at a wall-mounted safety sign while briefing two workers" | `live-action` | There is text on screen, but nobody has to read it. Legibility is not the scene's job. |
| R4 | "Split screen: before on the left, after on the right, both are photographs of the same gate" | `live-action` | Comparison is a diagram word, but the content is two photographs. Only the layout is graphic, and layout is an edit decision in Phase 6, not a Remotion shot. |

---

## Scoring notes

- Judge the LABEL, not the wording of the reasoning.
- `live-action + overlay:<shot-id>` and `live-action` are DIFFERENT answers. Fixture 5 is only correct
  with the overlay part; a bare `live-action` there loses the diagram entirely.
- If a fixture starts failing after a rule edit, the rule changed meaning — fix the rule or record why
  the new answer is better. Never edit the fixture to match the new output.
