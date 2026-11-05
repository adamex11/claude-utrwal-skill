#!/usr/bin/env python3
"""Zwięzła oś czasu sesji Claude Code z pliku .jsonl.

Zostawia to, z czego da się odtworzyć umiejętność: wiadomości i decyzje użytkownika,
skrócony tekst asystenta, wywołania narzędzi, krótkie wyniki, błędy, raporty subagentów
i streszczenia po kompakcji. Pomija myślenie modelu, pełne treści zapisywanych plików,
wstrzyknięte treści skilli i rekordy techniczne. Fragmenty wyglądające na sekrety
(tokeny, klucze, hasła) maskuje - heurystycznie, więc nie wszystkie.

Użycie:
  python3 wyciagnij_rozmowe.py                    # bieżąca sesja (CLAUDE_CODE_SESSION_ID)
  python3 wyciagnij_rozmowe.py --sesja ID [ID ...]
  python3 wyciagnij_rozmowe.py --lista            # sesje bieżącego projektu
  python3 wyciagnij_rozmowe.py --sesja ID --wyjscie plik.md
  python3 wyciagnij_rozmowe.py --sesja ID --tylko uzytkownik,decyzje,bledy,kompakcja   # mapa dużej sesji
  python3 wyciagnij_rozmowe.py --sesja ID --pliki            # pliki zapisane w sesji
  python3 wyciagnij_rozmowe.py --sesja ID --pliki build.js   # ich pełna treść
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

# Claude Code trzyma zapisy sesji w <katalog konfiguracji>/projects (domyślnie ~/.claude)
PROJEKTY = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser() / "projects"
# Rekordy bez treści rozmowy
POMIJANE_TYPY = {
    "file-history-snapshot", "file-history-delta", "ai-title", "last-prompt", "mode", "permission-mode",
    "queue-operation", "attachment", "system", "atis-latch", "summary", "agent-name", "cost-state",
    "frame-link", "continued-in",
}
POMIJANE_PREFIKSY = ("artifact-",)
# Rodzaje wpisów osi czasu (filtr --tylko)
KATEGORIE = ("uzytkownik", "decyzje", "bledy", "raporty", "kompakcja", "asystent", "narzedzia")
# Narzędzia, z których w osi czasu wystarczy ścieżka pliku (treść jest w samym pliku)
TYLKO_SCIEZKA = {"Write", "MultiEdit", "NotebookEdit", "Read"}
# Streszczenie po kompakcji to jedyny ślad pracy sprzed kompakcji - praktycznie bez obcinania
LIMIT_STRESZCZENIA = 30000
# Udane wyniki narzędzi do tej długości są pokazywane (wersje, liczniki, wynik `file`); dłuższe to zwykle listingi
LIMIT_KROTKIEGO_WYNIKU = 200
# Komendy Bash, które mogą zmienić istniejący plik (przekierowanie, edycja w miejscu, nadpisanie)
MODYFIKUJACY_BASH = re.compile(
    r">|\b(?:sed|perl|ruby)\s+(?:\S+\s+)*?-\w*i|--(?:in-place|write|fix)\b|\bgofmt\s+-w|\bsort\b.*\s-o\s"
    r"|\b(?:tee|mv|cp|rm|patch|truncate|dd|black|isort|prettier|rustfmt|ruff\s+format"
    r"|git\s+(?:checkout|restore|apply|stash|reset))\b")
# Przekierowania, które nie zapisują pliku (2>&1, >/dev/null) - zdejmowane przed sprawdzeniem
PRZEKIEROWANIE_BEZ_PLIKU = re.compile(r"\d*>>?\s*(?:&\d+|/dev/null)")
# Plik tworzony heredociem: cat > plik <<'EOF' ... EOF (także cat <<EOF > plik i tee plik <<EOF)
HEREDOC = re.compile(r"""(?:^|(?<=[;&|(]))[ \t]*(?:cat|tee)\b[^\n]*?<<-?[ \t]*(['"]?)(\w+)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*$""", re.S | re.M)
# Pliki konfiguracyjne: sekrety bywają w nich bez cudzysłowu (NOTION_TOKEN=..., password: ...)
KONFIGI = {".env", ".ini", ".cfg", ".conf", ".yml", ".yaml", ".toml", ".properties", ".sh", ".bash", ".zsh", ".txt"}


NAZWA_SEKRETU = r"(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)"
KONCOWKA_NAZWY = r"(?:_?(?:key|id|value|hash|base))?"
# Wartości, które nie są sekretem, tylko odwołaniem do niego
ODWOLANIE = r"""(?![$"'\[{]|os\.environ|process\.env|getenv)"""
# Fragmenty wyglądające na sekrety, stosowane wszędzie. Maskujemy wartość, zostawiając rodzaj.
SEKRETY = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S),
     "[SEKRET:klucz-prywatny]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[SEKRET:jwt]"),
    (re.compile(r"((?:Bearer|Basic)\s+)(?!\[SEKRET)[A-Za-z0-9._~+/=-]{8,}"), r"\1[SEKRET]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "[SEKRET:sk-...]"),
    (re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{10,}"), "[SEKRET:stripe]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[SEKRET:github-token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[SEKRET:github-token]"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}"), "[SEKRET:gitlab-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[SEKRET:aws-key]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "[SEKRET:google-key]"),
    (re.compile(r"\bnpm_[A-Za-z0-9]{30,}"), "[SEKRET:npm-token]"),
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "[SEKRET:huggingface-token]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[SEKRET:slack-token]"),
    # Hasło w adresie: postgres://user:haslo@host
    (re.compile(r"(://[^/\s:@\"']+:)(?![$\[])[^/\s@\"']{3,}(@)"), r"\1[SEKRET]\2"),
    # Tylko wartości w cudzysłowie, żeby nie psuć kodu w stylu token = os.environ["X"]. Nazwa z krótką
    # listą końcówek (SECRET_KEY, client_secret, "api_key":), żeby nie łapać tokenizer, token_url, secret_name
    (re.compile(r"""(["']?\b\w*""" + NAZWA_SEKRETU + r"""(?:_?(?:key|id|value|hash|base|str|string)|s)?["']?\s*[=:]\s*["'])"""
                r"""(?!\[SEKRET)[^"'\s]{8,}(["'])""", re.I),
     r"\1[SEKRET]\2"),
]
# Luźniejsze wzorce dla komend, tekstu rozmowy i plików konfiguracyjnych (w kodzie dawałyby fałszywe trafienia):
# export NOTION_TOKEN=..., --token=..., --token wartość, -u user:haslo, -pHaslo, X-API-Key: ..., password: ...
SEKRETY_LUZNE = [
    (re.compile(r"""(\b\w*""" + NAZWA_SEKRETU + KONCOWKA_NAZWY + r"""=)""" + ODWOLANIE + r"""[^\s"';&|]{8,}""", re.I),
     r"\1[SEKRET]"),
    (re.compile(r"""(--?""" + NAZWA_SEKRETU + r"""\s+)(?![$"'\[-])[^\s"';&|]{8,}""", re.I), r"\1[SEKRET]"),
    (re.compile(r"""((?:^|\s)(?:-u|--user)\s+[^\s:'"]+:)(?![$\[])[^\s'"]+"""), r"\1[SEKRET]"),
    (re.compile(r"""(\bmysql\b[^\n|;&]*?\s-p)(?![$\[])[^\s'"]{4,}"""), r"\1[SEKRET]"),
    (re.compile(r"""(\bx-api-key:\s*)(?!\[SEKRET)[^\s"']{8,}""", re.I), r"\1[SEKRET]"),
    (re.compile(r"""^(\s*[\w.-]*""" + NAZWA_SEKRETU + KONCOWKA_NAZWY + r"""\s*:\s+)""" + ODWOLANIE + r"""[^\s#"']{8,}""",
                re.I | re.M), r"\1[SEKRET]"),
]
zamaskowane = 0


def maskuj(tekst, luzne=True):
    """Najpierw wzorce rozpoznające rodzaj sekretu (github-token, sk-...), potem luźniejsze.

    Wzorce pomijają fragmenty już zamaskowane, więc ponowne maskowanie nie liczy sekretu drugi raz.
    """
    global zamaskowane
    tekst = str(tekst)
    for wzorzec, zamiana in SEKRETY + (SEKRETY_LUZNE if luzne else []):
        tekst, ile = wzorzec.subn(zamiana, tekst)
        zamaskowane += ile
    return tekst


def uwaga_o_sekretach():
    return (f"\n[UWAGA] Zamaskowano {zamaskowane} fragm. wyglądających na sekrety ([SEKRET]). Maskowanie jest "
            "heurystyczne: nie łapie sekretów wpisanych zwykłym tekstem ani nietypowych formatów. Nie przenoś do "
            "skilla ani [SEKRET], ani niczego, co wygląda na hasło, token lub klucz.")


def rekordy(plik):
    """Rekordy JSONL po kolei; uszkodzone linie i niepoprawne znaki są pomijane, a nie przerywają pracy."""
    with plik.open(encoding="utf-8", errors="replace") as f:
        for surowa in f:
            try:
                r = json.loads(surowa)
            except json.JSONDecodeError:
                continue
            if isinstance(r, dict):
                yield r


def ostatni_tytul(plik, koncowka=256 * 1024):
    """Najnowszy ai-title. Claude Code dopisuje go co kilkadziesiąt rekordów, więc zwykle wystarcza końcówka pliku."""
    def szukaj(linie):
        tytul = ""
        for surowa in linie:
            if '"ai-title"' not in surowa:  # tani filtr przed parsowaniem JSON
                continue
            try:
                r = json.loads(surowa)
            except json.JSONDecodeError:
                continue
            if isinstance(r, dict) and r.get("type") == "ai-title":
                tytul = r.get("aiTitle", "") or tytul
        return tytul

    with plik.open("rb") as f:
        rozmiar = f.seek(0, os.SEEK_END)
        f.seek(max(0, rozmiar - koncowka))
        # Dzielimy tylko na \n, tak jak rekordy() czyta plik; splitlines() dzieliłoby też na U+2028 wewnątrz JSON
        tytul = szukaj(f.read().decode("utf-8", errors="replace").split("\n"))
    if tytul or rozmiar <= koncowka:
        return tytul
    with plik.open(encoding="utf-8", errors="replace") as f:
        return szukaj(f)


def pierwsza_wiadomosc(plik):
    for r in rekordy(plik):
        if r.get("type") == "user" and not r.get("isMeta"):
            tekst = tekst_uzytkownika((r.get("message") or {}).get("content"))
            if tekst:
                return tekst
    return ""


def koduj(sciezka):
    """Claude Code koduje ścieżkę projektu, zamieniając każdy znak spoza [A-Za-z0-9] na '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(sciezka))


def foldery_projektu(cwd):
    """Folder sesji projektu oraz foldery z czasów, gdy projekt leżał gdzie indziej.

    Po przeniesieniu projektu stare sesje zostają pod starą zakodowaną ścieżką.
    Dopasowujemy więc też foldery kończące się tymi samymi 3 ostatnimi członami ścieżki.
    """
    # Ścieżka może być zapisana przed albo po rozwinięciu dowiązań (np. /var -> /private/var na macOS)
    dokladne = {PROJEKTY / koduj(cwd), PROJEKTY / koduj(Path(cwd).resolve())}
    koncowka = "-" + koduj(Path(*Path(cwd).parts[-3:]))
    if not PROJEKTY.is_dir():
        return [], dokladne
    foldery = [f for f in PROJEKTY.iterdir() if f.is_dir() and (f in dokladne or f.name.endswith(koncowka))]
    return sorted(foldery, key=lambda f: f not in dokladne), dokladne


def znajdz_plik(sesja):
    kandydaci = list(PROJEKTY.glob(f"*/{sesja}.jsonl"))
    if not kandydaci:
        sys.exit(f"Nie znaleziono pliku sesji {sesja}.jsonl w {PROJEKTY}")
    return kandydaci[0]


def skroc(tekst, n):
    tekst = maskuj(str(tekst).strip())
    return tekst if len(tekst) <= n else tekst[:n] + f" [...+{len(tekst) - n} zn.]"


def jedna_linia(tekst, n):
    return skroc(str(tekst).replace("\n", "⏎"), n)


def wzgledna(sciezka, cwd):
    """Ścieżka względem katalogu sesji, gdy w nim leży (krócej i czytelniej)."""
    if not sciezka or not cwd:
        return sciezka or ""
    try:
        return "./" + Path(sciezka).relative_to(cwd).as_posix()
    except ValueError:
        return sciezka


def tekst_wyniku(blok):
    tresc = blok.get("content")
    if isinstance(tresc, list):
        return "\n".join(c.get("text", "") for c in tresc if isinstance(c, dict))
    return str(tresc or "")


def opis_narzedzia(nazwa, wejscie, n, cwd):
    if nazwa == "Bash":
        return f"$ {skroc(wejscie.get('command', ''), n)}"
    if nazwa == "Edit":
        # Poprawka po błędzie to często właśnie lekcja, więc pokazujemy, co zmieniono
        return (f"{wzgledna(wejscie.get('file_path'), cwd)}: {jedna_linia(wejscie.get('old_string', ''), 80)}"
                f" -> {jedna_linia(wejscie.get('new_string', ''), 80)}")
    if nazwa in TYLKO_SCIEZKA:
        sciezka = wzgledna(wejscie.get("file_path") or wejscie.get("notebook_path"), cwd)
        return f"{sciezka} ({len(wejscie['edits'])} zmian)" if isinstance(wejscie.get("edits"), list) else sciezka
    if nazwa == "Skill":
        return skroc(f"{wejscie.get('skill', '')} {wejscie.get('args', '')}", n)
    if nazwa in ("Agent", "Task"):
        rodzaj = wejscie.get("subagent_type") or wejscie.get("model") or ""
        return f"[{rodzaj}] {wejscie.get('description', '')}: {skroc(wejscie.get('prompt', ''), n // 2)}"
    if nazwa == "AskUserQuestion":
        pytania = [p.get("question", "") for p in wejscie.get("questions") or [] if isinstance(p, dict)]
        return skroc(" | ".join(pytania), n)
    return skroc(json.dumps(wejscie, ensure_ascii=False), n // 2)


def odpowiedzi_na_pytania(r, wynik):
    """Decyzje użytkownika z AskUserQuestion. Najpewniej z toolUseResult.answers ({pytanie: odpowiedź})."""
    dane = r.get("toolUseResult")
    if isinstance(dane, dict) and isinstance(dane.get("answers"), dict) and dane["answers"]:
        notatki = dane.get("annotations") if isinstance(dane.get("annotations"), dict) else {}
        czesci = []
        for pytanie, odpowiedz in dane["answers"].items():
            notatka = notatki.get(pytanie, {}).get("notes") if isinstance(notatki.get(pytanie), dict) else None
            czesci.append(f'"{pytanie}" -> {odpowiedz}' + (f" (notatka: {notatka})" if notatka else ""))
        return "; ".join(czesci)
    # Starsze i obecne brzmienie tekstu wyniku
    if any(f in wynik for f in ("Your questions have been answered", "User has answered", "The user answered")):
        return wynik
    return None


def tekst_uzytkownika(tresc):
    """Zwraca tekst wpisany przez człowieka albo None dla treści wstrzykniętych."""
    if isinstance(tresc, list):
        bloki = [b for b in tresc if isinstance(b, dict)]
        teksty = [b.get("text", "") for b in bloki if b.get("type") == "text"]
        obrazy = sum(1 for b in bloki if b.get("type") == "image")
        tresc = "\n".join(teksty + ["[obraz]"] * obrazy)
    if not tresc:
        return None
    # Nazwa i argumenty szukane osobno: między znacznikami bywa nowa linia i <command-message>
    nazwa = re.search(r"<command-name>(.*?)</command-name>", tresc, re.S)
    if nazwa:
        argumenty = re.search(r"<command-args>(.*?)</command-args>", tresc, re.S)
        return f"{nazwa.group(1).strip()} {argumenty.group(1).strip() if argumenty else ''}".strip()
    if tresc.lstrip().startswith(("<local-command", "<command-message", "<system-reminder", "<task-notification",
                                  "<bash-", "Base directory for this skill")):
        return None
    return tresc


def raport_subagenta(r):
    """Raport subagenta: rekord isMeta z origin.kind == "peer". Zwraca (nazwa, treść) albo None."""
    origin = r.get("origin") or {}
    if origin.get("kind") != "peer" or not origin.get("body"):
        return None
    tresc = origin["body"]
    # Zdejmujemy ramkę harnessu ("... The report follows:") i wcięcie, które dodaje każdej linii raportu
    znacznik = "The report follows:"
    if znacznik in tresc:
        tresc = tresc.split(znacznik, 1)[1]
    tresc = "\n".join(linia[2:] if linia.startswith("  ") else linia for linia in tresc.splitlines())
    return origin.get("name") or "subagent", tresc


def znacznik(nazwa, tekst):
    m = re.search(f"<{nazwa}>(.*?)</{nazwa}>", tekst, re.S)
    return m.group(1).strip() if m else ""


def powiadomienie_zadania(tekst):
    """Z <task-notification> zostawia status, opis i wynik zadania w tle (jeśli są)."""
    pola = {k: znacznik(k, tekst) for k in ("status", "summary", "result")}
    pola = {k: v for k, v in pola.items() if v}
    if not pola.get("summary") and not pola.get("result"):
        return None
    return pola


def os_czasu(plik, n):
    """Lista (kategoria, linia). Rekord o nietypowym kształcie jest pomijany i liczony, a nie przerywa pracy."""
    linie = []
    narzedzia = {}  # tool_use_id -> (nazwa, krótki opis), żeby wynik i błąd wskazywały komendę
    pominiete = 0

    def dodaj(kategoria, tekst):
        linie.append((kategoria, tekst))

    def rekord(r):
        typ = r.get("type")
        if typ in POMIJANE_TYPY or str(typ).startswith(POMIJANE_PREFIKSY) or r.get("isSidechain"):
            return
        wiadomosc = r.get("message") or {}
        tresc = wiadomosc.get("content")
        if r.get("isCompactSummary"):
            dodaj("kompakcja", f"\n[STRESZCZENIE PO KOMPAKCJI]\n{skroc(tekst_uzytkownika(tresc) or '', LIMIT_STRESZCZENIA)}")
            return
        if typ == "user":
            if r.get("isMeta"):
                raport = raport_subagenta(r)
                if raport:
                    dodaj("raporty", f"\n<< RAPORT SUBAGENTA ({raport[0]}): {skroc(raport[1], n * 4)}")
                return
            if isinstance(tresc, list):
                for b in tresc:
                    if not isinstance(b, dict) or b.get("type") != "tool_result":
                        continue
                    wynik = tekst_wyniku(b)
                    nazwa, zrodlo = narzedzia.get(b.get("tool_use_id"), ("?", "?"))
                    # Odpowiedzi na pytania (AskUserQuestion) to decyzje użytkownika, czyli parametry skilla
                    odpowiedz = odpowiedzi_na_pytania(r, wynik) if nazwa in ("AskUserQuestion", "?") else None
                    if odpowiedz:
                        dodaj("decyzje", f"\n>> ODPOWIEDŹ UŻYTKOWNIKA: {skroc(odpowiedz, n * 10)}")
                    elif b.get("is_error"):
                        dodaj("bledy", f"   !! BŁĄD ({zrodlo}): {skroc(wynik, n)}")
                    elif nazwa == "Bash" and 0 < len(wynik.strip()) <= LIMIT_KROTKIEGO_WYNIKU:
                        dodaj("narzedzia", f"     = {jedna_linia(wynik, LIMIT_KROTKIEGO_WYNIKU)}")
            surowy = tresc if isinstance(tresc, str) else ""
            if surowy.lstrip().startswith("<task-notification"):
                pola = powiadomienie_zadania(surowy)
                if pola:
                    dodaj("raporty", f"   [ZADANIE W TLE: {pola.get('status', '?')}] {skroc(pola.get('summary', ''), n)}")
                    if pola.get("result"):
                        dodaj("raporty", f"   [WYNIK ZADANIA] {skroc(pola['result'], n * 2)}")
                return
            # Komenda wpisana przez użytkownika z prefiksem ! i jej wynik
            if surowy.lstrip().startswith("<bash-input>"):
                dodaj("uzytkownik", f"\n>> UŻYTKOWNIK: $ {skroc(znacznik('bash-input', surowy), n)}")
                return
            if surowy.lstrip().startswith("<bash-stdout>"):
                wynik = "\n".join(filter(None, (znacznik("bash-stdout", surowy), znacznik("bash-stderr", surowy))))
                if wynik:
                    dodaj("narzedzia", f"     = {skroc(wynik, n)}")
                return
            tekst = tekst_uzytkownika(tresc)
            if tekst:
                # Wymagania użytkownika to najcenniejszy materiał - limit dużo wyższy niż dla reszty
                dodaj("uzytkownik", f"\n>> UŻYTKOWNIK: {skroc(tekst, n * 10)}")
        elif typ == "assistant" and isinstance(tresc, list):
            for b in tresc:
                if b.get("type") == "text" and b.get("text", "").strip():
                    dodaj("asystent", f"   ASYSTENT: {skroc(b['text'], n)}")
                elif b.get("type") == "tool_use":
                    opis = opis_narzedzia(b.get("name"), b.get("input") or {}, n, r.get("cwd"))
                    narzedzia[b.get("id")] = (b.get("name"), f"{b.get('name')} {jedna_linia(opis, 40)}")
                    dodaj("narzedzia", f"   - {b.get('name')}: {opis}")

    for r in rekordy(plik):
        try:
            rekord(r)
        except (AttributeError, TypeError, KeyError, ValueError):
            pominiete += 1
    if pominiete:
        dodaj("bledy", f"\n[UWAGA] Pominięto {pominiete} rekordów o nietypowym kształcie.")
    return linie


def heredoki(komenda, cwd):
    """Pliki zapisane heredociem w komendzie: [(ścieżka, treść, czy przybliżona)]. Dopisywanie (>>, tee -a) pomijamy."""
    wynik = []
    for m in HEREDOC.finditer(komenda):
        pierwsza = m.group(0).lstrip().split("\n", 1)[0]
        if re.search(r"(?<!\d)>>|\btee\s+-\w*a", pierwsza):
            continue
        cel = (re.search(r"(?<![<>\d&])>\s*([^\s;&|<>]+)", pierwsza)
               or re.search(r"\btee\s+([^\s;&|<>-][^\s;&|<>]*)", pierwsza))
        if not cel:
            continue
        sciezka = cel.group(1).strip("'\"")
        if cwd and not Path(sciezka).is_absolute():
            sciezka = str(Path(cwd) / sciezka)
        # Bez cudzysłowu wokół ogranicznika powłoka podstawia $ZMIENNE i `komendy`, więc treść w pliku może być inna
        przyblizona = not m.group(1) and bool(re.search(r"[$`]", m.group(3)))
        wynik.append((sciezka, m.group(3) + "\n", przyblizona))
    return wynik


def pliki_sesji(plik):
    """Odtwarza ostatnią treść plików zapisanych w sesji (Write, heredoc, kolejne Edit).

    Zwraca {ścieżka: {"tresc": str albo None, "edycje": int, "ok": czy Edit dało się nałożyć,
    "bash": czy zmieniał go Bash, "przyblizona": czy treść z heredoca mogła zależeć od zmiennych}}.
    Treść jest None, gdy plik tylko edytowano (brak pełnego zapisu w sesji).
    Zmian zrobionych przez Bash (sed, przekierowanie) nie da się odtworzyć - są tylko oznaczane.
    """
    # Pierwsze przejście: wywołania, które skończyły się błędem (np. Edit z niepasującym old_string),
    # nie zmieniły pliku, więc nie wolno ich nakładać
    nieudane = set()
    for r in rekordy(plik):
        tresc = (r.get("message") or {}).get("content") if isinstance(r.get("message"), dict) else None
        if r.get("type") == "user" and isinstance(tresc, list):
            for b in tresc:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    nieudane.add(b.get("tool_use_id"))
    pliki = {}

    def nowy(tresc, przyblizona=False):
        return {"tresc": tresc, "edycje": 0, "ok": True, "bash": False, "przyblizona": przyblizona}

    def blok(b, cwd):
        w = b.get("input") or {}
        if b.get("name") == "Bash":
            komenda = str(w.get("command", ""))
            zapisane = heredoki(komenda, cwd)
            cele = {sciezka for sciezka, _, _ in zapisane}
            if MODYFIKUJACY_BASH.search(PRZEKIEROWANIE_BEZ_PLIKU.sub("", HEREDOC.sub("", komenda))):
                for sc, dane in pliki.items():
                    # nazwa jako osobne słowo, a nie fragment innej (a.js w data.json)
                    if sc not in cele and re.search(r"(?<![\w.-])" + re.escape(Path(sc).name) + r"(?![\w.-])", komenda):
                        dane["bash"] = True
            for sciezka, tresc, przyblizona in zapisane:
                pliki[sciezka] = nowy(tresc, przyblizona)
            return
        sciezka = w.get("file_path")
        if not sciezka:
            return
        if b.get("name") == "Write":
            pliki[sciezka] = nowy(w.get("content", ""))
        elif b.get("name") in ("Edit", "MultiEdit"):
            dane = pliki.setdefault(sciezka, nowy(None))
            zmiany = w.get("edits") or [w]
            for z in zmiany:
                stary, nowa = z.get("old_string", ""), z.get("new_string", "")
                if not stary and dane["tresc"] is None:
                    dane["tresc"] = nowa  # Edit z pustym old_string tworzy plik
                elif stary and dane["tresc"] is not None and stary in dane["tresc"]:
                    dane["tresc"] = (dane["tresc"].replace(stary, nowa) if z.get("replace_all")
                                     else dane["tresc"].replace(stary, nowa, 1))
                else:
                    dane["ok"] = False
            dane["edycje"] += len(zmiany)

    for r in rekordy(plik):
        if r.get("type") != "assistant" or r.get("isSidechain") or not isinstance(r.get("message"), dict):
            continue
        for b in r["message"].get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use" or b.get("id") in nieudane:
                continue
            try:
                blok(b, r.get("cwd"))
            except (AttributeError, TypeError, KeyError, ValueError):
                continue
    return pliki


def uwagi_o_pliku(dane):
    uwagi = []
    if dane["tresc"] is None:
        uwagi.append("tylko Edit, brak pełnej treści")
    elif not dane["ok"]:
        uwagi.append("niektóre Edit nie dały się nałożyć")
    if dane["przyblizona"]:
        uwagi.append("z heredoca ze zmiennymi powłoki - treść przybliżona")
    if dane["bash"]:
        uwagi.append("zmieniany też przez Bash - te zmiany nie są uwzględnione")
    return uwagi


def raport_plikow(plik, wzorce, limit):
    pliki = pliki_sesji(plik)
    linie = []
    if not wzorce:
        linie.append("Pliki zapisane w sesji (istnieje = czy plik jest dziś na dysku):")
        for sciezka, dane in pliki.items():
            stan = "istnieje" if Path(sciezka).exists() else "BRAK NA DYSKU"
            rozmiar = f"{len(dane['tresc'])} zn." if dane["tresc"] is not None else "?"
            uwagi = "".join(f"; {u}" for u in uwagi_o_pliku(dane))
            linie.append(f"  {sciezka}  [{stan}; {rozmiar}; Edit: {dane['edycje']}{uwagi}]")
        return linie
    pasujace = {s: d for s, d in pliki.items() if any(w in s for w in wzorce)}
    if len(pasujace) > 5:
        linie.append(f"[UWAGA] Wzorzec pasuje do {len(pasujace)} plików. Zawęź go, jeśli potrzebujesz tylko części.")
    for sciezka, dane in pasujace.items():
        # Sekrety w plikach konfiguracyjnych bywają bez cudzysłowu; w kodzie luźne wzorce psułyby zwykłe linie
        konfig = Path(sciezka).suffix.lower() in KONFIGI or Path(sciezka).name.lower().startswith(".env")
        if Path(sciezka).exists():
            # Plik na dysku to wersja ostateczna (obejmuje też zmiany z Bash i z późniejszych sesji)
            linie.append(f"\n===== {sciezka} [treść z dysku] =====")
            tresc = Path(sciezka).read_text(encoding="utf-8", errors="replace")
        else:
            linie.append(f"\n===== {sciezka} [odtworzone z sesji, pliku nie ma na dysku; Edit: {dane['edycje']}] =====")
            uwagi = [u for u in uwagi_o_pliku(dane) if not u.startswith("tylko Edit")]
            if uwagi:
                linie.append("[UWAGA: " + "; ".join(uwagi) + "]")
            tresc = dane["tresc"]
            if tresc is None:
                linie.append("[brak pełnej treści - plik tylko edytowano w tej sesji]")
                continue
        if limit and len(tresc) > limit:
            linie.append(maskuj(tresc[:limit], luzne=konfig))
            linie.append(f"[...obcięto: plik ma {len(tresc)} zn. Całość: --limit-pliku 0"
                         + (f" albo przeczytaj {sciezka}]" if Path(sciezka).exists() else "]"))
        else:
            linie.append(maskuj(tresc, luzne=konfig))
    if not linie:
        linie.append(f"Żaden zapisany plik nie pasuje do: {' '.join(wzorce)}")
    return linie


def lista_sesji(cwd):
    # Gdy w katalogu nie ma sesji (np. po cd do podkatalogu), szukamy w katalogach nadrzędnych
    for katalog in [cwd, *cwd.parents][:-1]:
        foldery, dokladne = foldery_projektu(katalog)
        if foldery:
            break
    else:
        sys.exit(f"Brak sesji dla projektu {cwd} ani katalogów nadrzędnych w {PROJEKTY}")
    wiersze = []
    if katalog != cwd:
        wiersze.append(f"Brak sesji dla {cwd} - pokazuję sesje katalogu nadrzędnego {katalog}:")
    if any(f not in dokladne for f in foldery):
        wiersze.append("Sesje z kilku lokalizacji projektu (projekt był przenoszony):")
        wiersze += [f"  {f.name}" for f in foldery]
    pliki = [p for f in foldery for p in f.glob("*.jsonl")]
    for plik in sorted(pliki, key=lambda p: p.stat().st_mtime):
        # Nie czytamy całych plików: tytuł z końcówki, pierwsza wiadomość z początku
        tytul, pierwsza = ostatni_tytul(plik), pierwsza_wiadomosc(plik)
        czas = datetime.datetime.fromtimestamp(plik.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        rozmiar = plik.stat().st_size // 1024
        wiersze.append(f"{plik.stem}  {czas}  {rozmiar:>6} KB  {tytul or '-'}  | {skroc(pierwsza, 70)}")
    return wiersze


def kategorie(tekst):
    wybrane = {k.strip() for k in tekst.split(",") if k.strip()}
    nieznane = wybrane - set(KATEGORIE)
    if nieznane:
        raise argparse.ArgumentTypeError(f"nieznane kategorie: {', '.join(sorted(nieznane))}; dostępne: {', '.join(KATEGORIE)}")
    return wybrane


def main():
    # Windows domyślnie wypisuje w kodowaniu konsoli, a oś czasu ma polskie znaki
    for strumien in (sys.stdout, sys.stderr):
        if hasattr(strumien, "reconfigure"):
            strumien.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sesja", nargs="+", help="id sesji (domyślnie CLAUDE_CODE_SESSION_ID)")
    p.add_argument("--lista", action="store_true", help="lista sesji projektu z bieżącego katalogu")
    p.add_argument("--projekt", default=os.getcwd(), help="katalog projektu dla --lista")
    p.add_argument("--max-znakow", type=int, default=300,
                   help="obcięcie wpisu (wiadomości i decyzje użytkownika: 10x więcej, raporty subagentów: 4x; streszczenie "
                        "po kompakcji nie jest obcinane); większa wartość = pełniejszy wynik")
    p.add_argument("--tylko", type=kategorie, metavar="KATEGORIE",
                   help=f"tylko wybrane rodzaje wpisów, po przecinku: {','.join(KATEGORIE)}")
    p.add_argument("--pliki", nargs="*", metavar="WZORZEC",
                   help="zamiast osi czasu: bez wzorca lista plików zapisanych w sesji, "
                        "z wzorcem (fragment ścieżki) pełna odtworzona treść pasujących plików")
    p.add_argument("--limit-pliku", type=int, default=200000, help="obcięcie treści pliku w --pliki (0 = bez limitu)")
    p.add_argument("--wyjscie", help="zapis do pliku zamiast na ekran")
    a = p.parse_args()

    if a.lista:
        linie = lista_sesji(Path(a.projekt).absolute())
    else:
        sesje = a.sesja or [os.environ.get("CLAUDE_CODE_SESSION_ID")]
        if not sesje[0]:
            sys.exit("Podaj --sesja ID (brak zmiennej CLAUDE_CODE_SESSION_ID).")
        linie = []
        for s in sesje:
            plik = znajdz_plik(s)
            linie.append(f"# Sesja {s} ({plik.stat().st_size // 1024} KB)")
            if a.pliki is not None:
                linie += raport_plikow(plik, a.pliki, a.limit_pliku)
                continue
            linie += [tekst for kategoria, tekst in os_czasu(plik, a.max_znakow) if not a.tylko or kategoria in a.tylko]
            if (plik.parent / s / "subagents").is_dir():
                linie.append("\n[UWAGA] Sesja ma subagentów - widać ich zlecenia i raporty końcowe, a przebieg ich pracy jest w osobnych plikach.")
        linie.append(uwaga_o_sekretach())

    wynik = "\n".join(linie) + "\n"
    if a.wyjscie:
        Path(a.wyjscie).write_text(wynik, encoding="utf-8")
        print(f"Zapisano {len(wynik)} znaków do {a.wyjscie}")
    else:
        sys.stdout.write(wynik)


if __name__ == "__main__":
    main()
