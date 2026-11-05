# claude-utrwal-skill

**Autor: Maciej Adamek** · [github.com/adamex11](https://github.com/adamex11)

Skill dla [Claude Code](https://claude.com/claude-code), który na koniec pracy zamienia to, czego
nauczyliście się z Claude w rozmowie, w **nowy skill na przyszłość**. Następnym razem to samo zadanie
idzie szybciej, taniej (mniej tokenów) i bez powtarzania tych samych błędów.

Skill to **przepis, nie zapis rozmowy**: zostaje ostateczna działająca procedura, parametry zamiast
konkretnych wartości, działający kod w `scripts/` i tabela pułapek z błędów, które naprawdę wystąpiły.
Równie ważne: gdy nie ma czego utrwalać, skill mówi **"nic"**, zamiast zaśmiecać listę skilli.

```
/utrwal-skill
```

## Jak to działa

1. **Zebranie materiału.** Głównym źródłem jest rozmowa, którą Claude ma w kontekście. Gdy rozmowa była
   streszczona, umiejętność powstawała w kilku sesjach albo przed `/clear`, skill czyta zapisy sesji
   (`~/.claude/projects/.../*.jsonl`) przez skrypt, który robi z nich zwięzłą oś czasu
   (sesja 3,3 MB -> ok. 37 KB). Kod zapisany w sesji, także w tymczasowym scratchpadzie, odzyskuje flagą `--pliki`.
2. **Analiza.** Każda lekcja trafia do jednej kategorii: **skill** (procedura, która powtórzy się na innym
   wejściu), **CLAUDE.md** (reguła albo fakt, nie procedura) albo **nic** (jednorazowe). Skill sprawdza
   istniejące skille i zamiast duplikatu proponuje **aktualizację**.
3. **Propozycja i STOP.** Nazwa, miejsce zapisu (projekt albo globalnie, z uzasadnieniem), parametry,
   kroki, skrypty, pułapki. **Bez Twojej akceptacji nic nie jest zapisywane.** W przypadku granicznym
   skill nie rozstrzyga sam, tylko pyta.
4. **Budowa.** SKILL.md według szablonu. Długi kod z sesji staje się **szkieletem z kopii działającego
   pliku** (treść i dane idą z JSON), a nie poleceniem "napisz X od nowa".
5. **Weryfikacja.** Lista kontrolna, potem **test suchy**: subagent bez kontekstu rozmowy czyta tylko nowy
   skill, dostaje inne wejście (najlepiej prawdziwe pliki) i wypisuje niejasności. Jedna runda poprawek.
6. **Podsumowanie.** Co powstało, co poprawiono, czego nie sprawdzono i komenda do testu na żywo.

## Wymagania

- Claude Code (CLI, aplikacja desktop albo rozszerzenie IDE).
- Python 3.9+ (`python3 --version`). Skrypt używa tylko biblioteki standardowej.
- Git (do pobrania repozytorium).

## Instalacja w Claude Code

### 1. Sprawdź wymagania

```bash
python3 --version
```

### 2. Pobierz repozytorium

```bash
git clone https://github.com/adamex11/claude-utrwal-skill.git
cd claude-utrwal-skill
```

### 3. Uruchom instalator

```bash
python3 install.py
```

Instalator kopiuje skill do `~/.claude/skills/utrwal-skill/` (albo do `$CLAUDE_CONFIG_DIR/skills/`,
jeśli używasz niestandardowego katalogu konfiguracji; wtedy przepisuje wszystkie ścieżki `~/.claude/`
w plikach skilla, także miejsca zapisu globalnych skilli i globalnego CLAUDE.md). Aktualizacja jest
bezpieczna: nowa wersja powstaje obok i zastępuje starą dopiero po udanym kopiowaniu. Jeśli
`~/.claude/skills/utrwal-skill` jest dowiązaniem (np. do klonu repozytorium), instalator go nie nadpisze.
`python3 install.py --sprawdz` tylko sprawdza wymagania, niczego nie kopiuje.

Na Windowsie użyj `python` zamiast `python3`.

### 4. Zrestartuj Claude Code

Albo otwórz nową sesję. Skill pojawi się na liście poleceń jako `/utrwal-skill`.

### 5. Pierwsze użycie

Pracuj z Claude normalnie. Gdy skończysz zadanie, które warto powtórzyć (np. raport dla klienta,
analiza dokumentu, generator prezentacji), wpisz:

```
/utrwal-skill
```

Przykładowa propozycja:

```
Nazwa: raport-kwartalny  |  Nowy  |  Miejsce: projekt - używa ledgera i skryptów tego projektu
Opis (description): Używaj, gdy użytkownik prosi o raport kwartalny spółki z PDF-ów wynikowych...
Parametry: TICKER, ścieżki PDF
Kroki: 1. Środowisko  2. Wyciągnięcie tabel z PDF  3. Ledger  4. Notatka DOCX  5. Kontrola liczb
Skrypty: tabele_pdf.py - wyciąga tabele - nowy; generuj_docx.py - bez zmian
Pułapki: tabela na dwóch stronach -> parser gubi wiersze -> scal strony przed parsowaniem
Do CLAUDE.md (propozycja): brak
Ograniczenia materiału: praca subagentów niewidoczna
Odrzucone jako jednorazowe: wartości z tego kwartału, wybór kolorów
```

Gdy nie ma czego utrwalać:

```
Wynik: nic do utrwalenia jako skill
Dlaczego: Jednorazowa instalacja narzędzia, bez procedury, która powtórzy się na innym wejściu.
Do CLAUDE.md (propozycja): ~/.claude/CLAUDE.md: "Do konwersji dokumentów używaj LibreOffice (soffice)."
```

W przypadku granicznym:

```
Kandydat graniczny: prezentacja-z-xlsx-i-pdf - prezentacja PPTX z arkusza i PDF-a z wynikami
Za: gotowy szkielet generatora i rozwiązane problemy środowiska
Przeciw: wykonane raz, częściowo pokrywa to skill pptx
Tworzyć skill? (tak -> pokażę propozycję / nie -> wynik "nic")
```

### 6. Użycie z wcześniejszymi sesjami

Gdy umiejętność powstawała w kilku sesjach albo przed `/clear`:

```
/utrwal-skill --sesja ID1 ID2
```

Listę sesji projektu (id, czas ostatniej zmiany pliku sesji, rozmiar, tytuł) pokaże Claude na prośbę, albo sam uruchomisz:

```bash
python3 ~/.claude/skills/utrwal-skill/scripts/wyciagnij_rozmowe.py --lista
```

Możesz też dać podpowiedź, co utrwalić: `/utrwal-skill notatka docx`.

### 7. Aktualizacja

```bash
cd claude-utrwal-skill
git pull
python3 install.py
```

### 8. Deinstalacja

```bash
python3 install.py --uninstall
```

### 9. Rozwiązywanie problemów

| Objaw | Co zrobić |
|-------|-----------|
| Brak `/utrwal-skill` na liście poleceń | Zrestartuj Claude Code; sprawdź, czy istnieje `~/.claude/skills/utrwal-skill/SKILL.md`. |
| "Nie znaleziono pliku sesji" | Zły id; weź właściwy z `--lista`. |
| "Podaj --sesja ID" | Zmienna `CLAUDE_CODE_SESSION_ID` jest pusta (np. skrypt uruchomiony poza Claude Code); podaj `--sesja`. |
| `--lista` nie pokazuje starszych sesji | Projekt był przenoszony; skrypt szuka po 3 ostatnich członach ścieżki, a gdy to nie wystarcza, podaj `--projekt <stara ścieżka>`. |
| W skrócie brakuje treści | Skrót obcina wpisy; Claude ponawia z `--max-znakow 2000`. |

## Skrypt `wyciagnij_rozmowe.py`

| Wywołanie | Działanie |
|---|---|
| (bez argumentów) | oś czasu bieżącej sesji |
| `--sesja ID [ID ...]` | oś czasu wskazanych sesji |
| `--lista [--projekt KATALOG]` | sesje projektu, także sprzed przeniesienia projektu |
| `--pliki` | pliki zapisane w sesji (Write/Edit), czy są na dysku, czy zmieniano je przez Bash |
| `--pliki WZORZEC` | treść pasujących plików: z dysku, a gdy pliku już nie ma, odtworzona z sesji |
| `--max-znakow N` | limit wpisu (domyślnie 300, wiadomości użytkownika 10x więcej) |
| `--wyjscie PLIK` | zapis do pliku |

Oś czasu zostawia: Twoje wiadomości (z argumentami komend, np. `/raport ABC`) i odpowiedzi na pytania,
skrócony tekst Claude, komendy, ścieżki zapisanych plików, błędy razem z komendą, która je wywołała,
oraz zlecenia i raporty końcowe subagentów i wyniki zadań w tle. Pomija: myślenie modelu, treść
zapisywanych plików, wstrzyknięte treści skilli i rekordy techniczne. Uszkodzone linie zapisu pomija,
zamiast przerywać pracę. Przy odtwarzaniu plików pomija Edity, które skończyły się błędem.

## Prywatność

- Skrypt działa **lokalnie** i tylko czyta pliki w `~/.claude/projects/`. Nic nie wysyła.
- Oś czasu trafia do kontekstu Claude, tak samo jak treść zwykłej rozmowy. Fragmenty wyglądające na
  sekrety (`Authorization: Bearer ...`, tokeny GitHub, klucze `sk-...`, klucze AWS i Slack, hasła
  w cudzysłowie po `password=`/`token=`/`api_key=`) skrypt zamienia na `[SEKRET]` i podaje ich liczbę.
  Maskowanie opiera się na wzorcach, więc nie złapie wszystkiego: przejrzyj propozycję przed akceptacją.
- Lista kontrolna nowego skilla ma osobną sekcję o sekretach (grep po typowych wzorcach, sekrety ze
  zmiennych środowiskowych, nic oznaczonego `[SEKRET]` w skillu).
- Nowy skill zapisuje się dopiero po Twojej akceptacji. Gdy powstaje w repozytorium projektu, sprawdź
  go przed commitem.

## Ograniczenia

- Przebieg pracy subagentów jest w osobnych plikach; skrót pokazuje ich zlecenie i raport końcowy.
- Pliki tworzone wyłącznie przez Bash (`cp`, heredoc) nie trafiają do `--pliki`, a zmian zrobionych przez
  Bash nie da się odtworzyć z zapisu sesji (dlatego plik z dysku ma pierwszeństwo).
- Format zapisu sesji po kompakcji nie został zweryfikowany na prawdziwej sesji.
- Skill nie działa automatycznie (świadomie: bez hooków, żeby nie tworzyć skilli z każdej rozmowy).
- Ocena "skill / nic" to decyzja modelu; przypadki graniczne trafiają do Ciebie jako pytanie.

## Testy

```bash
python3 -m unittest discover -s tests -v
```

36 testów na sztucznych zapisach sesji (bez danych z prawdziwych rozmów): filtrowanie osi czasu,
argumenty komend, raporty subagentów, uszkodzone linie i ucięte znaki, streszczenie po kompakcji,
obcinanie, maskowanie sekretów (także bez cudzysłowu w Bash i w JSON, bez fałszywych trafień typu tokenizer), odzyskiwanie plików (MultiEdit, nieudane Edity, zmiany przez Bash), lista sesji (także długich) po
przeniesieniu projektu i z polskimi znakami w ścieżce, instalator (bezpieczna aktualizacja z przywracaniem, dowiązania,
przepisywanie ścieżek) i deinstalator.
CI uruchamia je na Windows i macOS (Python 3.9 i 3.12) oraz na Linuksie (Python 3.12).

Sam skill był testowany subagentami bez kontekstu rozmowy na prawdziwych sesjach (zadanie jednorazowe,
skill już istniejący, przypadek graniczny, pełna budowa). Wyniki i zmiany po testach:
[docs/projekt.md](docs/projekt.md).

## Autor

**Maciej Adamek** · [github.com/adamex11](https://github.com/adamex11)

Skill powstał jako zadanie domowe z kursu Vibe Coding (dzień 4: tworzenie skilli).

## Licencja

[MIT](LICENSE) © 2026 Maciej Adamek
