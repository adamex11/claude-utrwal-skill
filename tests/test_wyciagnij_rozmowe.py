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
        self.assertIn("Zamaskowano 0 fragm.", os_czasu)
        self.assertIn("heurystyczne", os_czasu)  # ostrzeżenie o niepełności także przy zerze

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
        self.assertNotIn("[UWAGA:", out)

    def test_plik_tylko_edytowany(self):
        sciezka = str(Path(self.tmp.name) / "usuniety.py")
        self.zapisz_sesje("s1", [narzedzie("t1", "Edit", {"file_path": sciezka, "old_string": "a", "new_string": "b"})])
        _, lista = self.uruchom("--sesja", "s1", "--pliki")
        self.assertIn("tylko Edit, brak pełnej treści", lista)
        self.assertNotIn("nie dały się nałożyć", lista)  # Edit nie zawiódł, tylko nie było bazy
        _, tresc = self.uruchom("--sesja", "s1", "--pliki", "usuniety")
        self.assertIn("brak pełnej treści", tresc)



class TrzeciaRecenzja(Baza):
    """Przypadki z recenzji Sonnet + Fable: decyzje, kompakcja, sekrety w plikach, --tylko, heredoc, odporność."""

    def test_odpowiedz_askuserquestion_z_toolUseResult(self):
        self.zapisz_sesje("s1", [
            narzedzie("q1", "AskUserQuestion", {"questions": [{"question": "Stawka?", "header": "Stawka"}]}),
            {"type": "user", "toolUseResult": {"questions": [], "answers": {"Stawka?": "180 EUR/h"},
                                               "annotations": {"Stawka?": {"notes": "netto"}}},
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "q1",
                                                      "content": "Your questions have been answered: ..."}]}},
        ])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn('>> ODPOWIEDŹ UŻYTKOWNIKA: "Stawka?" -> 180 EUR/h (notatka: netto)', out)
        self.assertIn("- AskUserQuestion: Stawka?", out)

    def test_odpowiedz_w_nowym_brzmieniu_bez_toolUseResult(self):
        self.zapisz_sesje("s1", [
            narzedzie("q1", "AskUserQuestion", {"questions": [{"question": "Format?"}]}),
            wynik("q1", 'Your questions have been answered: "Format?"="docx"'),
        ])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn('>> ODPOWIEDŹ UŻYTKOWNIKA: Your questions have been answered: "Format?"="docx"', out)

    def test_dlugie_streszczenie_nie_jest_obcinane(self):
        streszczenie = "Ustalenia: " + "kolejny szczegół ustaleń. " * 400 + "KONIEC_STRESZCZENIA"
        self.zapisz_sesje("s1", [wpis_uzytkownika(streszczenie, isCompactSummary=True)])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn("KONIEC_STRESZCZENIA", out)

    def test_sekrety_w_pliku_env_i_wynikach(self):
        env = Path(self.tmp.name) / ".env"
        env.write_text("NOTION_TOKEN=secret_abcdef1234567890\nDATABASE_URL=postgres://admin:Sup3rTajne@db:5432/x\n"
                       "STRIPE_KEY=sk_live_abcdef1234567890\npassword: hunter22222\nDEBUG=true\n", encoding="utf-8")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Write", {"file_path": str(env), "content": "x"}),
            narzedzie("t2", "Bash", {"command": "env | grep TOKEN"}),
            wynik("t2", "env: NOTION_TOKEN=secret_abcdef1234567890", blad=True),
        ])
        _, pliki = self.uruchom("--sesja", "s1", "--pliki", ".env")
        for sekret in ("secret_abcdef1234567890", "Sup3rTajne", "sk_live_abcdef1234567890", "hunter22222"):
            self.assertNotIn(sekret, pliki)
        self.assertIn("DEBUG=true", pliki)
        self.assertIn("heurystyczne", pliki)
        _, os_czasu = self.uruchom("--sesja", "s1")
        self.assertNotIn("secret_abcdef1234567890", os_czasu)

    def test_znane_formaty_sekretow(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        komendy = [
            f"curl -H 'Authorization: Bearer {jwt}' x", "curl -u admin:S3cretPass99 https://api.x",
            "curl -H 'X-API-Key: abcd1234efgh5678' x", "curl -H 'Authorization: Basic dXNlcjpwYXNzd29yZA==' x",
            "mysql -u root -pHaslo1234 baza", "export GOOGLE=AIza" + "SyA1234567890abcdefghijklmnopqrstu",
            "npm config set //r/:_authToken npm_" + "a" * 36, "git clone https://oauth2:glpat-" + "b" * 20 + "@gitlab.com/x",
        ]
        klucz = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        sciezka = Path(self.tmp.name) / "klucz.txt"
        sciezka.write_text(klucz, encoding="utf-8")
        self.zapisz_sesje("s1", [narzedzie(f"t{i}", "Bash", {"command": k}) for i, k in enumerate(komendy)]
                          + [narzedzie("w", "Write", {"file_path": str(sciezka), "content": "x"})])
        _, out = self.uruchom("--sesja", "s1")
        for sekret in (jwt, "S3cretPass99", "abcd1234efgh5678", "dXNlcjpwYXNzd29yZA", "Haslo1234",
                       "SyA1234567890", "a" * 36, "b" * 20):
            self.assertNotIn(sekret, out)
        _, pliki = self.uruchom("--sesja", "s1", "--pliki", "klucz")
        self.assertNotIn("MIIEowIBAAKCAQEA", pliki)
        self.assertIn("[SEKRET:klucz-prywatny]", pliki)

    def test_luzne_wzorce_nie_psuja_kodu(self):
        sciezka = Path(self.tmp.name) / "klient.py"
        kod = "token=get_token()\nAPI_TOKEN=os.environ['API_TOKEN']\ndef f(password: str): pass\n"
        sciezka.write_text(kod, encoding="utf-8")
        self.zapisz_sesje("s1", [narzedzie("t1", "Write", {"file_path": str(sciezka), "content": "x"})])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "klient")
        self.assertIn(kod.strip(), out)

    def test_filtr_tylko(self):
        self.zapisz_sesje("s1", [
            wpis_uzytkownika("Zrób raport"),
            tekst_asystenta("Robię."),
            narzedzie("t1", "Bash", {"command": "python3 r.py"}),
            wynik("t1", "KeyError", blad=True),
        ])
        _, out = self.uruchom("--sesja", "s1", "--tylko", "uzytkownik,bledy")
        self.assertIn(">> UŻYTKOWNIK: Zrób raport", out)
        self.assertIn("!! BŁĄD", out)
        self.assertNotIn("ASYSTENT", out)
        self.assertNotIn("- Bash:", out)
        kod, out = self.uruchom("--sesja", "s1", "--tylko", "nieznana")
        self.assertNotEqual(kod, 0)
        self.assertIn("nieznane kategorie", out)

    def test_edit_krotki_wynik_obraz_i_komenda_uzytkownika(self):
        self.zapisz_sesje("s1", [
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": "To ten błąd"}, {"type": "image", "source": {}}]}},
            wpis_uzytkownika("<bash-input>git status</bash-input>"),
            wpis_uzytkownika("<bash-stdout>On branch main</bash-stdout><bash-stderr></bash-stderr>"),
            {"type": "assistant", "cwd": str(self.projekt), "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Edit", "input": {
                    "file_path": str(self.projekt / "r.py"), "old_string": "enc='utf-8'", "new_string": "enc='cp1250'"}},
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "file dane.csv"}},
                {"type": "tool_use", "id": "t3", "name": "Agent", "input": {
                    "subagent_type": "Explore", "model": "haiku", "description": "Szukaj", "prompt": "x"}}]}},
            wynik("t2", "dane.csv: CSV text, ISO-8859 text"),
        ])
        _, out = self.uruchom("--sesja", "s1")
        self.assertIn(">> UŻYTKOWNIK: To ten błąd\n[obraz]", out)
        self.assertIn(">> UŻYTKOWNIK: $ git status", out)
        self.assertIn("= On branch main", out)
        self.assertIn("- Edit: ./r.py: enc='utf-8' -> enc='cp1250'", out)
        self.assertIn("= dane.csv: CSV text, ISO-8859 text", out)
        self.assertIn("- Agent: [Explore] Szukaj", out)

    def test_heredoc_w_pliki(self):
        self.zapisz_sesje("s1", [
            {"type": "assistant", "cwd": self.tmp.name, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {
                    "command": "mkdir -p d && cat > d/README.md <<'EOF'\n# Klient\nKroki onboardingu\nEOF"}},
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {
                    "command": "cat <<EOF > conf.txt\nuser=$USER\nEOF"}}]}},
        ])
        _, lista = self.uruchom("--sesja", "s1", "--pliki")
        self.assertIn("README.md", lista)
        self.assertIn("treść przybliżona", lista)  # conf.txt ma $USER bez cudzysłowu wokół EOF
        self.assertNotIn("zmieniany też przez Bash", lista)
        _, tresc = self.uruchom("--sesja", "s1", "--pliki", "README")
        self.assertIn("# Klient\nKroki onboardingu", tresc)

    def test_perl_pi_i_sort_o_zmieniaja_plik(self):
        sciezka = str(Path(self.tmp.name) / "a.js")
        for komenda in ("perl -pi -e 's/x/y/' a.js", "sort -o a.js a.js"):
            self.zapisz_sesje("s1", [
                narzedzie("t1", "Write", {"file_path": sciezka, "content": "x"}),
                narzedzie("t2", "Bash", {"command": komenda}),
            ])
            _, lista = self.uruchom("--sesja", "s1", "--pliki")
            self.assertIn("zmieniany też przez Bash", lista, komenda)

    def test_limit_pliku(self):
        sciezka = Path(self.tmp.name) / "duzy.json"
        sciezka.write_text("x" * 300, encoding="utf-8")
        self.zapisz_sesje("s1", [narzedzie("t1", "Write", {"file_path": str(sciezka), "content": "x"})])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "duzy", "--limit-pliku", "100")
        self.assertIn("obcięto: plik ma 300 zn.", out)
        self.assertNotIn("x" * 101, out)

    def test_edit_z_pustym_old_string(self):
        sciezka = str(Path(self.tmp.name) / "usuniety.py")
        self.zapisz_sesje("s1", [
            narzedzie("t1", "Edit", {"file_path": sciezka, "old_string": "", "new_string": "abc"}),
            narzedzie("t2", "Edit", {"file_path": sciezka, "old_string": "", "new_string": "X", "replace_all": True}),
        ])
        _, out = self.uruchom("--sesja", "s1", "--pliki", "usuniety")
        self.assertIn("abc", out)
        self.assertNotIn("XaXbXcX", out)
        self.assertIn("niektóre Edit nie dały się nałożyć", out)

    def test_nietypowy_rekord_nie_przerywa(self):
        self.zapisz_sesje("s1", [
            {"type": "assistant", "message": {"content": ["sam tekst zamiast bloku"]}},
            {"type": "user", "message": "tekst zamiast obiektu"},
            narzedzie("t1", "Bash", ["lista", "zamiast", "obiektu"]),
            wpis_uzytkownika("Prośba po dziwnych rekordach"),
        ])
        kod, out = self.uruchom("--sesja", "s1")
        self.assertEqual(kod, 0, out)
        self.assertIn("Prośba po dziwnych rekordach", out)
        self.assertIn("Pominięto", out)

    def test_lista_z_podkatalogu(self):
        self.zapisz_sesje("s1", [wpis_uzytkownika("Prośba z katalogu projektu")])
        podkatalog = self.projekt / "src" / "gleboko"
        podkatalog.mkdir(parents=True)
        kod, out = self.uruchom("--lista", "--projekt", str(podkatalog))
        self.assertEqual(kod, 0, out)
        self.assertIn("katalogu nadrzędnego", out)
        self.assertIn("Prośba z katalogu projektu", out)


if __name__ == "__main__":
    unittest.main()
