# Spec: skill `/utrwal-skill`

Data: 2026-11-04, aktualizacja 2026-11-05 (wersja po testach). Status: zbudowany i przetestowany na subagentach.

## Cel

Na koniec pracy użytkownik wpisuje `/utrwal-skill [podpowiedź] [--sesja ID ...]`. Skill wydobywa z rozmowy (albo kilku sesji) powtarzalną umiejętność i zapisuje ją jako nowy skill albo aktualizację istniejącego, żeby następnym razem zrobić to samo szybciej i taniej (mniej tokenów, mniej błędów).

Sukces: powstały skill działa na innym wejściu niż to z rozmowy, nie powtarza ślepych uliczek, a działający kod z sesji jest w `scripts/`. Równie ważne: skill mówi "nic", gdy nie ma czego utrwalać.

## Ustalenia z użytkownikiem

- Uruchamianie tylko ręczne (`disable-model-invocation: true`), bez hooków.
- Skill proponuje miejsce zapisu nowego skilla (projekt `.claude/skills/` albo globalnie `~/.claude/skills/`) z uzasadnieniem, użytkownik zatwierdza.
- Weryfikacja: lista kontrolna + test suchy subagentem bez kontekstu rozmowy. Test na żywo tylko proponowany.

## Miejsce i pliki

Globalnie: `~/.claude/skills/utrwal-skill/`

- `SKILL.md` - procedura (6 kroków, tabela pułapek).
- `scripts/wyciagnij_rozmowe.py` - zapis sesji `.jsonl` -> zwięzła oś czasu, lista sesji, odzyskiwanie plików.
- `references/szablon.md` - szkielet nowego SKILL.md.
- `references/lista_kontrolna.md` - kryteria jakości nowego skilla.

Frontmatter: `name`, `description` (tylko warunki użycia, bez streszczania kroków), `disable-model-invocation: true`, `argument-hint`. Bez `context: fork`, bo skill potrzebuje kontekstu rozmowy.

## Zasady

- Nic nie jest zapisywane przed akceptacją propozycji (poza plikami roboczymi w scratchpadzie). Dotyczy też CLAUDE.md i istniejących skilli.
- Jeden skill na wywołanie.
- "Nic" to poprawny wynik: opis każdego skilla jest wczytywany w każdej sesji, więc skill z zadania jednorazowego tylko kosztuje.

## Przebieg

1. **Zebranie.** Głównym źródłem jest rozmowa w kontekście. Skrypt tylko wtedy, gdy czegoś brakuje: po kompakcji, dla sesji sprzed `/clear`, dla kilku sesji naraz, albo gdy użytkownik podał `--sesja`. Kod z sesji odzyskuje się przez `--pliki`.
2. **Analiza.**
   - Każda lekcja: `skill` / `CLAUDE.md` (projektu albo globalny `~/.claude/CLAUDE.md` dla faktów o maszynie; tylko jeśli jeszcze tego tam nie ma) / `nic`.
   - Kryterium pułapki: błąd, który może się powtórzyć (zależy od wejścia, środowiska, kolejności kroków). Błąd trwale naprawiony w kodzie nie jest pułapką; jeśli wymaga stałej kontroli, staje się krokiem.
   - Długi kod specyficzny dla przypadku: szkielet zaczynany **od kopii działającego pliku**, w którym tylko treść i dane zamienia się na JSON lub argumenty. Nie pisze się generatora od nowa.
   - Kroki, które robi już inny skill lub skrypt: odwołanie zamiast opisu.
   - Istniejące skille: lista z kontekstu + `ls` folderów skilli. Pokrycie -> aktualizacja (tylko brakujące elementy). Skill zbudowany w analizowanej sesji bez późniejszego użycia -> "nic", chyba że brakuje kroku.
   - **Przypadek graniczny** (procedura powtarzalna, ale wykonana raz albo częściowo pokryta przez inne skille): skill nie rozstrzyga sam, tylko pyta użytkownika (kandydat, za, przeciw).
   - Wynik "nic": krótki format (dlaczego, propozycja do CLAUDE.md, ograniczenia materiału), kroki 3-6 pomijane.
3. **Propozycja i STOP.** Nazwa, nowy/aktualizacja, miejsce z uzasadnieniem, opis, parametry, kroki (przy aktualizacji tylko zmiany), skrypty (nowy / przenieść / skopiować / zaktualizować / bez zmian), do 8 pułapek, propozycja do CLAUDE.md, ograniczenia materiału, odrzucone.
4. **Budowa.** SKILL.md wg szablonu (przy aktualizacji tylko zaakceptowane zmiany). Każdy skrypt uruchomiony raz; gdy się nie da (sieć, zależności), co najmniej kontrola składni i wpis "niesprawdzone" w podsumowaniu.
5. **Weryfikacja.** Lista kontrolna, potem jeden test suchy: subagent czyta tylko nowy skill, dostaje inne wejście (najlepiej prawdziwe pliki z projektu lub dysku), opisuje kroki i niejasności, niczego nie uruchamia. Jedna runda poprawek.
6. **Podsumowanie.** Co powstało i gdzie, wynik testu suchego (otwarte sprawy jako pytania), czego nie sprawdzono, komenda testu na żywo, pozostali kandydaci.

## Skrypt `wyciagnij_rozmowe.py`

| Wywołanie | Działanie |
|---|---|
| (bez argumentów) | oś czasu bieżącej sesji (`CLAUDE_CODE_SESSION_ID`) |
| `--sesja ID [ID ...]` | oś czasu wskazanych sesji (szuka we wszystkich projektach) |
| `--lista [--projekt KATALOG]` | sesje projektu: id, data, rozmiar, tytuł; dołącza sesje sprzed przeniesienia projektu (foldery z tymi samymi 3 ostatnimi członami ścieżki) |
| `--pliki` | pliki zapisane w sesji (Write/Edit), czy są na dysku, czy zmieniano je przez Bash |
| `--pliki WZORZEC` | treść pasujących plików: z dysku, a gdy pliku nie ma, odtworzona z sesji (Write + Edit) z ostrzeżeniem o zmianach przez Bash |
| `--max-znakow N` | limit wpisu (domyślnie 300, wiadomości użytkownika 10x więcej) |
| `--wyjscie PLIK` | zapis do pliku |

- Czyta strumieniowo (pliki sesji do kilku MB; sesja 3,3 MB -> ok. 37 KB skrótu).
- Zostawia: wiadomości użytkownika (bez wstrzykniętych treści i powiadomień), odpowiedzi na pytania, skrócony tekst asystenta, wywołania narzędzi (Bash: komenda; Write/Edit/Read: ścieżka), błędy z komendą, która je wywołała, wywołania skilli.
- Pomija: myślenie modelu, rekordy techniczne, rekordy subagentów (sidechain).

## Znane ograniczenia

- Praca subagentów jest w osobnych plikach (`ID/subagents/`); widać tylko zlecenie i raport.
- Pliki tworzone wyłącznie przez Bash (`cp`, heredoc) nie trafiają do `--pliki`; zmian przez Bash nie da się odtworzyć z sesji.
- Format zapisu po kompakcji nie został zweryfikowany na prawdziwej sesji.
- Scratchpad (`/private/tmp/...`) znika po restarcie, więc kod trzeba przenieść do `scripts/` nowego skilla.

## Poza zakresem

Automatyka i hooki, kilka skilli naraz, zmiany w CLAUDE.md, pamięci i istniejących skillach bez akceptacji, procedura testu na żywo.

## Testy (subagenci bez kontekstu rozmowy)

| Scenariusz | Sesja | Oczekiwane | Wynik |
|---|---|---|---|
| Zadanie jednorazowe | c18d573f (instalacja OpenOffice) | "nic" | "nic" 3/3 |
| Skill już istnieje | b2233a4a (budowa pakiet-analityczny) | brak duplikatu | runda 1: aktualizacja; po dodaniu kryterium pułapki: "nic" 5/5 |
| Przypadek graniczny | 8dec41ef (prezentacja z xlsx i pdf) | pytanie do użytkownika | pytanie z argumentami za i przeciw |
| Pełna budowa (odpowiedź "tak") | 8dec41ef | działający skill | skill z 5-7 plikami; w ostatniej wersji generator z kopii `build.js` (319 -> 255 linii, poprawki z sesji zachowane), zbudowany PPTX 15 slajdów |

Zmiany wprowadzone po testach: kryterium pułapki, format i zasady wyniku "nic", reguła przypadku granicznego, sprawdzanie CLAUDE.md przed propozycją, `--pliki` (kod ze scratchpadu), szkielet z kopii działającego pliku, kontrola składni przy niemożliwym uruchomieniu, prawdziwe pliki w teście suchym, `--lista` po przeniesieniu projektu.

Nieprzetestowane: użycie na żywo z prawdziwymi odpowiedziami użytkownika.
