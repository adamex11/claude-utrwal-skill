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

    def test_wszystkie_sciezki_wskazuja_na_niestandardowy_katalog(self):
        self.uruchom()
        konfig = self.konfig.resolve().as_posix()
        for plik in self.cel.rglob("*.md"):
            tresc = plik.read_text(encoding="utf-8")
            self.assertNotIn("~/.claude/", tresc, plik)
        tresc = (self.cel / "SKILL.md").read_text(encoding="utf-8")
        # Pliki skilla wskazuje ${CLAUDE_SKILL_DIR} (podstawia Claude Code), przepisywane są tylko miejsca zapisu
        self.assertIn("${CLAUDE_SKILL_DIR}/scripts/wyciagnij_rozmowe.py", tresc)
        self.assertNotIn(f"{konfig}/skills/utrwal-skill/", tresc)
        self.assertIn(f"{konfig}/CLAUDE.md", tresc)  # globalny CLAUDE.md
        self.assertIn(f"{konfig}/skills/<nazwa>/", tresc)  # miejsce zapisu skilli globalnych

    def aktualizuj_z_awaria(self, awaria):
        """Aktualizacja w podprocesie z podmienioną funkcją; awaria musi wystąpić i zostać zgłoszona."""
        self.uruchom()
        (self.cel / "znacznik.txt").write_text("stara wersja", encoding="utf-8")
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.konfig), PYTHONIOENCODING="utf-8")
        kod = ("import pathlib, shutil, install\n" + awaria +
               "try:\n    install.instaluj()\nexcept OSError as e:\n    print('AWARIA:', e)\n")
        r = subprocess.run([sys.executable, "-c", kod], cwd=str(REPO), env=env, capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("AWARIA: dysk pełny", r.stdout, r.stderr)
        self.assertTrue((self.cel / "znacznik.txt").is_file())
        self.assertTrue((self.cel / "SKILL.md").is_file())
        resztki = [p.name for p in self.cel.parent.iterdir() if p.name.startswith(".")]
        self.assertEqual(resztki, [])

    def test_nieudane_kopiowanie_zostawia_stary_skill(self):
        self.aktualizuj_z_awaria("def awaria(*a, **k): raise OSError('dysk pełny')\n"
                                 "shutil.copytree = awaria\n")

    def test_nieudana_podmiana_przywraca_stary_skill(self):
        # Stary skill jest już przeniesiony do .utrwal-skill-stary, gdy zawodzi wstawienie nowego
        self.aktualizuj_z_awaria("oryginal = pathlib.Path.rename\n"
                                 "def awaria(self, cel):\n"
                                 "    if self.parent.name.startswith('.utrwal-skill-nowy'):\n"
                                 "        raise OSError('dysk pełny')\n"
                                 "    return oryginal(self, cel)\n"
                                 "pathlib.Path.rename = awaria\n")

    @unittest.skipIf(sys.platform == "win32", "dowiązania na Windows wymagają uprawnień administratora")
    def test_dowiazanie_nie_jest_nadpisywane(self):
        klon = Path(self.tmp.name) / "klon"
        klon.mkdir()
        (self.konfig / "skills").mkdir()
        self.cel.symlink_to(klon, target_is_directory=True)
        kod, out = self.uruchom()
        self.assertEqual(kod, 1)
        self.assertIn("dowiązaniem", out)
        self.assertTrue(self.cel.is_symlink())
        kod, out = self.uruchom("--uninstall")
        self.assertEqual(kod, 0, out)
        self.assertFalse(self.cel.exists())
        self.assertTrue(klon.is_dir())

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
        self.assertIn("\nargument-hint: ", tresc.split("\n---\n", 1)[0])

    def test_bez_dlugich_myslnikow(self):
        for plik in (REPO / "src").rglob("*"):
            if plik.is_file() and plik.suffix in (".md", ".py"):
                tresc = plik.read_text(encoding="utf-8")
                self.assertNotIn("\u2014", tresc, plik)
                self.assertNotIn("\u2013", tresc, plik)


if __name__ == "__main__":
    unittest.main()
