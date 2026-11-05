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
from pathlib import Path

NAZWA = "utrwal-skill"
ZRODLO = Path(__file__).resolve().parent / "src" / NAZWA
DOMYSLNA_SCIEZKA = "~/.claude/skills/utrwal-skill"
MIN_PYTHON = (3, 8)


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


def instaluj():
    docelowy = cel()
    aktualizacja = docelowy.exists()
    if aktualizacja:
        shutil.rmtree(docelowy)
    shutil.copytree(ZRODLO, docelowy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # SKILL.md podaje ścieżki do skryptów; przy niestandardowym katalogu konfiguracji trzeba je przepisać
    if docelowy != Path(DOMYSLNA_SCIEZKA).expanduser().resolve():
        skill_md = docelowy / "SKILL.md"
        tresc = skill_md.read_text(encoding="utf-8").replace(DOMYSLNA_SCIEZKA, docelowy.as_posix())
        skill_md.write_text(tresc, encoding="utf-8")
    print(f"{'Zaktualizowano' if aktualizacja else 'Zainstalowano'} skill w {docelowy}")
    print("Zrestartuj Claude Code (albo otwórz nową sesję), potem na koniec pracy wpisz: /utrwal-skill")


def odinstaluj():
    docelowy = cel()
    if not docelowy.exists():
        print(f"Skill nie jest zainstalowany ({docelowy}).")
        return
    shutil.rmtree(docelowy)
    print(f"Usunięto {docelowy}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
