#!/usr/bin/env python3
# Copyright (c) 2026 Maciej Adamek - utrwal-skill (https://github.com/adamex11/claude-utrwal-skill). Licencja MIT.
"""Instalator skilla /utrwal-skill dla Claude Code.

Kopiuje src/utrwal-skill do <katalog konfiguracji Claude>/skills/utrwal-skill
(domyślnie ~/.claude, albo CLAUDE_CONFIG_DIR, jeśli ustawiony).

Użycie:
  python3 install.py               # instalacja albo aktualizacja
  python3 install.py --uninstall   # usunięcie skilla
  python3 install.py --sprawdz     # tylko sprawdzenie wymagań, bez zmian
"""
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

NAZWA = "utrwal-skill"
ZRODLO = Path(__file__).resolve().parent / "src" / NAZWA
DOMYSLNY_KATALOG = "~/.claude/"
MIN_PYTHON = (3, 9)


def katalog_konfiguracji():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser().resolve()


def cel():
    return katalog_konfiguracji() / "skills" / NAZWA


def sprawdz():
    """Zwraca listę problemów (pusta = wszystko w porządku)."""
    problemy = []
    if sys.version_info < MIN_PYTHON:
        problemy.append(f"Wymagany Python {'.'.join(map(str, MIN_PYTHON))}+, jest {sys.version.split()[0]}.")
    if not (ZRODLO / "SKILL.md").is_file():
        problemy.append(f"Brak {ZRODLO / 'SKILL.md'} - uruchom instalator z katalogu repozytorium.")
    if not katalog_konfiguracji().is_dir():
        problemy.append(f"Brak katalogu Claude Code {katalog_konfiguracji()} - czy Claude Code jest zainstalowany?")
    return problemy


def przepisz_sciezki(katalog_skilla):
    """Przy niestandardowym katalogu konfiguracji zamienia każde ~/.claude/ w plikach .md skilla.

    Dotyczy nie tylko ścieżek do skryptów, ale też miejsc zapisu (globalne skille, globalny CLAUDE.md).
    """
    konfig = katalog_konfiguracji()
    if konfig == Path(DOMYSLNY_KATALOG).expanduser().resolve():
        return
    for plik in katalog_skilla.rglob("*.md"):
        tresc = plik.read_text(encoding="utf-8")
        plik.write_text(tresc.replace(DOMYSLNY_KATALOG, konfig.as_posix() + "/"), encoding="utf-8")


def instaluj():
    docelowy = cel()
    if docelowy.is_symlink():
        # Dowiązanie zwykle wskazuje na klon repozytorium (tryb deweloperski) - nie nadpisujemy go
        sys.exit(f"BŁĄD: {docelowy} jest dowiązaniem do {os.readlink(docelowy)}. Usuń je ręcznie albo zostaw, "
                 "jeśli tak pracujesz z repozytorium.")
    aktualizacja = docelowy.exists()
    docelowy.parent.mkdir(parents=True, exist_ok=True)
    # Kopia powstaje obok celu i dopiero gotowa zastępuje stary skill, więc nieudane kopiowanie go nie niszczy
    tymczasowy = Path(tempfile.mkdtemp(prefix=f".{NAZWA}-nowy-", dir=docelowy.parent))
    stary = docelowy.parent / f".{NAZWA}-stary"
    try:
        nowy = tymczasowy / NAZWA
        shutil.copytree(ZRODLO, nowy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        przepisz_sciezki(nowy)
        if aktualizacja:
            if stary.exists():
                shutil.rmtree(stary)
            docelowy.rename(stary)
        nowy.rename(docelowy)
    except Exception:
        if aktualizacja and stary.exists() and not docelowy.exists():
            stary.rename(docelowy)
        raise
    finally:
        shutil.rmtree(tymczasowy, ignore_errors=True)
    shutil.rmtree(stary, ignore_errors=True)
    print(f"{'Zaktualizowano' if aktualizacja else 'Zainstalowano'} skill w {docelowy}")
    print("Zrestartuj Claude Code (albo otwórz nową sesję), potem na koniec pracy wpisz: /utrwal-skill")


def odinstaluj():
    docelowy = cel()
    if docelowy.is_symlink():
        docelowy.unlink()
        print(f"Usunięto dowiązanie {docelowy} (wskazywany katalog został nietknięty)")
        return
    if not docelowy.exists():
        print(f"Skill nie jest zainstalowany ({docelowy}).")
        return
    shutil.rmtree(docelowy)
    print(f"Usunięto {docelowy}")


def main():
    for strumien in (sys.stdout, sys.stderr):
        if hasattr(strumien, "reconfigure"):
            strumien.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tryb = p.add_mutually_exclusive_group()
    tryb.add_argument("--uninstall", action="store_true", help="usuń zainstalowany skill")
    tryb.add_argument("--sprawdz", action="store_true", help="tylko sprawdź wymagania")
    a = p.parse_args()

    if a.uninstall:
        odinstaluj()
        return
    problemy = sprawdz()
    for problem in problemy:
        print(f"BŁĄD: {problem}")
    if problemy:
        sys.exit(1)
    if a.sprawdz:
        print(f"Wymagania spełnione. Skill trafi do {cel()}")
        return
    instaluj()


if __name__ == "__main__":
    main()
