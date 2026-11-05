# Lista kontrolna nowego skilla

Sprawdź każdy punkt. Gdy któryś nie jest spełniony, popraw skill przed testem suchym.

## Nagłówek
- [ ] `name` = nazwa folderu; tylko małe litery, cyfry, dywizy; bez polskich znaków.
- [ ] `description` opisuje tylko, KIEDY użyć (sytuacje, frazy użytkownika), bez streszczenia kroków. Do ok. 500 znaków.
- [ ] `description` mówi też, kiedy NIE używać, jeśli istnieje podobny skill albo podobna sytuacja; nie pokrywa się z opisem innego skilla.
- [ ] `argument-hint`, jeśli skill przyjmuje parametr; w treści `$ARGUMENTS` i reakcja na jego brak.
- [ ] `disable-model-invocation: true`, jeśli skill ma efekty uboczne (wysyłka, publikacja, usuwanie, płatności).
- [ ] `allowed-tools` z `${CLAUDE_SKILL_DIR}`, jeśli skill uruchamia własne skrypty; bez szerokich uprawnień w rodzaju `Bash(*)`.

## Ogólność
- [ ] Brak wartości z tego konkretnego przebiegu (ticker, nazwa klienta, data, liczba) poza oznaczonym przykładem. Takie wartości są parametrami.
- [ ] Stałe projektu (nazwa bazy, szablonu, kanału, identyfikator bazy w Notion) mogą zostać, jeśli skill jest projektowy: zebrane w jednym miejscu (sekcja w SKILL.md albo plik w `references/`) i opisane, czym są.
- [ ] Brak ścieżek bezwzględnych `/Users/...`. Pliki skilla przez `${CLAUDE_SKILL_DIR}/...`, pliki projektu względem katalogu projektu albo przez `${CLAUDE_PROJECT_DIR}/...`.
- [ ] Komendy `python3` mają uwagę, że na Windowsie to `python`.
- [ ] Brak narracji ("w rozmowie zrobiliśmy"); tryb rozkazujący.

## Treść
- [ ] Każdy krok ma komendę lub jasną czynność i warunek przejścia dalej.
- [ ] Kroki deterministyczne są skryptami w `scripts/`, nie opisem do odtworzenia. Długi kod z rozmowy jest szkieletem z parametrami, a nie poleceniem "napisz X".
- [ ] Kroki, które robi już inny skill lub skrypt, odwołują się do niego.
- [ ] Skrypty nie mają zaszytych ścieżek narzędzi (np. `/opt/homebrew/bin/...`); szukają ich przez `which` i zgłaszają brak.
- [ ] Sekcja "Pułapki" zawiera błędy, które faktycznie wystąpiły, z rozwiązaniem.
- [ ] Ślepe uliczki z rozmowy nie są krokami.
- [ ] SKILL.md ma mniej niż 500 linii; długie materiały są w `references/`.

## Sekrety
- [ ] Żadnych tokenów, kluczy API, haseł ani nagłówków `Authorization: Bearer ...` w SKILL.md, `scripts/` i `references/`. Sprawdź grepem, np. `grep -rniE "bearer|basic |api[_-]?key|token|secret|passw|sk-|sk_live|ghp_|glpat-|AIza|eyJ|PRIVATE KEY|://[^/ ]+:[^/ ]+@" <folder skilla>`, i przejrzyj każde trafienie.
- [ ] Skrypty biorą sekrety ze zmiennych środowiskowych albo pliku spoza skilla (np. `.env` w `.gitignore`), a SKILL.md mówi, jak je ustawić.
- [ ] Nie przenoś do skilla fragmentów, które `wyciagnij_rozmowe.py` oznaczył jako `[SEKRET]`, ani niczego, co wygląda na sekret, a nie zostało oznaczone (maskowanie jest heurystyczne).

## Skrypty
- [ ] Każdy skrypt uruchomiony co najmniej raz po uogólnieniu (np. `--help` albo przebieg na przykładzie).
- [ ] Zależności spoza biblioteki standardowej są w `scripts/requirements.txt`.
- [ ] Jedno źródło prawdy: skrypty przeniesione albo świadomie skopiowane (zapisane w "Pułapkach", że kopie trzeba aktualizować razem).

## Zasady środowiska
- [ ] Skill nie łamie reguł z CLAUDE.md projektu (język, format, zakazy).
