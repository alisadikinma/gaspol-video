import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import registry_build

ROOT = Path(__file__).resolve().parent.parent.parent


def entry(**over):
    base = {
        "id": "tools/composite.py",
        "purpose": "Insert, overlay or split a shot into a finished master.",
        "tasks": ["composite", "overlay"],
        "phase": "6",
        "replaces": [],
        "distinct_because": "",
        "internal_reason": "",
    }
    base.update(over)
    return base


def registry(*tools, **over):
    reg = {"version": 1, "tools": list(tools), "routes": [], "ffprobe_allow": []}
    reg.update(over)
    return reg


class FakeRoot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for rel in (
            "tools/composite.py",
            "tools/gen_vo.mjs",
            "tools/_venv.py",
            "tools/__init__.py",
            "tools/vidkit/__init__.py",
            "tools/vidkit/__main__.py",
            "tools/vidkit/ff.py",
            "tools/vidkit/js/env.mjs",
        ):
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x = 1\n")

    def tearDown(self):
        self._tmp.cleanup()

    def problems(self, reg):
        return registry_build.validate(reg, self.root)

    def assertProblem(self, reg, text):
        probs = self.problems(reg)
        self.assertTrue(any(text in p for p in probs), f"{text!r} not found in {probs}")


class ValidateTest(FakeRoot):
    def test_unknown_id_on_disk_rejected(self):
        self.assertProblem(
            registry(entry(id="tools/nope.py")), "tools/nope.py: file does not exist"
        )

    def test_valid_entry_passes(self):
        self.assertEqual(self.problems(registry(entry())), [])

    def test_empty_tools_passes(self):
        self.assertEqual(self.problems(registry()), [])

    def test_wrong_version(self):
        self.assertProblem(registry(version=2), "registry: version must be 1")

    def test_duplicate_id(self):
        self.assertProblem(
            registry(entry(), entry(tasks=["other"])), "tools/composite.py: duplicate id"
        )

    def test_replaces_unknown_id(self):
        self.assertProblem(
            registry(entry(replaces=["tools/ghost.py"])),
            "tools/composite.py: replaces unknown id tools/ghost.py",
        )

    def test_replaces_known_id_ok(self):
        reg = registry(
            entry(replaces=["tools/gen_vo.mjs"]),
            entry(id="tools/gen_vo.mjs", tasks=["voice"]),
        )
        self.assertEqual(self.problems(reg), [])

    def test_purpose_too_long(self):
        self.assertProblem(
            registry(entry(purpose="x" * 141)), "tools/composite.py: purpose longer than 140"
        )

    def test_purpose_with_newline(self):
        self.assertProblem(
            registry(entry(purpose="one\ntwo")), "tools/composite.py: purpose has a newline"
        )

    def test_purpose_empty(self):
        self.assertProblem(registry(entry(purpose="")), "tools/composite.py: purpose is empty")

    def test_tasks_uppercase_or_space(self):
        self.assertProblem(registry(entry(tasks=["Bad"])), "tools/composite.py: bad task token 'Bad'")
        self.assertProblem(
            registry(entry(tasks=["has space"])), "tools/composite.py: bad task token 'has space'"
        )

    def test_tasks_duplicate_token(self):
        self.assertProblem(
            registry(entry(tasks=["a", "a"])), "tools/composite.py: duplicate task 'a'"
        )

    def test_tasks_count_bounds(self):
        self.assertProblem(registry(entry(tasks=[])), "tools/composite.py: tasks must hold 1-6")
        self.assertProblem(
            registry(entry(tasks=list("abcdefg"))), "tools/composite.py: tasks must hold 1-6"
        )

    def test_phase_outside_set(self):
        self.assertProblem(registry(entry(phase="8")), "tools/composite.py: bad phase '8'")
        self.assertProblem(registry(entry(phase=6)), "tools/composite.py: bad phase 6")

    def test_phase_shared_ok(self):
        self.assertEqual(self.problems(registry(entry(phase="shared"))), [])

    def test_wrong_field_types(self):
        self.assertProblem(registry(entry(tasks="composite")), "tools/composite.py: tasks must be a list")
        self.assertProblem(registry(entry(replaces="x")), "tools/composite.py: replaces must be a list")
        self.assertProblem(
            registry(entry(distinct_because=3)), "tools/composite.py: distinct_because must be a string"
        )
        self.assertProblem(
            registry(entry(internal_reason=None)), "tools/composite.py: internal_reason must be a string"
        )

    def test_entry_not_object(self):
        self.assertProblem(registry("nope"), "tool #1: entry must be an object")

    def test_route_cell_with_pipe(self):
        reg = registry(routes=[{"task": "a | b", "use": "`x`", "tools": []}])
        self.assertProblem(reg, "route #1: task has a pipe or newline")
        reg = registry(routes=[{"task": "a", "use": "`x`\ny", "tools": []}])
        self.assertProblem(reg, "route #1: use has a pipe or newline")

    def test_route_empty_cell(self):
        reg = registry(routes=[{"task": "", "use": "`x`", "tools": []}])
        self.assertProblem(reg, "route #1: task is empty")

    def test_route_unknown_tool(self):
        reg = registry(routes=[{"task": "a", "use": "`x`", "tools": ["tools/ghost.py"]}])
        self.assertProblem(reg, "route #1: unknown tool tools/ghost.py")

    def test_route_empty_tools_allowed(self):
        reg = registry(routes=[{"task": "a", "use": "`x`", "tools": []}])
        self.assertEqual(self.problems(reg), [])

    def test_ffprobe_allow_stale_entry(self):
        reg = registry(ffprobe_allow=[{"id": "tools/composite.py", "reason": "r"}])
        self.assertProblem(reg, "tools/composite.py: stale ffprobe_allow entry (no ffprobe in file)")

    def test_ffprobe_allow_live_entry(self):
        (self.root / "tools/composite.py").write_text('run(["ffprobe", "-v"])\n')
        reg = registry(ffprobe_allow=[{"id": "tools/composite.py", "reason": "r"}])
        self.assertEqual(self.problems(reg), [])

    def test_ffprobe_allow_missing_file_and_reason(self):
        reg = registry(ffprobe_allow=[{"id": "tools/ghost.py", "reason": ""}])
        probs = self.problems(reg)
        self.assertTrue(any("tools/ghost.py: file does not exist" in p for p in probs))
        self.assertTrue(any("tools/ghost.py: ffprobe_allow reason is empty" in p for p in probs))

    def test_duplicate_pair_fails(self):
        reg = registry(
            entry(),
            entry(id="tools/gen_vo.mjs"),
        )
        self.assertProblem(reg, "tools/gen_vo.mjs: duplicate of tools/composite.py")

    def test_duplicate_pair_excused_by_replaces(self):
        reg = registry(entry(replaces=["tools/gen_vo.mjs"]), entry(id="tools/gen_vo.mjs"))
        self.assertEqual(self.problems(reg), [])

    def test_duplicate_pair_excused_by_both_distinct(self):
        reg = registry(
            entry(distinct_because="a"),
            entry(id="tools/gen_vo.mjs", distinct_because="b"),
        )
        self.assertEqual(self.problems(reg), [])

    def test_same_tasks_different_phase_not_duplicate(self):
        reg = registry(entry(), entry(id="tools/gen_vo.mjs", phase="7"))
        self.assertEqual(self.problems(reg), [])

    def test_does_not_mutate_input(self):
        reg = registry(entry(id="tools/nope.py"))
        before = copy.deepcopy(reg)
        self.problems(reg)
        self.assertEqual(reg, before)


class CoverageTest(FakeRoot):
    def test_uncovered_tool_reported(self):
        probs = registry_build.validate(registry(), self.root, coverage=True)
        self.assertIn("tools/composite.py: not in registry", probs)

    def test_coverage_off_by_default(self):
        self.assertEqual(self.problems(registry()), [])

    def test_covered_tool_not_reported(self):
        probs = registry_build.validate(registry(entry()), self.root, coverage=True)
        self.assertNotIn("tools/composite.py: not in registry", probs)

    def test_needs_route_or_internal_reason(self):
        probs = registry_build.validate(registry(entry()), self.root, coverage=True)
        self.assertIn("tools/composite.py: no route and no internal_reason", probs)
        reg = registry(entry(internal_reason="imported helper"))
        probs = registry_build.validate(reg, self.root, coverage=True)
        self.assertNotIn("tools/composite.py: no route and no internal_reason", probs)
        reg = registry(
            entry(), routes=[{"task": "a", "use": "`x`", "tools": ["tools/composite.py"]}]
        )
        probs = registry_build.validate(reg, self.root, coverage=True)
        self.assertNotIn("tools/composite.py: no route and no internal_reason", probs)


class DiscoverTest(FakeRoot):
    def test_discover_sorted_and_excludes_infrastructure(self):
        self.assertEqual(
            registry_build.discover(self.root),
            [
                "tools/composite.py",
                "tools/gen_vo.mjs",
                "tools/vidkit/ff.py",
                "tools/vidkit/js/env.mjs",
            ],
        )

    def test_discover_real_repo_finds_known_tools(self):
        found = registry_build.discover(ROOT)
        self.assertIn("tools/registry_build.py", found)
        self.assertIn("tools/vidkit/ff.py", found)
        self.assertNotIn("tools/_venv.py", found)
        self.assertNotIn("tools/vidkit/__main__.py", found)


class LoadTest(FakeRoot):
    def test_missing_file(self):
        with self.assertRaises(registry_build.RegistryError) as cm:
            registry_build.load(self.root / "tools/registry.json")
        self.assertIn("registry.json", str(cm.exception))

    def test_invalid_json_names_parse_error(self):
        p = self.root / "tools/registry.json"
        p.write_text("{not json")
        with self.assertRaises(registry_build.RegistryError) as cm:
            registry_build.load(p)
        self.assertIn("not valid JSON", str(cm.exception))

    def test_non_object_json(self):
        p = self.root / "tools/registry.json"
        p.write_text("[]")
        with self.assertRaises(registry_build.RegistryError):
            registry_build.load(p)

    def test_roundtrip(self):
        p = self.root / "tools/registry.json"
        p.write_text(json.dumps(registry(entry())))
        self.assertEqual(registry_build.load(p), registry(entry()))


def cli(*argv, root=None):
    out, err = io.StringIO(), io.StringIO()
    args = list(argv)
    if root is not None:
        args = ["--root", str(root)] + args
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = registry_build.main(args)
        except SystemExit as e:
            rc = e.code
    return rc, out.getvalue(), err.getvalue()


class CliTest(FakeRoot):
    def write(self, reg):
        (self.root / "tools/registry.json").write_text(json.dumps(reg))

    def test_validate_ok(self):
        self.write(registry(entry()))
        rc, out, _ = cli("validate", root=self.root)
        self.assertEqual(rc, 0)
        self.assertIn("registry: ok", out)

    def test_validate_lists_problems_and_count(self):
        self.write(registry(entry(id="tools/nope.py"), entry(phase="9", tasks=["z"])))
        rc, out, _ = cli("validate", root=self.root)
        self.assertEqual(rc, 1)
        self.assertIn("tools/nope.py: file does not exist", out)
        self.assertIn("registry: 2 problem(s)", out)

    def test_validate_missing_registry_exit_2_names_path(self):
        rc, _, err = cli("validate", root=self.root)
        self.assertEqual(rc, 2)
        self.assertIn("registry.json", err)

    def test_validate_bad_json_exit_2(self):
        (self.root / "tools/registry.json").write_text("{oops")
        rc, _, err = cli("validate", root=self.root)
        self.assertEqual(rc, 2)
        self.assertIn("not valid JSON", err)

    def test_validate_coverage_flag(self):
        self.write(registry())
        rc, out, _ = cli("validate", "--coverage", root=self.root)
        self.assertEqual(rc, 1)
        self.assertIn("tools/composite.py: not in registry", out)

    def test_committed_registry_skeleton_is_valid(self):
        rc, out, _ = cli("validate", root=ROOT)
        self.assertEqual(rc, 0, out)


BEGIN = "<!-- registry:routes:begin -->"
END = "<!-- registry:routes:end -->"


def route(task, use, tools=()):
    return {"task": task, "use": use, "tools": list(tools)}


class RenderTest(FakeRoot):
    def write(self, reg):
        (self.root / "tools/registry.json").write_text(json.dumps(reg))

    def setUp(self):
        super().setUp()
        self.doc = self.root / "docs/tool-routing.md"
        self.doc.parent.mkdir(parents=True, exist_ok=True)
        self.reg = registry(
            routes=[route("Join clips", "`vidkit concat`"), route("Mix", "`mix.py`")]
        )
        self.write(self.reg)
        self.block = (
            "| I want to... | Use |\n|---|---|\n"
            "| Join clips | `vidkit concat` |\n| Mix | `mix.py` |\n"
        )

    def put(self, inner, before="intro\n\n", after="\n## Tail\ntext\n"):
        self.doc.write_text(before + BEGIN + "\n" + inner + END + "\n" + after)

    def test_render_check_reports_drift(self):
        self.put(self.block.replace("`mix.py`", "`other.py`"))
        rc, out, _ = cli("render", "--check", root=self.root)
        self.assertEqual(rc, 1)
        self.assertIn("drift", out)

    def test_render_check_ok_and_writes_nothing(self):
        self.put(self.block)
        before = self.doc.read_bytes()
        rc, _, _ = cli("render", "--check", root=self.root)
        self.assertEqual(rc, 0)
        self.assertEqual(self.doc.read_bytes(), before)

    def test_render_check_drift_writes_nothing(self):
        self.put("stale\n")
        before = self.doc.read_bytes()
        cli("render", "--check", root=self.root)
        self.assertEqual(self.doc.read_bytes(), before)

    def test_render_writes_block_and_keeps_outside_bytes(self):
        self.put("stale\n")
        rc, out, _ = cli("render", root=self.root)
        self.assertEqual(rc, 0)
        self.assertIn("routing table: 2 routes written", out)
        self.assertEqual(
            self.doc.read_text(),
            "intro\n\n" + BEGIN + "\n" + self.block + END + "\n\n## Tail\ntext\n",
        )

    def test_render_idempotent(self):
        self.put("stale\n")
        cli("render", root=self.root)
        first = self.doc.read_bytes()
        rc, out, _ = cli("render", root=self.root)
        self.assertEqual(rc, 0)
        self.assertIn("routing table: unchanged", out)
        self.assertEqual(self.doc.read_bytes(), first)

    def test_render_missing_markers_exit_2(self):
        self.doc.write_text("no markers here\n")
        rc, _, err = cli("render", root=self.root)
        self.assertEqual(rc, 2)
        self.assertIn("marker", err)
        rc, _, _ = cli("render", "--check", root=self.root)
        self.assertEqual(rc, 2)

    def test_render_reversed_markers_exit_2(self):
        self.doc.write_text(END + "\nx\n" + BEGIN + "\n")
        rc, _, err = cli("render", root=self.root)
        self.assertEqual(rc, 2)
        self.assertIn("marker", err)

    def test_render_missing_doc_exit_2(self):
        rc, _, err = cli("render", root=self.root)
        self.assertEqual(rc, 2)
        self.assertIn("tool-routing.md", err)

    def test_render_refuses_invalid_route(self):
        self.write(registry(routes=[route("a | b", "`x`")]))
        self.put("stale\n")
        before = self.doc.read_bytes()
        rc, _, _ = cli("render", root=self.root)
        self.assertEqual(rc, 1)
        self.assertEqual(self.doc.read_bytes(), before)

    def test_route_with_pipe_is_validate_problem(self):
        self.assertProblem(registry(routes=[route("a | b", "`x`")]), "pipe")

    def test_escaped_pipe_is_allowed(self):
        self.assertEqual(self.problems(registry(routes=[route("t", "`a b\\|c` x")])), [])
        self.assertEqual(self.problems(registry(routes=[route("a\\|b", "`x`")])), [])
        self.assertEqual(self.problems(registry(routes=[route("\\|a", "`x\\|y\\|z`")])), [])

    def test_bare_pipe_inside_code_span_rejected(self):
        self.assertProblem(registry(routes=[route("t", "`a|b`")]), "route #1: use has a pipe or newline")
        self.assertProblem(registry(routes=[route("a|b", "`x`")]), "route #1: task has a pipe or newline")

    def test_escaped_pipe_next_to_bare_pipe_rejected(self):
        self.assertProblem(registry(routes=[route("t", "`a\\||b`")]), "pipe")
        self.assertProblem(registry(routes=[route("t", "`a|\\|b`")]), "pipe")

    def test_escaped_backslash_before_pipe_rejected(self):
        # `\\|` in a GFM cell is a literal backslash followed by a bare pipe.
        self.assertProblem(registry(routes=[route("t", "`a\\\\|b`")]), "pipe")
        self.assertEqual(self.problems(registry(routes=[route("t", "`a\\\\\\|b`")])), [])

    def test_empty_route_cell_still_reported_empty(self):
        self.assertProblem(registry(routes=[route("", "`x`")]), "task is empty")

    def test_pipe_outside_code_span_of_use_rejected(self):
        self.assertProblem(registry(routes=[route("t", "a | b")]), "pipe")

    def test_committed_doc_matches_committed_registry(self):
        rc, out, _ = cli("render", "--check", root=ROOT)
        self.assertEqual(rc, 0, out)

    def test_committed_registry_route_count_and_validates(self):
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        self.assertEqual(len(reg["routes"]), 71)
        self.assertEqual(registry_build.validate(reg, ROOT), [])
        deck = [r for r in reg["routes"] if r["task"].startswith("Deck / slide")]
        self.assertEqual(deck[0]["tools"], [])


class CommittedCoverageTest(unittest.TestCase):
    def test_coverage_reports_composite_until_registered(self):
        rc, out, _ = cli("validate", "--coverage", root=ROOT)
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        ids = {t["id"] for t in reg["tools"]}
        self.assertIn("tools/composite.py", ids, out)
        self.assertNotIn("tools/composite.py: not in registry", out)

    def test_first_half_tools_are_registered_and_routed(self):
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        by_id = {t["id"]: t for t in reg["tools"]}
        routed = {tid for r in reg["routes"] for tid in r["tools"]}
        for name in ("asset_home", "asset_library", "burn_subs", "caption_keywords",
                     "check_overlay_strings", "check_vo_duration", "clean_voice",
                     "composite", "composite_logo", "cost_log", "edit_render",
                     "gen_app_screen", "gen_captions", "gen_music", "gen_sfx", "gen_subs"):
            self.assertIn(f"tools/{name}.py", by_id)
        self.assertIn("tools/gen_vo.mjs", by_id)
        for tid, t in by_id.items():
            self.assertTrue(tid in routed or t["internal_reason"], tid)


class CommittedFullToolsCoverageTest(unittest.TestCase):
    def test_every_tool_directly_under_tools_is_registered_and_routed(self):
        rc, out, _ = cli("validate", "--coverage", root=ROOT)
        direct = [
            i for i in registry_build.discover(ROOT) if i.count("/") == 1
        ]
        lines = out.splitlines()
        for tid in direct:
            self.assertNotIn(f"{tid}: not in registry", lines)
            self.assertNotIn(f"{tid}: no route and no internal_reason", lines)
        leftovers = [ln for ln in lines if ln.startswith("tools/") and not ln.startswith("tools/vidkit/")]
        self.assertEqual(leftovers, [])

    def test_probe_clips_is_excused_from_vidkit_probe(self):
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        by_id = {t["id"]: t for t in reg["tools"]}
        self.assertEqual(
            by_id["tools/probe_clips.py"]["distinct_because"],
            "writes work/clip-manifest.json for a project (inventory + audio presence); "
            "vidkit probe prints one file's facts",
        )
        self.assertEqual(
            by_id["tools/probe_clips.py"]["tasks"], ["clip-manifest", "inventory", "durations"]
        )


class CommittedVidkitCoverageTest(unittest.TestCase):
    def test_committed_registry_fully_covers_repo(self):
        rc, out, _ = cli("validate", "--coverage", root=ROOT)
        self.assertEqual(rc, 0, out)
        self.assertEqual([ln for ln in out.splitlines() if "not in registry" in ln], [])

    def test_ffprobe_allow_is_the_six_that_need_raw_fields(self):
        # GV-22: everything else probes through vidkit/ff.py or vidkit/js/ff.mjs.
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        self.assertEqual(sorted(a["id"] for a in reg["ffprobe_allow"]), [
            "tools/face_box.py", "tools/person_mask.py", "tools/probe_clips.py", "tools/registry_build.py",
            "tools/retention_gate.py", "tools/vidkit/color.py"])

    def test_every_route_tool_id_exists(self):
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        ids = {t["id"] for t in reg["tools"]}
        for r in reg["routes"]:
            for tid in r["tools"]:
                self.assertIn(tid, ids, r["task"])

    def test_vidkit_modules_and_js_helpers_registered(self):
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        ids = {t["id"] for t in reg["tools"]}
        for name in ("audiostudy beats bond color colormatch cover encoder ff gates ingest "
                     "join karaoke loudness mixdown patch sheet speech stages synth track "
                     "unwhite").split():
            self.assertIn(f"tools/vidkit/{name}.py", ids)
        for name in ("cast_voice", "eleven", "env"):
            self.assertIn(f"tools/vidkit/js/{name}.mjs", ids)

    def test_env_helper_is_internal_and_gates_patch_routed(self):
        reg = json.loads((ROOT / "tools/registry.json").read_text())
        by_id = {t["id"]: t for t in reg["tools"]}
        routed = {tid for r in reg["routes"] for tid in r["tools"]}
        self.assertTrue(by_id["tools/vidkit/js/env.mjs"]["internal_reason"])
        self.assertIn("tools/vidkit/gates.py", routed)
        self.assertIn("tools/vidkit/patch.py", routed)


class FfprobeScanTest(FakeRoot):
    def probe_reg(self, **over):
        return registry(
            entry(),
            entry(id="tools/new_probe.py", tasks=["probe"], internal_reason="test"),
            **over,
        )

    def setUp(self):
        super().setUp()
        (self.root / "tools/new_probe.py").write_text("x = 1\n")

    def scan(self, reg):
        return [p for p in registry_build.validate(reg, self.root, coverage=True) if "ffprobe" in p]

    def test_unlisted_ffprobe_reported_exactly(self):
        (self.root / "tools/new_probe.py").write_text("# uses ffprobe\n")
        probs = self.scan(self.probe_reg())
        self.assertEqual(
            probs, ["tools/new_probe.py: ffprobe outside vidkit/ff.py or vidkit/js/ff.mjs "
            "and not in ffprobe_allow"]
        )

    def test_allowed_ffprobe_passes(self):
        (self.root / "tools/new_probe.py").write_text("# uses ffprobe\n")
        reg = self.probe_reg(ffprobe_allow=[{"id": "tools/new_probe.py", "reason": "r"}])
        self.assertEqual(self.scan(reg), [])

    def test_ff_py_is_exempt(self):
        (self.root / "tools/vidkit/ff.py").write_text("run(['ffprobe'])\n")
        probs = self.scan(self.probe_reg())
        self.assertEqual(probs, [])

    def test_ff_mjs_is_exempt(self):
        (self.root / "tools/vidkit/js").mkdir(parents=True, exist_ok=True)
        (self.root / "tools/vidkit/js/ff.mjs").write_text("execFile('ffprobe')\n")
        self.assertEqual(self.scan(self.probe_reg()), [])

    def test_init_file_is_scanned(self):
        (self.root / "tools/vidkit/__init__.py").write_text("# ffprobe\n")
        probs = self.scan(self.probe_reg())
        self.assertIn(
            "tools/vidkit/__init__.py: ffprobe outside vidkit/ff.py or vidkit/js/ff.mjs "
            "and not in ffprobe_allow",
            probs,
        )

    def test_word_boundary(self):
        (self.root / "tools/new_probe.py").write_text("x = 'myffprobe_x'\n")
        self.assertEqual(self.scan(self.probe_reg()), [])

    def test_not_scanned_without_coverage(self):
        (self.root / "tools/new_probe.py").write_text("# ffprobe\n")
        probs = registry_build.validate(self.probe_reg(), self.root)
        self.assertFalse(any("outside vidkit" in p for p in probs))

    def test_allow_schema_bad_shapes(self):
        probs = self.problems(registry(ffprobe_allow="x"))
        self.assertIn("registry: ffprobe_allow must be a list", probs)
        probs = self.problems(registry(ffprobe_allow=[{"id": 3, "reason": "r"}]))
        self.assertTrue(any("needs a string id" in p for p in probs))


class SuggestTest(unittest.TestCase):
    def run_suggest(self, text, *extra):
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools/registry_build.py"), "suggest", *extra],
            input=text,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()

    def test_concat_text_ranks_join_first(self):
        lines = self.run_suggest("ffmpeg -f concat -i list.txt out.mp4")
        self.assertTrue(lines[0].startswith("tools/vidkit/join.py \u2014 "), lines)

    def test_top_limits_lines(self):
        lines = self.run_suggest("ffmpeg concat overlay subtitles music loudness", "--top", "2")
        self.assertEqual(len(lines), 2)

    def test_default_top_is_three(self):
        lines = self.run_suggest("ffmpeg concat overlay subtitles music loudness probe")
        self.assertEqual(len(lines), 3)

    def test_nothing_scores_prints_nothing(self):
        self.assertEqual(self.run_suggest("qqq zzz"), [])

    def test_text_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.txt"
            f.write_text("ffmpeg concat", encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(ROOT / "tools/registry_build.py"), "suggest", "--text-file", str(f)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(r.returncode, 0)
        self.assertIn("tools/vidkit/join.py", r.stdout)

    def test_scoring_and_registry_order_ties(self):
        reg = {
            "tools": [
                {"id": "tools/a.py", "purpose": "Alpha thing.", "tasks": ["foo"]},
                {"id": "tools/b.py", "purpose": "Beta thing.", "tasks": ["foo"]},
                {"id": "tools/c.py", "purpose": "Gamma thing.", "tasks": ["foo", "bar"]},
            ]
        }
        ids = [t["id"] for t in registry_build.suggest_tools(reg, "foo bar", top=3)]
        self.assertEqual(ids, ["tools/c.py", "tools/a.py", "tools/b.py"])

    def test_purpose_words_score_once_and_need_four_letters(self):
        reg = {"tools": [{"id": "tools/a.py", "purpose": "Mix the mix of audio audio.", "tasks": ["zzz"]}]}
        self.assertEqual(registry_build.score_tool(reg["tools"][0], {"mix", "audio", "the"}), 1)


class HyphenTagScoringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads((ROOT / "tools/registry.json").read_text(encoding="utf-8"))

    def scores(self, tool, text):
        # score through the public ranking path: a one-tool registry lists the tool only when score > 0
        return bool(registry_build.suggest_tools({"tools": [tool]}, text, top=1))

    def test_clip_manifest_text_ranks_probe_clips_first(self):
        top = registry_build.suggest_tools(self.reg, "write work/clip-manifest.json", top=1)
        self.assertEqual(top[0]["id"], "tools/probe_clips.py")

    def test_gate_av_tag_scores_its_tool(self):
        tool = next(t for t in self.reg["tools"] if "gate-av" in t.get("tasks", []))
        self.assertTrue(self.scores(tool, "run the gate-av check"))

    def test_concat_still_ranks_join_first(self):
        top = registry_build.suggest_tools(self.reg, "ffmpeg -f concat -i list.txt out.mp4", top=1)
        self.assertEqual(top[0]["id"], "tools/vidkit/join.py")

    def test_every_task_tag_scores_its_own_tool(self):
        dead = [
            (t["id"], tag)
            for t in self.reg["tools"]
            for tag in t.get("tasks", [])
            if not self.scores(t, tag)
        ]
        self.assertEqual(dead, [])

    def test_whole_hyphen_tag_scores_two_and_parts_one_without_double_count(self):
        tool = {"id": "tools/a.py", "purpose": "Zzz.", "tasks": ["clip-manifest"]}
        whole = registry_build.score_tool(tool, registry_build.text_words("clip-manifest"))
        part = registry_build.score_tool(tool, registry_build.text_words("manifest only"))
        self.assertEqual(whole, 2)
        self.assertEqual(part, 1)

    def test_text_token_hyphen_parts_are_added(self):
        words = registry_build.text_words("Clip-Manifest concat")
        self.assertTrue({"clip-manifest", "clip", "manifest", "concat"} <= words)


class HookTest(unittest.TestCase):
    REG = {"tools": [{"id": "tools/vidkit/join.py", "purpose": "Join clips.", "tasks": ["concat"]}]}

    def payload(self, path="/proj/s.py", key="content", text="ffmpeg -f concat", tool="Write"):
        return {"tool_name": tool, "tool_input": {"file_path": path, key: text}}

    def test_should_fire_table(self):
        cases = [
            ("write content", self.payload(), True),
            ("edit new_string", self.payload(key="new_string", tool="Edit"), True),
            ("md no fire", self.payload(path="/proj/n.md"), False),
            ("mjs fires", self.payload(path="/proj/n.mjs"), True),
            ("sh fires", self.payload(path="/proj/n.sh"), True),
            ("under tools", self.payload(path=str(ROOT / "tools/x.py")), False),
            ("under tests", self.payload(path=str(ROOT / "tests/py/x.py")), False),
            ("under templates", self.payload(path=str(ROOT / "templates/x.py")), False),
            ("outside root with tools dir fires", self.payload(path="/other/tools/x.py"), True),
            ("no keyword", self.payload(text="print('hello')"), False),
            ("capital Remotion", self.payload(text="import Remotion"), True),
            ("ffprobe", self.payload(text="run ffprobe"), True),
            ("empty content", self.payload(text=""), False),
            ("missing tool_input", {"tool_name": "Write"}, False),
            ("tool_input not dict", {"tool_input": "x"}, False),
            ("payload not dict", ["x"], False),
            ("garbage", None, False),
            ("path not string", {"tool_input": {"file_path": 3, "content": "ffmpeg"}}, False),
            ("content not string", {"tool_input": {"file_path": "/p/a.py", "content": 5}}, False),
        ]
        for name, payload, want in cases:
            with self.subTest(name):
                self.assertEqual(registry_build.should_fire(payload, ROOT), want)

    def test_large_content_scans_first_200kb_only(self):
        late = "x" * (registry_build.SCAN_LIMIT + 10) + " ffmpeg"
        self.assertFalse(registry_build.should_fire(self.payload(text=late), ROOT))
        early = "ffmpeg " + "x" * (registry_build.SCAN_LIMIT + 10)
        self.assertTrue(registry_build.should_fire(self.payload(text=early), ROOT))

    def test_hook_output_json_with_suggestion(self):
        out = json.loads(registry_build.hook_output(self.payload(), self.REG))
        h = out["hookSpecificOutput"]
        self.assertEqual(h["hookEventName"], "PreToolUse")
        ctx = h["additionalContext"]
        self.assertTrue(ctx.startswith("gaspol-video: tools that already do similar work:\n"))
        self.assertIn("tools/vidkit/join.py \u2014 Join clips.", ctx)
        self.assertTrue(ctx.endswith(registry_build.HOOK_RULE))

    def test_hook_output_no_match_is_rule_only(self):
        reg = {"tools": [{"id": "tools/a.py", "purpose": "Alpha.", "tasks": ["qqq"]}]}
        ctx = json.loads(registry_build.hook_output(self.payload(), reg))["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(ctx, registry_build.HOOK_RULE)


class ScriptTest(unittest.TestCase):
    def test_help_runs_as_script(self):
        r = subprocess.run(
            [sys.executable, str(ROOT / "tools/registry_build.py"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("validate", r.stdout)


if __name__ == "__main__":
    unittest.main()
