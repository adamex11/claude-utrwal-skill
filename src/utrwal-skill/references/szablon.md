# Szablon nowego SKILL.md

Wypełnij każdą sekcję. Sekcję bez treści usuń, nie zostawiaj pustej.

```markdown
---
name: nazwa-skilla                  # = nazwa folderu; małe litery, cyfry, dywizy, bez polskich znaków
description: Używaj, gdy ... (konkretne sytuacje i frazy użytkownika, np. "zrób X dla Y"). Nie używaj, gdy ... (sytuacje podobne, ale obsługiwane inaczej). Tylko warunki użycia, bez streszczania kroków.
argument-hint: PARAMETR             # jeśli skill przyjmuje parametr
disable-model-invocation: true      # jeśli skill ma efekty uboczne (wysyła, publikuje, usuwa) - tylko ręczne wywołanie
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)   # jeśli skill ma skrypty - bez pytań o uprawnienia
---

# Tytuł (co powstaje)

Parametr: **$ARGUMENTS**. Jeśli brak, zapytaj o niego i nic więcej nie rób.

Skrypty: `${CLAUDE_SKILL_DIR}/scripts/`. Uruchamiaj przez interpreter, z pełną ścieżką w każdej komendzie: `python3 ${CLAUDE_SKILL_DIR}/scripts/skrypt.py` (na Windowsie `python`). Claude Code podstawia `${CLAUDE_SKILL_DIR}` przed pokazaniem skilla modelowi. Nie definiuj skrótów w rodzaju `$S`, bo zmienne powłoki nie przetrwają między wywołaniami.

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
