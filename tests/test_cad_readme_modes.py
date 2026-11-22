"""The README checker keeps the legacy still until the committed index shows the declared withdrawal."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "cad_readmes", Path(__file__).resolve().parents[1] / "scripts/cad-readmes.py")
cad_readmes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cad_readmes)

CONFIG = {"siteUrl": "https://example.invalid/site/"}
REASON = "Synthetic withdrawal."


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ReadmeModes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.files = {
            "README.md": b"# Synthetic\n",
            "README.old.md": b"# Synthetic before\n",
            "docs/robot/preliminary-layout-900.png": b"synthetic still",
            "docs/preliminary-design/releases.json": json.dumps(
                {"releases": ["layout-900"], "designStatus": {"layout-900": "in-progress"}, "current": "layout-900"}).encode(),
            "docs/preliminary-design/releases/layout-900/release.json": b"{}",
            "docs/preliminary-design/releases/layout-900/receipt.json": b'{"receipt": 1}',
            "docs/preliminary-design/releases/layout-900/review-scene.json.gz": b"scene",
        }
        release = "docs/preliminary-design/releases/layout-900/"
        self.files["docs/robot/preliminary-layout-900.json"] = json.dumps({
            "release": "layout-900", "imageSha256": sha(self.files["docs/robot/preliminary-layout-900.png"]),
            "releaseRecordSha256": sha(self.files[release + "release.json"]),
            "receiptSha256": sha(self.files[release + "receipt.json"]),
            "sceneSha256": sha(self.files[release + "review-scene.json.gz"]),
            "caption": {"title": "Synthetic layout", "alt": "Alt.", "pose": "Parked.", "scope": "Blocks only."}}).encode()
        self.policy = {
            "detailedDesigns": {"index": "docs/detailed-design/designs.json",
                                "withdrawn": [{"design": "draft-900", "reason": REASON, "files": {}}]},
            "preliminaryReadmeArchive": {
                "readmeSha256": sha(self.files["README.md"]), "archive": "README.old.md",
                "archivedSha256": sha(self.files["README.old.md"]),
                "image": "docs/robot/preliminary-layout-900.png",
                "imageSha256": sha(self.files["docs/robot/preliminary-layout-900.png"])}}

    def index(self, status="withdrawn", current=None, designs=("draft-900",)):
        return json.dumps({"current": current, "designs": list(designs),
                           "designStatus": {d: status for d in designs}}).encode()

    def feature(self, index=None, update=False):
        for name, data in self.files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_bytes(data)
        (self.root / ".github").mkdir(exist_ok=True)
        (self.root / ".github/public-model-policy.json").write_text(json.dumps(self.policy), encoding="utf-8")
        if index is not None:
            (self.root / "docs/detailed-design").mkdir(parents=True, exist_ok=True)
            (self.root / "docs/detailed-design/designs.json").write_bytes(index)
        return cad_readmes.preliminary_feature(self.root, CONFIG, update)

    def test_legacy_mode_without_a_declaration(self):
        del self.policy["detailedDesigns"]
        self.assertIsNone(self.feature(self.index()))

    def test_legacy_mode_with_an_empty_declaration(self):
        self.policy["detailedDesigns"]["withdrawn"] = []
        self.assertIsNone(self.feature(self.index()))

    def test_legacy_mode_until_the_index_is_committed(self):
        self.assertIsNone(self.feature())

    def test_legacy_mode_while_the_declared_design_is_not_withdrawn(self):
        for status in ("effective", "in-progress", "superseded"):
            self.assertIsNone(self.feature(self.index(status, current="draft-900" if status != "superseded" else None)))
        self.assertIsNone(self.feature(self.index(designs=("another-900",))))

    def test_damaged_index_is_an_error_not_a_mode(self):
        for damaged in (b"", b"{", b"[]", b"null", b'{"designs": ["draft-900"]}',
                        b'{"designs": "draft-900", "designStatus": {"draft-900": "withdrawn"}}',
                        b'{"designs": ["draft-900"], "designStatus": ["withdrawn"]}'):
            with self.assertRaisesRegex(ValueError, "Unreadable detailed design index"):
                self.feature(damaged)

    def test_withdrawal_features_the_pinned_preliminary_still(self):
        feature = self.feature(self.index())
        self.assertEqual(feature["heading"], "Preliminary design · in progress · layout-900")
        self.assertEqual(feature["image"], self.root / "docs/robot/preliminary-layout-900.png")
        self.assertEqual(feature["review"], "https://example.invalid/site/preliminary-design/")
        self.assertEqual(feature["text"], "Synthetic layout. Parked. Blocks only.")

    def test_withdrawal_needs_the_approved_handoff(self):
        del self.policy["preliminaryReadmeArchive"]
        with self.assertRaisesRegex(ValueError, "README handoff"):
            self.feature(self.index())

    def test_a_different_still_is_refused(self):
        self.files["docs/robot/preliminary-layout-900.png"] = b"another still"
        with self.assertRaisesRegex(ValueError, "Changed CAD evidence"):
            self.feature(self.index())

    def test_a_still_of_another_release_state_is_refused(self):
        self.files["docs/preliminary-design/releases/layout-900/receipt.json"] = b'{"receipt": 2}'
        with self.assertRaisesRegex(ValueError, "differs from the current release"):
            self.feature(self.index())

    def test_a_different_readme_or_archive_is_refused_when_checking(self):
        for name in ("README.md", "README.old.md"):
            saved, self.files[name] = self.files[name], b"# Edited\n"
            with self.assertRaisesRegex(ValueError, "approved handoff"):
                self.feature(self.index())
            self.assertIsNotNone(self.feature(self.index(), update=True))
            self.files[name] = saved

    def test_a_current_detailed_design_is_not_silently_replaced(self):
        for index in (self.index(current="draft-900"), json.dumps({
                "current": None, "designs": ["draft-900", "detail-901"],
                "designStatus": {"draft-900": "withdrawn", "detail-901": "withdrawn"}}).encode()):
            with self.assertRaisesRegex(ValueError, "needs its own README still"):
                self.feature(index)


if __name__ == "__main__":
    unittest.main()
