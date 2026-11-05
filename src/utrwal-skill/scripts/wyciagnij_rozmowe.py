#!/usr/bin/env python3
"""Zwięzła oś czasu sesji Claude Code z pliku .jsonl.

Zostawia to, z czego da się odtworzyć umiejętność: wiadomości użytkownika,
skrócony tekst asystenta, wywołania narzędzi i błędy. Pomija myślenie modelu,
pełne treści zapisywanych plików, wstrzyknięte treści skilli i rekordy techniczne.

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
PROJEKTY = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
# Rekordy bez treści rozmowy
POMIJANE_TYPY = {
    "file-history-snapshot", "ai-title", "last-prompt", "mode", "permission-mode",
    "queue-operation", "attachment", "system", "atis-latch", "summary",
}
# Narzędzia, z których wystarczy ścieżka pliku (treść jest w samym pliku)
TYLKO_SCIEZKA = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Read"}


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
    tekst = str(tekst).strip()
    return tekst if len(tekst) <= n else tekst[:n] + f" [...+{len(tekst) - n} zn.]"


def tekst_wyniku(blok):
    tresc = blok.get("content")
    if isinstance(tresc, list):
        return "\n".join(c.get("text", "") for c in tresc if isinstance(c, dict))
    return str(tresc or "")


def opis_narzedzia(nazwa, wejscie, n):
    if nazwa == "Bash":
        return f"$ {skroc(wejscie.get('command', ''), n)}"
    if nazwa in TYLKO_SCIEZKA:
        return wejscie.get("file_path") or wejscie.get("notebook_path") or ""
    if nazwa == "Skill":
        return f"{wejscie.get('skill', '')} {wejscie.get('args', '')}".strip()
    if nazwa == "Agent":
        return f"[{wejscie.get('model', '')}] {wejscie.get('description', '')}: {skroc(wejscie.get('prompt', ''), n // 2)}"
    return skroc(json.dumps(wejscie, ensure_ascii=False), n // 2)


def tekst_uzytkownika(tresc):
    """Zwraca tekst wpisany przez człowieka albo None dla treści wstrzykniętych."""
    if isinstance(tresc, list):
        tresc = "\n".join(b.get("text", "") for b in tresc if isinstance(b, dict) and b.get("type") == "text")
    if not tresc:
        return None
    polecenie = re.search(r"<command-name>(.*?)</command-name>.*?(?:<command-args>(.*?)</command-args>)?", tresc, re.S)
    if polecenie:
        return f"{polecenie.group(1)} {polecenie.group(2) or ''}".strip()
    if tresc.lstrip().startswith(("<local-command", "<command-message", "<system-reminder", "<task-notification", "Base directory for this skill")):
        return None
    return tresc


def os_czasu(plik, n):
    linie = []
    id_narzedzi = {}  # tool_use_id -> krótki opis, żeby błąd wskazywał komendę
    for surowa in plik.open(encoding="utf-8"):
        try:
            r = json.loads(surowa)
        except json.JSONDecodeError:
            continue
        typ = r.get("type")
        if typ in POMIJANE_TYPY or r.get("isSidechain"):
            continue
        if r.get("isCompactSummary"):
            linie.append(f"\n[STRESZCZENIE PO KOMPAKCJI]\n{skroc(tekst_uzytkownika(r['message'].get('content')) or '', n * 4)}")
            continue
        wiadomosc = r.get("message") or {}
        tresc = wiadomosc.get("content")
        if typ == "user":
            if r.get("isMeta"):
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
    pliki = {}
    for surowa in plik.open(encoding="utf-8"):
        try:
            r = json.loads(surowa)
        except json.JSONDecodeError:
            continue
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        for b in (r.get("message") or {}).get("content") or []:
            if not isinstance(b, dict) or b.get("type") != "tool_use":
                continue
            w = b.get("input") or {}
            if b.get("name") == "Bash":
                komenda = w.get("command", "")
                for sc, dane in pliki.items():
                    if Path(sc).name in komenda:
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
            linie.append(Path(sciezka).read_text(encoding="utf-8", errors="replace"))
            continue
        uwagi = [u for u, warunek in (("niektóre Edit nie dały się nałożyć", not ok),
                                       ("plik zmieniano też przez Bash - te zmiany nie są uwzględnione", bash)) if warunek]
        linie.append(f"\n===== {sciezka} [odtworzone z sesji, pliku nie ma na dysku; Edit: {edycje}] =====")
        if uwagi:
            linie.append("[UWAGA: " + "; ".join(uwagi) + "]")
        linie.append(tresc if tresc is not None else "[brak pełnej treści - plik tylko edytowano w tej sesji]")
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
        tytul, pierwsza = "", ""
        for surowa in plik.open(encoding="utf-8"):
            try:
                r = json.loads(surowa)
            except json.JSONDecodeError:
                continue
            if r.get("type") == "ai-title":
                tytul = r.get("aiTitle", "")
            elif not pierwsza and r.get("type") == "user" and not r.get("isMeta"):
                pierwsza = tekst_uzytkownika((r.get("message") or {}).get("content")) or ""
        czas = datetime.datetime.fromtimestamp(plik.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        rozmiar = plik.stat().st_size // 1024
        wiersze.append(f"{plik.stem}  {czas}  {rozmiar:>6} KB  {tytul or '-'}  | {skroc(pierwsza, 70)}")
    return wiersze


def main():
    # Windows domyślnie wypisuje w kodowaniu konsoli, a oś czasu ma polskie znaki
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
                linie.append("\n[UWAGA] Sesja ma subagentów - ich praca jest w osobnych plikach, tu widać tylko zlecenia.")

    wynik = "\n".join(linie) + "\n"
    if a.wyjscie:
        Path(a.wyjscie).write_text(wynik, encoding="utf-8")
        print(f"Zapisano {len(wynik)} znaków do {a.wyjscie}")
    else:
        sys.stdout.write(wynik)


if __name__ == "__main__":
    main()
