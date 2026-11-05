# Szablon nowego SKILL.md

Wypełnij każdą sekcję. Sekcję bez treści usuń, nie zostawiaj pustej.

```markdown
---
name: nazwa-skilla                  # = nazwa folderu; małe litery, cyfry, dywizy, bez polskich znaków
description: Używaj, gdy ... (konkretne sytuacje i frazy użytkownika, np. "zrób X dla Y"). Tylko warunki użycia, bez streszczania kroków.
argument-hint: PARAMETR             # jeśli skill przyjmuje parametr
---

# Tytuł (co powstaje)

Parametr: **$ARGUMENTS**. Jeśli brak, zapytaj o niego i nic więcej nie rób.

Skrypty: `<pełna ścieżka skilla>/scripts/`. Uruchamiaj przez interpreter, z pełną ścieżką w każdej komendzie: `python3 <pełna ścieżka skilla>/scripts/skrypt.py` (zmienne powłoki nie przetrwają między wywołaniami, więc nie definiuj skrótów w rodzaju `$S`).

## Zasady (obowiązują w każdym kroku)

- Reguły, których złamanie psuje wynik. Każda z krótkim "dlaczego".

## Krok 0. Środowisko

Co musi być zainstalowane, jak to sprawdzić, co zrobić, gdy brakuje.

## Krok 1..N. <czynność>

Komenda, oczekiwany wynik, warunek przejścia dalej. Przy decyzjach: warunek -> działanie.

## Pułapki

| Objaw | Przyczyna | Co zrobić |
|-------|-----------|-----------|
| (z błędów w rozmowie) | | |

## Wynik

Lista plików, które powstają, i co pokazać użytkownikowi na koniec.
```

Wskazówki:
- Kroki deterministyczne (pobieranie, przeliczanie, generowanie plików, kontrole) -> skrypt w `scripts/`. W SKILL.md zostaje komenda i interpretacja wyniku.
- Długie materiały (listy kluczy, schematy, przykłady treści) -> `references/` i jedno zdanie w SKILL.md, kiedy je przeczytać.
- Pisz w trybie rozkazującym, do wykonawcy, bez historii: "Uruchom", a nie "W rozmowie uruchomiliśmy".
