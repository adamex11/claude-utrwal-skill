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

    def test_bash_bez_zmian_pliku_nie_jest_oznaczany(self):
        sciezka = str(Path(self.tmp.name) / "a.js")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": sciezka, "content": "x"}),
            narzedzie("t2", "Bash", {"command": "node a.js 2>&1 | tail && cat a.js 2>/dev/null"}),  # uruchomienie i odczyt
            narzedzie("t3", "Bash", {"command": "sed -i '' s/x/y/ data.json"}),  # inny plik zawierający "a.js"
        ])
        _, lista = self.uruchom("--sesja", "s1", "--pliki")
        self.assertNotIn("zmieniany też przez Bash", lista)
        self.zapisz_sesje("s2", [
            narzedzie("t1", "Write", {"file_path": sciezka, "content": "x"}),
            narzedzie("t2", "Bash", {"command": "echo y >> a.js"}),
        ])
        _, lista = self.uruchom("--sesja", "s2", "--pliki")
        self.assertIn("zmieniany też przez Bash", lista)
        for komenda in ("npx prettier --write a.js", "sed -e s/x/y/ -i a.js", "python3 gen.py > a.js 2>&1"):
            self.zapisz_sesje("s3", [
                narzedzie("t1", "Write", {"file_path": sciezka, "content": "x"}),
                narzedzie("t2", "Bash", {"command": komenda}),
            ])
            _, lista = self.uruchom("--sesja", "s3", "--pliki")
            self.assertIn("zmieniany też przez Bash", lista, komenda)

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

    def test_najnowszy_tytul_z_dlugiej_sesji(self):
        dlugie = [wpis_uzytkownika("Pierwsza prośba"), {"type": "ai-title", "aiTitle": "Stary tytuł"}]
        dlugie += [tekst_asystenta("x" * 1000) for _ in range(400)]  # ok. 400 KB, więcej niż czytana końcówka
        dlugie += [{"type": "ai-title", "aiTitle": "Nowy tytuł"}]
        self.zapisz_sesje("s1", dlugie)
        self.zapisz_sesje("s2", [{"type": "ai-title", "aiTitle": "Tylko na początku"}]
                          + [tekst_asystenta("x" * 1000) for _ in range(400)])
        _, out = self.uruchom("--lista")
        self.assertIn("Nowy tytuł", out)
        self.assertNotIn("Stary tytuł", out)
        self.assertIn("Pierwsza prośba", out)
        self.assertIn("Tylko na początku", out)  # brak tytułu w końcówce = czytamy cały plik

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


class Recenzja(Baza):
    """Przypadki z recenzji: argumenty komend, raporty subagentów, uszkodzone dane, sekrety, nieudane Edit."""

    def test_argumenty_komendy_slash(self):
        self.zapisz_sesje("s1", [wpis_uzytkownika(
            "<command-message>raport</command-message>\n<command-name>/raport</command-name>\n"
            "<command-args>ABC 2026</command-args>")])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn(">> UŻYTKOWNIK: /raport ABC 2026", out)

    def test_raport_subagenta_i_zadanie_w_tle(self):
        cialo = ("[Subagent hand-back] Ramka harnessu. The report follows:\n"
                 "  ## Wynik recenzji\n  Znaleziono 2 problemy w parserze.")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Agent", {"description": "Recenzja parsera", "prompt": "Sprawdź parser"}),
            wpis_uzytkownika(cialo, isMeta=True, origin={"kind": "peer", "name": "general-purpose", "body": cialo}),
            wpis_uzytkownika("<task-notification>\n<task-id>x</task-id>\n<status>completed</status>\n"
                             "<summary>Agent \"Recenzja parsera\" finished</summary>\n"
                             "<result>Parser poprawiony</result>\n</task-notification>"),
        ])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn("<< RAPORT SUBAGENTA (general-purpose):", out)
        self.assertIn("Znaleziono 2 problemy w parserze.", out)
        self.assertNotIn("Ramka harnessu", out)
        self.assertIn("[ZADANIE W TLE: completed]", out)
        self.assertIn("[WYNIK ZADANIA] Parser poprawiony", out)

    def test_uszkodzony_jsonl_i_ucięty_znak(self):
        plik = self.zapisz_sesje("s1", [wpis_uzytkownika("Pierwsza prośba")])
        with plik.open("ab") as f:
            f.write(b'{"type": "user", "message": {"content": "niedoko\n')  # urwany JSON
            f.write(b"\xc5\n")  # ucięty znak wielobajtowy (pierwszy bajt "ł")
            f.write(json.dumps(wpis_uzytkownika("Druga prośba"), ensure_ascii=False).encode("utf-8") + b"\n")
        kod, out = self.uruchom("--sesja", "s1")
        self.assertEqual(kod, 0, out)
        self.assertIn("Pierwsza prośba", out)
        self.assertIn("Druga prośba", out)

    def test_streszczenie_po_kompakcji(self):
        self.zapisz_sesje("s1", [wpis_uzytkownika("Podsumowanie wcześniejszej pracy: raport ABC", isCompactSummary=True)])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn("[STRESZCZENIE PO KOMPAKCJI]", out)
        self.assertIn("raport ABC", out)

    def test_nieudany_edit_nie_jest_nakladany(self):
        sciezka = str(Path(self.tmp.name) / "usuniety.py")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": sciezka, "content": "x = 1\n"}),
            narzedzie("t2", "Edit", {"file_path": sciezka, "old_string": "x = 1", "new_string": "x = 2"}),
            wynik("t2", "File has been modified since read", blad=True),
            narzedzie("t3", "Edit", {"file_path": sciezka, "old_string": "x = 1", "new_string": "x = 3"}),
        ])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "usuniety")
        self.assertIn("x = 3", out)
        self.assertNotIn("x = 2", out)

    def test_polskie_znaki_w_sciezce_projektu(self):
        projekt = Path(self.tmp.name).resolve() / "Łódź" / "Zażółć" / "projekt"
        projekt.mkdir(parents=True)
        folder = self.konfig / "projects" / koduj(projekt)
        folder.mkdir(parents=True)
        self.zapisz_sesje("pl", [{"type": "ai-title", "aiTitle": "Gęślą jaźń"}], folder=folder)
        kod, out = self.uruchom("--lista", "--projekt", str(projekt))
        self.assertEqual(kod, 0, out)
        self.assertIn("Gęślą jaźń", out)

    def test_maskowanie_sekretow(self):
        token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
        sciezka = Path(self.tmp.name) / "klient.py"
        sciezka.write_text('API_KEY = "abcdefgh12345678"\nklucz = os.environ["API_KEY"]\n', encoding="utf-8")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Bash", {"command": f"curl -H 'Authorization: Bearer abcdef123456789' -H 'X: {token}' x"}),
            narzedzie("t2", "Write", {"file_path": str(sciezka), "content": "stara"}),
        ])
        _, out = self.uruchom("--sesja", "s1")
        self.assertNotIn("abcdef123456789", out)
        self.assertNotIn(token, out)
        self.assertIn("Bearer [SEKRET]", out)
        self.assertIn("Zamaskowano", out)
        _, pliki = self.uruchom("--sesja", "s1", "--pliki", "klient")
        self.assertNotIn("abcdefgh12345678", pliki)
        self.assertIn('os.environ["API_KEY"]', pliki)  # kod bez sekretu zostaje nietknięty

    def test_sekrety_bez_cudzyslowu_i_w_argumentach_skilla(self):
        token = "ghp_" + "Z9y8X7w6V5u4T3s2R1q0P9o8"
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Bash", {"command": "export NOTION_TOKEN=secret_abcdef123456 && "
                                                "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI123 aws s3 ls && "
                                                "export TOKEN=$INNA_ZMIENNA"}),
            narzedzie("t2", "Write", {"file_path": "/x/ustawienia.py", "content": "x"}),
            narzedzie("t3", "Skill", {"skill": "publikuj", "args": f"--token {token}"}),
        ])
        _, out = self.uruchom("--sesja", "s1")
        self.assertNotIn("secret_abcdef123456", out)
        self.assertNotIn("wJalrXUtnFEMI123", out)
        self.assertIn("NOTION_TOKEN=[SEKRET]", out)
        self.assertIn("TOKEN=$INNA_ZMIENNA", out)  # odwołanie do zmiennej to nie sekret
        self.assertNotIn(token, out)
        self.assertIn("publikuj --token [SEKRET:github-token]", out)

    def test_kod_z_podobnymi_nazwami_nie_jest_maskowany(self):
        sciezka = Path(self.tmp.name) / "model.py"
        kod = ('tokenizer = "gpt2-medium"\ntoken_url = "https://oauth2.googleapis.com/token"\n'
               'secret_name = "prod/database"\n')
        sciezka.write_text(kod, encoding="utf-8")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": str(sciezka), "content": "x"}),
            narzedzie("t2", "Bash", {"command": "MAX_TOKENS=100000000 TOKEN_FILE=/home/u/token.txt python3 model.py"}),
        ])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "model")
        self.assertIn(kod.strip(), out)
        _, os_czasu = self.uruchom("--sesja", "s1")
        self.assertIn("MAX_TOKENS=100000000", os_czasu)
        self.assertNotIn("Zamaskowano", os_czasu)

    def test_sekrety_w_json_i_po_spacji(self):
        self.zapisz_sesje("s1", [
            narzedzie("t1", "mcp__serwis__login", {"user": "jan", "password": "tajnehaslo123"}),
            narzedzie("t2", "Bash", {"command": "cli login --token abcdefghijkl123"}),
            narzedzie("t3", "Skill", {"skill": "publikuj", "args": "--api-key zxcvbnmasdf987"}),
        ])
        _, out = self.uruchom("--sesja", "s1")
        for sekret in ("tajnehaslo123", "abcdefghijkl123", "zxcvbnmasdf987"):
            self.assertNotIn(sekret, out)
        self.assertIn('"password": "[SEKRET]"', out)
        self.assertIn("Zamaskowano 3 fragm.", out)  # każdy sekret liczony raz, mimo kilku przejść

    def test_sekret_w_nazwie_ze_skladnikiem(self):
        sciezka = Path(self.tmp.name) / "ustawienia.py"
        sciezka.write_text('SECRET_KEY = "django-insecure-abc123xyz"\n', encoding="utf-8")
        self.zapisz_sesje("s1", [narzedzie("t1", "Write", {"file_path": str(sciezka), "content": "x"})])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "ustawienia")
        self.assertNotIn("django-insecure-abc123xyz", out)
        self.assertIn('SECRET_KEY = "[SEKRET]"', out)

    def test_multiedit_i_replace_all(self):
        sciezka = str(Path(self.tmp.name) / "usuniety.py")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": sciezka, "content": "a = 1\na = 1\nb = 2\n"}),
            narzedzie("t2", "MultiEdit", {"file_path": sciezka, "edits": [
                {"old_string": "a = 1", "new_string": "a = 9", "replace_all": True},
                {"old_string": "b = 2", "new_string": "b = 8"}]}),
        ])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "usuniety")
        self.assertIn("a = 9\na = 9\nb = 8", out)
        self.assertIn("Edit: 2", out)
        self.assertNotIn("UWAGA", out)

    def test_plik_tylko_edytowany(self):
        sciezka = str(Path(self.tmp.name) / "usuniety.py")
        self.zapisz_sesje("s1", [narzedzie("t1", "Edit", {"file_path": sciezka, "old_string": "a", "new_string": "b"})])
        _, lista = self.uruchom("--sesja", "s1", "--pliki")
        self.assertIn("tylko Edit", lista)
        self.assertIn("nie wszystkie Edit dało się odtworzyć", lista)
        _, tresc = self.uruchom("--sesja", "s1", "--pliki", "usuniety")
        self.assertIn("brak pełnej treści", tresc)


if __name__ == "__main__":
    unittest.main()
