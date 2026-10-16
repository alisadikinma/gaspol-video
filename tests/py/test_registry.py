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
        self.assertProblem(reg, "tools/composite.py: ffprobe_allow is stale")

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
