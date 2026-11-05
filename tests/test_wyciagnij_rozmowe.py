"""Testy skryptu wyciagnij_rozmowe.py na sztucznych zapisach sesji (bez danych prawdziwych rozmów)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKRYPT = Path(__file__).resolve().parents[1] / "src" / "utrwal-skill" / "scripts" / "wyciagnij_rozmowe.py"


def koduj(sciezka):
    import re
    return re.sub(r"[^A-Za-z0-9]", "-", str(sciezka))


def wpis_uzytkownika(tekst, **extra):
    return {"type": "user", "message": {"role": "user", "content": tekst}, **extra}


def narzedzie(id_, nazwa, wejscie):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": id_, "name": nazwa, "input": wejscie}]}}


def wynik(id_, tresc, blad=False):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": id_, "content": tresc, "is_error": blad}]}}


def tekst_asystenta(tekst):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "TAJNE_MYSLENIE"}, {"type": "text", "text": tekst}]}}


class Baza(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.konfig = Path(self.tmp.name) / "claude"
        # Claude Code zapisuje katalog projektu tak, jak widzi go proces (po rozwinięciu dowiązań, np. /private/var)
        self.projekt = Path(self.tmp.name).resolve() / "Kurs" / "Day 4" / "moj-projekt"
        self.projekt.mkdir(parents=True)
        self.folder = self.konfig / "projects" / koduj(self.projekt)
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def zapisz_sesje(self, sid, rekordy, folder=None):
        plik = (folder or self.folder) / f"{sid}.jsonl"
        with plik.open("w", encoding="utf-8") as f:
            for r in rekordy:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return plik

    def uruchom(self, *args, sesja=None):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.konfig), PYTHONIOENCODING="utf-8")
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        if sesja:
            env["CLAUDE_CODE_SESSION_ID"] = sesja
        r = subprocess.run([sys.executable, str(SKRYPT), *args], capture_output=True, text=True,
                           encoding="utf-8", env=env, cwd=str(self.projekt))
        return r.returncode, r.stdout + r.stderr


class OsCzasu(Baza):
    def setUp(self):
        super().setUp()
        self.zapisz_sesje("s1", [
            {"type": "ai-title", "aiTitle": "Testowa sesja"},
            wpis_uzytkownika("Zrób raport dla spółki ABC"),
            wpis_uzytkownika("Base directory for this skill: /x", isMeta=True),
            wpis_uzytkownika("<task-notification>coś w tle</task-notification>"),
            tekst_asystenta("Robię raport."),
            narzedzie("t1", "Bash", {"command": "python3 raport.py ABC"}),
            wynik("t1", "Traceback: KeyError 'przychody'", blad=True),
            narzedzie("t2", "Write", {"file_path": "/x/raport.py", "content": "TRESC_PLIKU_NIE_DO_OSI"}),
            wynik("t3", 'User has answered your questions: "Format?"="docx"'),
            {"type": "assistant", "isSidechain": True, "message": {"content": [{"type": "text", "text": "SUBAGENT"}]}},
        ])

    def test_zostawia_istotne_i_pomija_szum(self):
        kod, out = self.uruchom("--sesja", "s1")
        self.assertEqual(kod, 0)
        self.assertIn(">> UŻYTKOWNIK: Zrób raport dla spółki ABC", out)
        self.assertIn("$ python3 raport.py ABC", out)
        self.assertIn("!! BŁĄD (Bash", out)
        self.assertIn("KeyError", out)
        self.assertIn("/x/raport.py", out)
        self.assertIn("ODPOWIEDŹ UŻYTKOWNIKA", out)
        for szum in ("TAJNE_MYSLENIE", "TRESC_PLIKU_NIE_DO_OSI", "Base directory", "task-notification", "SUBAGENT"):
            self.assertNotIn(szum, out)

    def test_domyslnie_biezaca_sesja_ze_zmiennej(self):
        kod, out = self.uruchom(sesja="s1")
        self.assertEqual(kod, 0)
        self.assertIn("# Sesja s1", out)

    def test_bez_sesji_czytelny_blad(self):
        kod, out = self.uruchom()
        self.assertEqual(kod, 1)
        self.assertIn("--sesja", out)

    def test_nieznana_sesja(self):
        kod, out = self.uruchom("--sesja", "brak")
        self.assertEqual(kod, 1)
        self.assertIn("Nie znaleziono", out)

    def test_obcinanie_i_max_znakow(self):
        self.zapisz_sesje("s2", [tekst_asystenta("A" * 1000)])
        _, krotko = self.uruchom("--sesja", "s2")
        _, dlugo = self.uruchom("--sesja", "s2", "--max-znakow", "2000")
        self.assertIn("[...+700 zn.]", krotko)
        self.assertNotIn("[...", dlugo)

    def test_wyjscie_do_pliku(self):
        cel = Path(self.tmp.name) / "os.md"
        kod, out = self.uruchom("--sesja", "s1", "--wyjscie", str(cel))
        self.assertEqual(kod, 0)
        self.assertIn("Zrób raport", cel.read_text(encoding="utf-8"))


class Pliki(Baza):
    def test_lista_i_odtworzenie_usunietego_pliku(self):
        sciezka = str(Path(self.tmp.name) / "usuniety.js")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": sciezka, "content": "const a = 1;\nconst b = 2;\n"}),
            narzedzie("t2", "Edit", {"file_path": sciezka, "old_string": "b = 2", "new_string": "b = 3"}),
        ])
        _, lista = self.uruchom("--sesja", "s1", "--pliki")
        self.assertIn("BRAK NA DYSKU", lista)
        self.assertIn("Edit: 1", lista)
        _, tresc = self.uruchom("--sesja", "s1", "--pliki", "usuniety")
        self.assertIn("odtworzone z sesji", tresc)
        self.assertIn("const b = 3;", tresc)

    def test_plik_na_dysku_ma_pierwszenstwo_i_ostrzezenie_o_bash(self):
        sciezka = Path(self.tmp.name) / "build.js"
        sciezka.write_text("WERSJA_Z_DYSKU", encoding="utf-8")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": str(sciezka), "content": "WERSJA_Z_SESJI"}),
            narzedzie("t2", "Bash", {"command": "sed -i '' s/a/b/ build.js"}),
        ])
        _, lista = self.uruchom("--sesja", "s1", "--pliki")
        self.assertIn("zmieniany też przez Bash", lista)
        _, tresc = self.uruchom("--sesja", "s1", "--pliki", "build.js")
        self.assertIn("treść z dysku", tresc)
        self.assertIn("WERSJA_Z_DYSKU", tresc)
        self.assertNotIn("WERSJA_Z_SESJI", tresc)

    def test_brak_dopasowania(self):
        self.zapisz_sesje("s1", [narzedzie("t1", "Write", {"file_path": "/x/a.py", "content": "x"})])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "nieistnieje")
        self.assertIn("Żaden zapisany plik", out)


class ListaSesji(Baza):
    def test_lista_z_tytulem(self):
        self.zapisz_sesje("s1", [{"type": "ai-title", "aiTitle": "Raport ABC"}, wpis_uzytkownika("Pierwsza prośba")])
        kod, out = self.uruchom("--lista")
        self.assertEqual(kod, 0)
        self.assertIn("s1", out)
        self.assertIn("Raport ABC", out)
        self.assertIn("Pierwsza prośba", out)
        self.assertNotIn("przenoszony", out)

    def test_sesje_sprzed_przeniesienia_projektu(self):
        # Ta sama końcówka ścieżki (Kurs/Day 4/moj-projekt), ale inny początek = projekt przeniesiony
        stary = self.konfig / "projects" / koduj(Path("/stare") / "Kurs" / "Day 4" / "moj-projekt")
        stary.mkdir(parents=True)
        self.zapisz_sesje("stara", [wpis_uzytkownika("Sesja przed przeniesieniem")], folder=stary)
        self.zapisz_sesje("nowa", [wpis_uzytkownika("Sesja po przeniesieniu")])
        _, out = self.uruchom("--lista")
        self.assertIn("przenoszony", out)
        self.assertIn("stara", out)
        self.assertIn("nowa", out)

    def test_nieznany_projekt(self):
        kod, out = self.uruchom("--lista", "--projekt", str(Path(self.tmp.name) / "x" / "y" / "z"))
        self.assertEqual(kod, 1)
        self.assertIn("Brak sesji", out)


if __name__ == "__main__":
    unittest.main()
