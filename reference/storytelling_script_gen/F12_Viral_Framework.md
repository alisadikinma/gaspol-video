# F12: Viral Framework (short-form)

**When used:** the target platform is a short-form feed (YouTube Shorts, Instagram Reels, TikTok). Skip it for long-form B2B films.

**What it is:** a 7-stage checklist for the structure of a short viral video. It is imitation of **structure**, never of **content**: no footage, voice, face, script, music or sound effect of any reference channel is copied.

**What it does not do:** F12 adds to the 9 Commandments, F5 (Hook Vault), F6 (CTA Vault) and F11. It never overrides them. When F12 and a Commandment disagree, the Commandment wins and the checklist item is answered `N/A: reason`.

## Source and how to read the tags

- **Source: the course notebook `Seefluencer AI Mentor` (id `114215f6`)**, queried with `notebooklm ask -n 114215f6` on 2026-10-16. Four questions: the 7 stages, the title formula, the loop ending, the analytics thresholds.
- `[DATA]` = stated by the course or its transcripts, quoted from the notebook answer.
- `[TAFSIRAN]` = our interpretation: how a stage becomes a testable checklist line.
- Every number below is `source: course`. It is advice from a course, not platform data. The audio study of 12 reference clips (`docs/evals/viral-audio-study.md`) measured no SFX or music rule, so **this framework states none**.

## The checklist block

A short-form `av-script.md` carries a `## Viral Checklist` block after `## Production Notes`: a table `| Stage | Item | Verdict |` with one row per item below. Verdict is `PASS`, `FAIL: reason`, `N/A: reason` or `PENDING: reason`.

- `PENDING` is legal only for stages 6 and 7 (they happen after publishing). Stages 1-5 must be decided before the script is approved.
- `N/A` and `PENDING` always need a reason.
- Check it: `python3 tools/viral_checklist.py check <av-script.md>`. Exit 0 = every item decided and none FAIL. Exit 1 = a problem, listed one per line. Exit 2 = the file cannot be read.
- A `FAIL:` is a finding for the owner to rule on, not an automatic stop: fix it, or keep it and say why in Production Notes.

## Stage 1: Topic research

`[DATA]` "Sweet Spot" = the overlap of Interest, Expertise and Market Demand. "Specific Niche": narrow a broad niche ("Business" to "Digital Marketing untuk Pemilik Usaha Kuliner"). "7 Faktor Viralitas": Pro/Kontra, Relatability, Celebrity Association, Trending Topics, Emotion, Shock Value, Comedy. ATM = Amati, Tiru, Modifikasi (watch, copy the pattern, modify).

| Item id | Pass when | Fail when |
|---|---|---|
| `specific-niche` | The topic names a specific audience and subject, not a broad category | The topic is "business" or "health" with no narrowing |
| `viral-factor` | At least one of the 7 viral factors is named and visible in the script | No factor can be pointed to |
| `market-demand` | The script or brief states why people want this (a validated similar video, search interest, a real event) | The only reason is that the maker likes the topic |

`[TAFSIRAN]` ATM is a method of pattern study, which is exactly the "structure not content" line above.

## Stage 2: Hook (first 3 seconds) and title

`[DATA]` "The 3-Second Rule": most viewers decide in the first 3 seconds. "Clickbait but Honest": as sensational as possible, and the video must then keep the promise. Multi-Sensory Hook = a bold statement (audio) + large text in the safe zone (visual) + curiosity or urgency (psychology). Named failures: the "Hi guys, hari ini aku mau..." opening, deceptive clickbait, a static frame in the first 3 seconds. Hook types: Negative, Proof, Promise, Audience Pain Point, Transformation (these map onto F5; use F5 for the wording).

| Item id | Pass when | Fail when |
|---|---|---|
| `no-greeting` | The first words are not a greeting or a "today I will..." warm-up | The script opens with "Hi guys" or the company name (also breaks Commandment 1) |
| `visual-hook` | Something moves or changes on screen in seconds 0-1 | The first shot is a still or a logo |
| `honest-promise` | The body delivers what the hook promised | The hook claims something the video never shows |
| `title-formula` | The title carries emotion + a public figure + a large or specific amount, or the row says why the topic has no such figure | The title is generic and has none of the three |
| `person-claim-verified` | Any real person named in the title or hook is tied only to claims that have a checkable source, worded as sourced ("kata PLN", "diduga") | A real person is named with a claim nobody has verified |

### Title formula

`[DATA]` Asked for the title formula, the notebook gave: viral title = emotion or sensation + public figure (Celebrity Association) + specific or extreme amount. Examples quoted by the course: "Seberapa kaya Ronaldo?", "Aku nginap di rumah 70 miliar punya Dr Richard!", "Begini caraku hasilkan 1 miliar rupiah dari 0 rupiah". Course wording: "Menggunakan nama artis atau orang terkenal lainnya bisa meningkatkan viralitas. Contohnya, konten 'Seberapa kaya' Samuel Christ." and "Kamu wajib bikin hook yang se-clickbait mungkin, tapi isinya juga tetep wajib memenuhi ekspektasi hook tersebut. Tidak berbohong."

`[TAFSIRAN]` The three ingredients are the same in every answer. The notebook's wording of the formula differed between questions (once it described the hook formula instead), so treat the order of the three as loose.

**Guard (ours, not the course's):** a title that names a real person must not assert a claim about that person that nobody has verified. A famous name borrows credibility; it must not borrow a falsehood. Use a sourced claim or drop the name. This is why `person-claim-verified` is its own item. It applies the course's own "Clickbait but Honest" rule to named people.

## Stage 3: Script

`[DATA]` "Killer Script": Hook, Foreshadow, Body, Ending. Foreshadow = the bridge right after the hook that makes the viewer curious about the end (course timing in one answer: seconds 3-5). Body = "Singkat, Padat, Jelas", Problem-Solution or 3-5 points, no "tele-tele" (fluff). "The Chat" tone: talk like to a friend at a coffee shop, not like a news reader; include personal experience.

| Item id | Pass when | Fail when |
|---|---|---|
| `killer-structure` | Hook, Foreshadow, Body and Ending are all present in order | A part is missing |
| `foreshadow` | A foreshadow beat starts in the 3-5 s window (a retention gate default is 3-6 s) and its promise is answered later | No foreshadow, or it starts after 6 s |
| `tight-body` | Every body row adds value; no filler rows | Rows that repeat or wander from the hook |
| `chat-tone` | Conversational, "aku/kamu" voice | Reads like an announcement |
| `loop-ending` | See below | The last line closes with a generic sign-off |

### Loop ending

`[DATA]` Course: "The Loop: Seamlessly connecting the last sentence back to the first sentence of the Hook to encourage re-watching." and "Awal video dan ending video nyambung banget dengan smooth." Example from the course notebook: the video ends on "...Dan itulah..." and the first line is "...seberapa kaya Ronaldo?", so the replay reads "Dan itulah seberapa kaya Ronaldo?". A second example: the last line "It finally shattered, but look at the pattern!" loops back to "Can you break an unbreakable glass?".

`[TAFSIRAN]` The rule is: the last line returns to the hook's open question so the replay reads as one sentence. "Dan itulah..." is an example, not a mandatory phrase. The loop must not trick the viewer into a false claim; an honest CTA ending is allowed instead, but then `loop-ending` is `FAIL` or `N/A: reason`, never silently `PASS`.

## Stage 4: Edit

`[DATA]` "Every Second Matters". Change frame, angle or digital zoom every 1-3 seconds. B-roll must match the spoken word (prefer self-shot). Captions: Montserrat Bold, size 15-18, shadow, word by word, centre safe zone, not under platform buttons. Audio clean, music matches the mood, SFX only to emphasise motion. Failures: dead air, a shot still for more than 3 seconds, long static paragraphs, music covering the voice.

| Item id | Pass when | Fail when |
|---|---|---|
| `cut-every-1-3s` | A cut, angle or zoom change at least every 3 seconds is planned | Rows or shots run past 3 s with no change planned |
| `contextual-broll` | Each visual shows what the line says | B-roll that only decorates |
| `captions-safe-zone` | Captions are keywords, in the safe zone, and within the 50% overlay limit (doc 19) | Text under the platform buttons or wall-to-wall subtitles |
| `audio-clean` | Voice is clear and music sits under it (retention gate R5) | Music covers the voice |

`[TAFSIRAN]` Editing is measured on the finished cut by `tools/retention_gate.py` (Phase 6). At script time answer from the plan, or `N/A: reason` when the plan cannot show it. Doc 19 keeps the keyword-not-subtitle rule; the course's "word by word" is read as keyword overlays, not full subtitles.

## Stage 5: Caption and hashtags

`[DATA]` Three caption types: Question (a pro/contra prompt), Hook (one honest clickbait sentence), Storytelling (hook, body, CTA, hashtags). Hashtags: 3-5 in a 3-tier formula, 1-2 macro (100K-1M uses), 1-2 micro (10K-100K), 1 unique (own brand). Failure: tens of random hashtags, an empty caption.

| Item id | Pass when | Fail when |
|---|---|---|
| `caption-type` | A post caption is drafted and is one of the three types | No caption drafted |
| `hashtag-3-tier` | 3-5 hashtags following the 3-tier split | None, or a pile of random ones |
| `invites-interaction` | The caption or CTA asks something that invites a comment | Flat description only |

## Stage 6: Posting

`[DATA]` "Omnipresence": post the same vertical file to TikTok, Instagram Reels and YouTube Shorts at once. Upload hour is a myth for a new account; retention decides. A custom cover matters most for YouTube Shorts. Avoid music that gets muted by licence.

| Item id | Pass when | Fail when |
|---|---|---|
| `omnipresence` | The platform line lists all three feeds | One platform only |
| `custom-cover` | A cover frame is planned (Phase 7 packaging) | Not planned for Shorts |
| `music-licence` | Music is licensed or generated, not a copied track | A copied track |

`PENDING: reason` is allowed here until the video is published.

## Stage 7: Analytics

`[DATA]` "Analytics ideal untuk TikTok: Watched full video minimal 20%, Average watch time minimal 50%." Winning Content Cycle: Experiment, Identify, Replicate, Improve. An outlier at 100K+ views is the "Winning Content"; replicate its format. Course wording: "Lakukan eksperimen ini sampai ada salah satu konsep yang berhasil mencapai lebih dari 100K+ views!... Replikasi winning content kamu."

| Threshold | Value | Tag |
|---|---|---|
| Watched full video | at least 20% | `source: course` |
| Average watch time | at least 50% of the video length | `source: course` |
| Replicate a winner | views above 100000 | `source: course` |

`[TAFSIRAN]` The course writes ">20%", ">50%" and "100K+"; the spec and `tools/viral_checklist.py` use `>=` for the two percentages and `>` for views. The two percentages are TikTok benchmarks in the course; applying them to YouTube or Reels is our extension.

| Item id | Pass when | Fail when |
|---|---|---|
| `benchmarks` | `viral_checklist.py rate` says pass for watched-full and average watch | Either is below its threshold |
| `outlier-identified` | One video clearly beats the account average | None yet (stay `PENDING`) |
| `replicate-winner` | The winner's format is reused for the next video | The format is dropped after a win |

Verdict from published numbers: `python3 tools/viral_checklist.py rate <project>/packaging/calibration.json`. It reads the keys `tools/yt_stats.py` writes (`avgViewPct`, `views`). `yt_stats.py` does **not** write a watched-full figure (YouTube Studio only), so the verdict reads `unknown` for it until `watchedFullPct` is added by hand. A missing figure is `unknown` and the output names the key; it is never guessed.

## Where the notebook was thin

- **Statistic for the 3-second rule differs between answers** (71% decide in 3 s in one, 65% of those who pass watch 10 s or more in another). F12 states no percentage for it.
- **Foreshadow timing**: one answer says seconds 3-5; the spec and the retention gate use 3-6 s. F12 uses 3-5 as the item text and notes the gate default.
- **Title formula**: the three answers agree on the three ingredients but not on the wording, and one answer described the hook formula instead of a title formula. Asked once more, the examples were all titles that fit the three ingredients.
- **Analytics thresholds are TikTok-only** in the course. No YouTube or Reels figure was given.
- **Posting and caption stages**: the course gives rules of thumb (3-5 hashtags, three caption types, post to three feeds) without measured evidence.
- Nothing about SFX or music was asked or found; the audio study measured none.

## Worked example

Real script: `Dampak-AI-DataCenter/output/av-script.md` (Reels and TikTok, 92 s, 9:16, Bahasa Indonesia). A copy was filled and checked; the project was not edited. The checklist is filled honestly, with FAIL where the script fails.

| Stage | Item | Verdict |
|---|---|---|
| topic research | `specific-niche` | PASS |
| topic research | `viral-factor` | PASS |
| topic research | `market-demand` | FAIL: no market-demand evidence is written in av-script.md |
| hook | `no-greeting` | PASS |
| hook | `visual-hook` | PASS |
| hook | `honest-promise` | PASS |
| hook | `title-formula` | FAIL: title 'Batam Gelap' has an emotion but no public figure and no large amount |
| hook | `person-claim-verified` | PASS |
| script | `killer-structure` | PASS |
| script | `foreshadow` | FAIL: starts at 0:06, course window is 3-5 s (hook fixed at 6 s by owner on 2026-10-13) |
| script | `tight-body` | PASS |
| script | `chat-tone` | FAIL: body is serious-news tone by brief (video_tone serious); course wants casual chat |
| script | `loop-ending` | FAIL: ends on a CTA to the comments, last line does not return to the hook question |
| edit | `cut-every-1-3s` | FAIL: script rows run 4-12 s (1:00-1:12 is 12 s); motion cuts are not planned at script level |
| edit | `contextual-broll` | PASS |
| edit | `captions-safe-zone` | N/A: caption placement is decided in Phase 6, not in the script |
| edit | `audio-clean` | N/A: BGM headroom is measured in Phase 6 (retention gate R5) |
| caption | `caption-type` | FAIL: no post caption is drafted in av-script.md |
| caption | `hashtag-3-tier` | FAIL: no hashtags drafted |
| caption | `invites-interaction` | PASS |
| posting | `omnipresence` | FAIL: platform line lists Reels and TikTok only, YouTube Shorts is not planned |
| posting | `custom-cover` | PENDING: cover is made in Phase 7 packaging |
| posting | `music-licence` | PENDING: music is generated in Phase 6 |
| analytics | `benchmarks` | PENDING: not published yet |
| analytics | `outlier-identified` | PENDING: not published yet |
| analytics | `replicate-winner` | PENDING: not published yet |

Output of `python3 tools/viral_checklist.py check`, **exit code 1** (9 FAIL cells, which is the honest result for an issue-explainer script that was approved before this framework existed):

```
FAIL topic research/market-demand: no market-demand evidence is written in av-script.md
FAIL hook/title-formula: title 'Batam Gelap' has an emotion but no public figure and no large amount
FAIL script/foreshadow: starts at 0:06, course window is 3-5 s (hook fixed at 6 s by owner on 2026-10-13)
FAIL script/chat-tone: body is serious-news tone by brief (video_tone serious); course wants casual chat
FAIL script/loop-ending: ends on a CTA to the comments, last line does not return to the hook question
FAIL edit/cut-every-1-3s: script rows run 4-12 s (1:00-1:12 is 12 s); motion cuts are not planned at script level
FAIL caption/caption-type: no post caption is drafted in av-script.md
FAIL caption/hashtag-3-tier: no hashtags drafted
FAIL posting/omnipresence: platform line lists Reels and TikTok only, YouTube Shorts is not planned
viral_checklist: 9 problem(s) in <scratch>/dampak/av-script.md
```

`[TAFSIRAN]` The `chat-tone` FAIL is a real conflict, not a defect: that script is a serious explainer by the owner's brief (`video_tone: serious`), and F12 does not override the tone chosen in Phase 1. The owner can keep it and note the reason in Production Notes.
