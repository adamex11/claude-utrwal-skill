"""Testy instalatora na tymczasowym katalogu konfiguracji (CLAUDE_CONFIG_DIR)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class Instalator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.konfig = Path(self.tmp.name) / "claude"
        self.konfig.mkdir()
        self.cel = self.konfig / "skills" / "utrwal-skill"

    def tearDown(self):
        self.tmp.cleanup()

    def uruchom(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.konfig), PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, str(REPO / "install.py"), *args], capture_output=True,
                           text=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout + r.stderr

    def test_instalacja_aktualizacja_deinstalacja(self):
        kod, out = self.uruchom()
        self.assertEqual(kod, 0, out)
        self.assertIn("Zainstalowano", out)
        for plik in ("SKILL.md", "scripts/wyciagnij_rozmowe.py", "references/szablon.md", "references/lista_kontrolna.md"):
            self.assertTrue((self.cel / plik).is_file(), plik)

        kod, out = self.uruchom()
        self.assertEqual(kod, 0, out)
        self.assertIn("Zaktualizowano", out)

        kod, out = self.uruchom("--uninstall")
        self.assertEqual(kod, 0, out)
        self.assertFalse(self.cel.exists())

    def test_sciezki_w_skill_md_wskazuja_na_niestandardowy_katalog(self):
        self.uruchom()
        tresc = (self.cel / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("~/.claude/skills/utrwal-skill", tresc)
        self.assertIn(self.cel.resolve().as_posix(), tresc)

    def test_sprawdz_nic_nie_instaluje(self):
        kod, out = self.uruchom("--sprawdz")
        self.assertEqual(kod, 0, out)
        self.assertFalse(self.cel.exists())

    def test_brak_katalogu_claude(self):
        self.konfig.rmdir()
        kod, out = self.uruchom()
        self.assertEqual(kod, 1)
        self.assertIn("Brak katalogu Claude Code", out)


class SkillMd(unittest.TestCase):
    def test_frontmatter(self):
        tresc = (REPO / "src" / "utrwal-skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(tresc.startswith("---\nname: utrwal-skill\n"))
        self.assertIn("disable-model-invocation: true", tresc)

    def test_bez_dlugich_myslnikow(self):
        for plik in (REPO / "src").rglob("*"):
            if plik.is_file() and plik.suffix in (".md", ".py"):
                tresc = plik.read_text(encoding="utf-8")
                self.assertNotIn("\u2014", tresc, plik)
                self.assertNotIn("\u2013", tresc, plik)


if __name__ == "__main__":
    unittest.main()
