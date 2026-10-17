"""check_overlay_strings.py: a string on screen that the script never approved fails the shot."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "check_overlay_strings.py"

SCRIPT = """# av-script

## Blok 4

Approved: `SETUJUI`, `KELUAR YARD`, `08:41`, `Truk 1 dari 3` … `Truk 3 dari 3`

## Blok 5

`NOT HERE`
"""


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


class CheckOverlayStringsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "av-script.md").write_text(SCRIPT)

    def tearDown(self):
        self._tmp.cleanup()

    def shot(self, body):
        p = self.dir / "Shot.tsx"
        p.write_text(f"export const Shot = () => (<div>{body}</div>);\n")
        return p

    def test_approved_and_composed_strings_pass(self):
        shot = self.shot("<b>SETUJUI</b><i>KELUAR YARD 08:41</i><p>Truk 3 dari 3</p>")
        proc = run(shot, "--from-markdown", self.dir / "av-script.md", "--heading", "Blok 4")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_invented_string_fails_and_is_named(self):
        shot = self.shot("<b>SETUJUI</b><i>NOT HERE</i>")
        proc = run(shot, "--from-markdown", self.dir / "av-script.md", "--heading", "Blok 4")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("'NOT HERE' is not in the approved list", proc.stdout)

    def test_no_approved_list_is_exit_2(self):
        proc = run(self.shot("<b>SETUJUI</b>"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no approved strings loaded", proc.stderr)


if __name__ == "__main__":
    unittest.main()
