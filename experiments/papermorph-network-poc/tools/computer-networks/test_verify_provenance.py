import shutil
import tempfile
import unittest
from pathlib import Path

import verify_provenance


SKILL_HASH = "a75a15df05d06ea19bfd25812d63272a46257b360ef47b8d2b4a79e24cbe0ac7"
ENGINE_HASH = "9fb78c741104edadad665e5bc9120f5317daecb3c9013bc31a2c2f3f4b3862fc"


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / ".qoder" / "skills" / "papermorph"
        self.engine = self.root / "engine"
        self.skill.mkdir(parents=True)
        self.engine.mkdir()
        (self.skill / "a.txt").write_bytes(b"alpha\n")
        (self.engine / "b.js").write_bytes(b"beta\n")
        self.record = {
            "skill_tree_sha256": SKILL_HASH,
            "engine_tree_sha256": ENGINE_HASH,
        }

    def test_tree_hash_matches_fixed_digest(self):
        self.assertEqual(verify_provenance.tree_hash(self.skill), SKILL_HASH)

    def test_matching_trees_pass(self):
        self.assertEqual(verify_provenance.verify(self.root, self.record), [])

    def test_crlf_checkout_matches_lf_record(self):
        (self.skill / "a.txt").write_bytes(b"alpha\r\n")
        (self.engine / "b.js").write_bytes(b"beta\r\n")
        self.assertEqual(verify_provenance.verify(self.root, self.record), [])

    def test_binary_crlf_is_not_normalized(self):
        mixed = self.root / "mixed"
        mixed.mkdir()
        (mixed / "a.txt").write_bytes(b"alpha\r\nbeta\n")
        (mixed / "b.bin").write_bytes(b"\x00alpha\r\n\xff")
        expected = "d140136135288932d87f85178ec62f6292abc06d59dcfdd7fc66945e020d07f5"
        self.assertEqual(verify_provenance.tree_hash(mixed), expected)
        (mixed / "b.bin").write_bytes(b"\x00alpha\n\xff")
        self.assertNotEqual(verify_provenance.tree_hash(mixed), expected)

    def test_nul_free_binary_crlf_is_not_normalized(self):
        mixed = self.root / "nul-free-binary"
        mixed.mkdir()
        (mixed / "a.txt").write_bytes(b"alpha\r\n")
        (mixed / "c.dat").write_bytes(b"ASCII\r\n")
        expected = "ed0fd023972fd4a6f06e30ad82bf5b6042787d8d5eed479d2a23f9e272dacf80"
        self.assertEqual(verify_provenance.tree_hash(mixed), expected)
        (mixed / "c.dat").write_bytes(b"ASCII\n")
        self.assertNotEqual(verify_provenance.tree_hash(mixed), expected)

    def test_content_drift_fails(self):
        (self.skill / "a.txt").write_text("changed\n", encoding="utf-8")
        errors = verify_provenance.verify(self.root, self.record)
        self.assertTrue(any("skill_tree_sha256" in error for error in errors))

    def test_extra_file_fails(self):
        (self.engine / "extra.js").write_text("extra\n", encoding="utf-8")
        errors = verify_provenance.verify(self.root, self.record)
        self.assertTrue(any("engine_tree_sha256" in error for error in errors))

    def test_missing_tree_fails(self):
        shutil.rmtree(self.engine)
        errors = verify_provenance.verify(self.root, self.record)
        self.assertTrue(any("engine" in error and "missing" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
