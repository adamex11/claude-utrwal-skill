#!/usr/bin/env python3
"""Zwięzła oś czasu sesji Claude Code z pliku .jsonl.

Zostawia to, z czego da się odtworzyć umiejętność: wiadomości użytkownika,
skrócony tekst asystenta, wywołania narzędzi, błędy i raporty subagentów. Pomija
myślenie modelu, pełne treści zapisywanych plików, wstrzyknięte treści skilli
i rekordy techniczne. Fragmenty wyglądające na sekrety (tokeny, klucze) maskuje.

Użycie:
  python3 wyciagnij_rozmowe.py                    # bieżąca sesja (CLAUDE_CODE_SESSION_ID)
  python3 wyciagnij_rozmowe.py --sesja ID [ID ...]
  python3 wyciagnij_rozmowe.py --lista            # sesje bieżącego projektu
  python3 wyciagnij_rozmowe.py --sesja ID --wyjscie plik.md
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
    "file-history-snapshot", "ai-title", "last-prompt", "mode", "permission-mode",
    "queue-operation", "attachment", "system", "atis-latch", "summary",
}
# Narzędzia, z których w osi czasu wystarczy ścieżka pliku (treść jest w samym pliku)
TYLKO_SCIEZKA = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Read"}
# Komendy Bash, które mogą zmienić istniejący plik (przekierowanie, edycja w miejscu, nadpisanie)
MODYFIKUJACY_BASH = re.compile(
    r">|\b(?:sed|perl|ruby)\s+(?:\S+\s+)*?-i|--(?:in-place|write|fix)\b|\bgofmt\s+-w"
    r"|\b(?:tee|mv|cp|rm|patch|truncate|dd|black|isort|prettier|rustfmt|ruff\s+format"
    r"|git\s+(?:checkout|restore|apply|stash|reset))\b")
# Przekierowania, które nie zapisują pliku (2>&1, >/dev/null) - zdejmowane przed sprawdzeniem
PRZEKIEROWANIE_BEZ_PLIKU = re.compile(r"\d*>>?\s*(?:&\d+|/dev/null)")


NAZWA_SEKRETU = r"(?:password|passwd|secret|token|api[_-]?key|access[_-]?key)"
# Fragmenty wyglądające na sekrety. Maskujemy wartość, zostawiając rodzaj, żeby było widać, co tam stało.
SEKRETY = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1[SEKRET]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "[SEKRET:sk-...]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "[SEKRET:github-token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[SEKRET:github-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[SEKRET:aws-key]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[SEKRET:slack-token]"),
    # Tylko wartości w cudzysłowie, żeby nie psuć kodu w stylu token = os.environ["X"]. Nazwa z krótką
    # listą końcówek (SECRET_KEY, client_secret, "api_key":), żeby nie łapać tokenizer, token_url, secret_name
    (re.compile(r"""(["']?\b\w*""" + NAZWA_SEKRETU + r"""(?:_?(?:key|id|value|hash|str|string)|s)?["']?\s*[=:]\s*["'])"""
                r"""(?!\[SEKRET)[^"'\s]{8,}(["'])""", re.I),
     r"\1[SEKRET]\2"),
]
# W komendach Bash i argumentach skilli sekrety bywają bez cudzysłowu: export NOTION_TOKEN=..., --token=...,
# --token wartość. Pomijamy odwołania do zmiennych ($X), wartości w cudzysłowie (łapie je wzorzec ogólny)
# i fragmenty już zamaskowane.
SEKRETY_BASH = [
    (re.compile(r"""(\b\w*""" + NAZWA_SEKRETU + r"""(?:_?(?:key|id|value|hash))?=)(?![$"'\[])[^\s"';&|]{8,}""", re.I),
     r"\1[SEKRET]"),
    (re.compile(r"""(--?""" + NAZWA_SEKRETU + r"""\s+)(?![$"'\[-])[^\s"';&|]{8,}""", re.I), r"\1[SEKRET]"),
]
zamaskowane = 0


def maskuj_komende(tekst):
    """Najpierw wzorce rozpoznające rodzaj sekretu (github-token, sk-...), potem luźniejsze z Bash."""
    return maskuj(maskuj(str(tekst)), SEKRETY_BASH)


def maskuj(tekst, wzorce=SEKRETY):
    global zamaskowane
    for wzorzec, zamiana in wzorce:
        tekst, ile = wzorzec.subn(zamiana, tekst)
        zamaskowane += ile
    return tekst


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
        tytul = szukaj(f.read().decode("utf-8", errors="replace").split("\n"))  # jak rekordy(): splitlines dzieli też na U+2028
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


def tekst_wyniku(blok):
    tresc = blok.get("content")
    if isinstance(tresc, list):
        return "\n".join(c.get("text", "") for c in tresc if isinstance(c, dict))
    return str(tresc or "")


def opis_narzedzia(nazwa, wejscie, n):
    if nazwa == "Bash":
        return f"$ {skroc(maskuj_komende(wejscie.get('command', '')), n)}"
    if nazwa in TYLKO_SCIEZKA:
        return wejscie.get("file_path") or wejscie.get("notebook_path") or ""
    if nazwa == "Skill":
        return skroc(maskuj_komende(f"{wejscie.get('skill', '')} {wejscie.get('args', '')}"), n)
    if nazwa == "Agent":
        return f"[{wejscie.get('model', '')}] {wejscie.get('description', '')}: {skroc(wejscie.get('prompt', ''), n // 2)}"
    return skroc(json.dumps(wejscie, ensure_ascii=False), n // 2)


def tekst_uzytkownika(tresc):
    """Zwraca tekst wpisany przez człowieka albo None dla treści wstrzykniętych."""
    if isinstance(tresc, list):
        tresc = "\n".join(b.get("text", "") for b in tresc if isinstance(b, dict) and b.get("type") == "text")
    if not tresc:
        return None
    # Nazwa i argumenty szukane osobno: między znacznikami bywa nowa linia i <command-message>
    nazwa = re.search(r"<command-name>(.*?)</command-name>", tresc, re.S)
    if nazwa:
        argumenty = re.search(r"<command-args>(.*?)</command-args>", tresc, re.S)
        return f"{nazwa.group(1).strip()} {argumenty.group(1).strip() if argumenty else ''}".strip()
    if tresc.lstrip().startswith(("<local-command", "<command-message", "<system-reminder", "<task-notification", "Base directory for this skill")):
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


def powiadomienie_zadania(tekst):
    """Z <task-notification> zostawia status, opis i wynik zadania w tle (jeśli są)."""
    pola = {k: re.search(f"<{k}>(.*?)</{k}>", tekst, re.S) for k in ("status", "summary", "result")}
    pola = {k: m.group(1).strip() for k, m in pola.items() if m}
    if not pola.get("summary") and not pola.get("result"):
        return None
    return pola


def os_czasu(plik, n):
    linie = []
    id_narzedzi = {}  # tool_use_id -> krótki opis, żeby błąd wskazywał komendę
    for r in rekordy(plik):
        typ = r.get("type")
        if typ in POMIJANE_TYPY or r.get("isSidechain"):
            continue
        if r.get("isCompactSummary"):
            linie.append(f"\n[STRESZCZENIE PO KOMPAKCJI]\n{skroc(tekst_uzytkownika((r.get('message') or {}).get('content')) or '', n * 4)}")
            continue
        wiadomosc = r.get("message") or {}
        tresc = wiadomosc.get("content")
        if typ == "user":
            if r.get("isMeta"):
                raport = raport_subagenta(r)
                if raport:
                    linie.append(f"\n<< RAPORT SUBAGENTA ({raport[0]}): {skroc(raport[1], n * 4)}")
                continue
            if isinstance(tresc, list):
                for b in tresc:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        wynik = tekst_wyniku(b)
                        # Odpowiedzi na pytania (AskUserQuestion) to decyzje użytkownika - zostawiamy je
                        if "User has answered" in wynik or "The user answered" in wynik:
                            linie.append(f"\n>> ODPOWIEDŹ UŻYTKOWNIKA: {skroc(wynik, n)}")
                        elif b.get("is_error"):
                            zrodlo = id_narzedzi.get(b.get("tool_use_id"), "?")
                            linie.append(f"   !! BŁĄD ({zrodlo}): {skroc(wynik, n)}")
            surowy = tresc if isinstance(tresc, str) else ""
            if surowy.lstrip().startswith("<task-notification"):
                pola = powiadomienie_zadania(surowy)
                if pola:
                    linie.append(f"   [ZADANIE W TLE: {pola.get('status', '?')}] {skroc(pola.get('summary', ''), n)}")
                    if pola.get("result"):
                        linie.append(f"   [WYNIK ZADANIA] {skroc(pola['result'], n * 2)}")
                continue
            tekst = tekst_uzytkownika(tresc)
            if tekst:
                # Wymagania użytkownika to najcenniejszy materiał - limit dużo wyższy niż dla reszty
                linie.append(f"\n>> UŻYTKOWNIK: {skroc(tekst, n * 10)}")
        elif typ == "assistant" and isinstance(tresc, list):
            for b in tresc:
                if b.get("type") == "text" and b.get("text", "").strip():
                    linie.append(f"   ASYSTENT: {skroc(b['text'], n)}")
                elif b.get("type") == "tool_use":
                    opis = opis_narzedzia(b.get("name"), b.get("input") or {}, n)
                    id_narzedzi[b.get("id")] = f"{b.get('name')} {skroc(opis, 80)}"
                    linie.append(f"   - {b.get('name')}: {opis}")
    return linie


def pliki_sesji(plik):
    """Odtwarza ostatnią treść plików zapisanych w sesji (Write + kolejne Edit).

    Zwraca {ścieżka: [treść albo None, liczba Edit, czy Edit dało się nałożyć, czy ruszał go Bash]}.
    Treść jest None, gdy plik tylko edytowano (brak pełnego Write w sesji).
    Zmian zrobionych przez Bash (sed, heredoc) nie da się odtworzyć - są tylko oznaczane.
    """
    # Pierwsze przejście: wywołania, które skończyły się błędem (np. Edit z niepasującym old_string),
    # nie zmieniły pliku, więc nie wolno ich nakładać
    nieudane = set()
    for r in rekordy(plik):
        if r.get("type") == "user" and isinstance((r.get("message") or {}).get("content"), list):
            for b in r["message"]["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    nieudane.add(b.get("tool_use_id"))
    pliki = {}
    for r in rekordy(plik):
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        for b in (r.get("message") or {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use" or b.get("id") in nieudane:
                continue
            w = b.get("input") or {}
            if b.get("name") == "Bash":
                komenda = str(w.get("command", ""))
                if not MODYFIKUJACY_BASH.search(PRZEKIEROWANIE_BEZ_PLIKU.sub("", komenda)):
                    continue  # cat, grep, python3 plik.py itp. nie zmieniają pliku
                for sc, dane in pliki.items():
                    # nazwa jako osobne słowo, a nie fragment innej (a.js w data.json)
                    if re.search(r"(?<![\w.-])" + re.escape(Path(sc).name) + r"(?![\w.-])", komenda):
                        dane[3] = True
                continue
            sciezka = w.get("file_path")
            if not sciezka:
                continue
            if b.get("name") == "Write":
                pliki[sciezka] = [w.get("content", ""), 0, True, False]
            elif b.get("name") in ("Edit", "MultiEdit"):
                tresc, edycje, ok, bash = pliki.get(sciezka, [None, 0, True, False])
                zmiany = w.get("edits") or [w]
                for z in zmiany:
                    stary, nowy = z.get("old_string", ""), z.get("new_string", "")
                    if tresc is not None and stary in tresc:
                        tresc = tresc.replace(stary, nowy) if z.get("replace_all") else tresc.replace(stary, nowy, 1)
                    else:
                        ok = False
                pliki[sciezka] = [tresc, edycje + len(zmiany), ok, bash]
    return pliki


def raport_plikow(plik, wzorce):
    pliki = pliki_sesji(plik)
    linie = []
    if not wzorce:
        linie.append("Pliki zapisane w sesji (istnieje = czy plik jest dziś na dysku):")
        for sciezka, (tresc, edycje, ok, bash) in pliki.items():
            stan = "istnieje" if Path(sciezka).exists() else "BRAK NA DYSKU"
            rozmiar = f"{len(tresc)} zn." if tresc is not None else "tylko Edit"
            uwaga = ("" if ok else ", nie wszystkie Edit dało się odtworzyć") + (", zmieniany też przez Bash" if bash else "")
            linie.append(f"  {sciezka}  [{stan}; {rozmiar}; Edit: {edycje}{uwaga}]")
        return linie
    for sciezka, (tresc, edycje, ok, bash) in pliki.items():
        if not any(w in sciezka for w in wzorce):
            continue
        if Path(sciezka).exists():
            # Plik na dysku to wersja ostateczna (obejmuje też zmiany z Bash i z późniejszych sesji)
            linie.append(f"\n===== {sciezka} [treść z dysku] =====")
            linie.append(maskuj(Path(sciezka).read_text(encoding="utf-8", errors="replace")))
            continue
        uwagi = [u for u, warunek in (("niektóre Edit nie dały się nałożyć", not ok),
                                       ("plik zmieniano też przez Bash - te zmiany nie są uwzględnione", bash)) if warunek]
        linie.append(f"\n===== {sciezka} [odtworzone z sesji, pliku nie ma na dysku; Edit: {edycje}] =====")
        if uwagi:
            linie.append("[UWAGA: " + "; ".join(uwagi) + "]")
        linie.append(maskuj(tresc) if tresc is not None else "[brak pełnej treści - plik tylko edytowano w tej sesji]")
    if not linie:
        linie.append(f"Żaden zapisany plik nie pasuje do: {' '.join(wzorce)}")
    return linie


def lista_sesji(cwd):
    foldery, dokladne = foldery_projektu(cwd)
    if not foldery:
        sys.exit(f"Brak sesji dla projektu {cwd} w {PROJEKTY}")
    wiersze = []
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
                   help="obcięcie wpisu (wiadomości użytkownika: 10x więcej); większa wartość = pełniejszy wynik")
    p.add_argument("--pliki", nargs="*", metavar="WZORZEC",
                   help="zamiast osi czasu: bez wzorca lista plików zapisanych w sesji, "
                        "z wzorcem (fragment ścieżki) pełna odtworzona treść pasujących plików")
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
                linie += raport_plikow(plik, a.pliki)
                continue
            linie += os_czasu(plik, a.max_znakow)
            if (plik.parent / s / "subagents").is_dir():
                linie.append("\n[UWAGA] Sesja ma subagentów - widać ich zlecenia i raporty końcowe, a przebieg ich pracy jest w osobnych plikach.")

    if zamaskowane:
        linie.append(f"\n[UWAGA] Zamaskowano {zamaskowane} fragm. wyglądających na sekrety ([SEKRET]). Nie przenoś ich do skilla.")
    wynik = "\n".join(linie) + "\n"
    if a.wyjscie:
        Path(a.wyjscie).write_text(wynik, encoding="utf-8")
        print(f"Zapisano {len(wynik)} znaków do {a.wyjscie}")
    else:
        sys.stdout.write(wynik)


if __name__ == "__main__":
    main()
