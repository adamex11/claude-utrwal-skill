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
- Pomija: myślenie modelu, rekordy techniczne, rekordy subagentów (sidechain), uszkodzone linie, Edity zakończone błędem (przy `--pliki`).
- Maskuje fragmenty wyglądające na sekrety (`[SEKRET]`) w osi czasu i w `--pliki`.

## Znane ograniczenia

- Przebieg pracy subagentów jest w osobnych plikach (`ID/subagents/`); widać zlecenie i raport końcowy (rekord `isMeta` z `origin.kind = "peer"`) oraz wyniki zadań w tle (`<task-notification>`).
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

## Recenzja zewnętrzna (2026-11-05)

Recenzja modelem Fable (ocena 7/10, bez błędów krytycznych). Poprawione:

| # | Problem | Poprawka |
|---|---|---|
| 1 | Argumenty komend slash ginęły (leniwe `.*?` przed opcjonalną grupą) | osobne wyszukanie nazwy i argumentów |
| 2 | Raporty subagentów odfiltrowane, choć dokumentacja mówiła, że są widoczne | raport z rekordu `origin.kind = "peer"`, status i wynik z `<task-notification>` |
| 3 | Przy `CLAUDE_CONFIG_DIR` przepisywana tylko jedna ścieżka | instalator przepisuje każde `~/.claude/` we wszystkich plikach .md |
| 4 | Brak ochrony przed sekretami w nowym skillu | maskowanie `[SEKRET]` w skrypcie + sekcja "Sekrety" na liście kontrolnej |
| 5 | Szablon wprowadzał `$S`, sprzecznie z SKILL.md | pełne ścieżki w każdej komendzie |
| 6 | Aktualizacja nieatomowa; `rmtree` na dowiązaniu kończył się tracebackiem | kopia obok i podmiana po sukcesie; dowiązanie nie jest nadpisywane |
| 7 | Nieudane Edity nakładane przy odtwarzaniu | pomijane wywołania z `is_error` |

Drobne: `errors="replace"` przy czytaniu, UTF-8 także na stderr, wskazówki dla Windows w SKILL.md, `description` pisany dla menu (przy `disable-model-invocation: true` model go nie dostaje), wymagany Python 3.9+ zgodnie z CI, 9 nowych testów (27 razem; 8 z nich nie przechodzi na kodzie sprzed poprawek).

## Druga recenzja (8/10)

| # | Problem | Poprawka |
|---|---|---|
| N1 | Test bezpiecznej aktualizacji nie sprawdzał wyniku podprocesu, a gałąź przywracania nie była testowana | asercja na zgłoszoną awarię + wariant z awarią przy wstawianiu nowej wersji (test wykrywa usunięcie przywracania) |
| N2 | Nieusunięty `.utrwal-skill-stary/` przechodził po cichu | komunikat z prośbą o ręczne usunięcie |
| N3 | Sekrety bez cudzysłowu w Bash (`export X_TOKEN=...`) i w nazwach typu `SECRET_KEY` nie były maskowane | osobny wzorzec dla komend Bash, szerszy wzorzec nazw |
| N4 | Argumenty narzędzia Skill trafiały do osi czasu bez skracania i maskowania | przechodzą przez `skroc` |
| N5 | Maskowane placeholdery mogły skłonić do usuwania linii | zdanie w SKILL.md: zastąp zmienną środowiskową |

Odrzucone: N6. Uwaga, że `ubuntu-latest` ma Pythona 3.9, jest nieaktualna: runner to Ubuntu 26.04 i setup-python kończy się błędem "not found for Ubuntu 26.04" (log CI pierwszego commita). Poprawiony tylko komentarz. Drobne z pierwszej recenzji: D2, D5, D9 (akapit podzielony na punkty), D10, D12, D13. D3: zmiana przez Bash tylko przy komendzie modyfikującej (przekierowanie, `sed -i`, `mv`...) i nazwie pliku jako osobnym słowie. D4: `--lista` czyta tytuł z końcówki pliku i pierwszą wiadomość z początku.

## Trzecia recenzja (Fable, 8/10)

| # | Problem | Poprawka |
|---|---|---|
| W1 | Rozszerzony wzorzec nazw maskował zwykły kod (`tokenizer = "gpt2"`, `token_url = "https://..."`) | po nazwie tylko krótka lista końcówek (`_key`, `_id`, `_value`...) |
| W2 | `2>&1` i `>/dev/null` liczone jako zmiana pliku przez Bash; formatery (`prettier --write`, `black`, `sed -e ... -i`) pomijane | przekierowania bez pliku zdejmowane przed sprawdzeniem, formatery dopisane |
| W3 | Sekrety w kluczach JSON/dict (`{"password": "..."}`, wejścia narzędzi MCP) niemaskowane | opcjonalny cudzysłów wokół nazwy |

Drobne: `split("\n")` zamiast `splitlines()` w `ostatni_tytul` (zgodnie z `rekordy()`), `--token wartość` po spacji maskowane w Bash i argumentach skilli (najpierw wzorce z rodzajem sekretu, już zamaskowane fragmenty nie są liczone drugi raz), `SKILL.md` "czas ostatniej zmiany", łagodniejszy komunikat o nieusuniętej kopii. D6 (ścieżka względna zamiast przepisywania `~/.claude/`) świadomie pominięte: zaszyta ścieżka jest pewniejsza niż poleganie na wstrzykniętej linii "Base directory". Zaakceptowane: fałszywe trafienie `token=...` w treści `git commit -m`. Razem 36 testów.
