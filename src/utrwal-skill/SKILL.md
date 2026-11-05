---
name: utrwal-skill
description: Używaj, gdy użytkownik wpisze /utrwal-skill albo na koniec pracy poprosi o zapisanie tego, czego nauczyliśmy się w rozmowie lub projekcie, jako skilla na przyszłość (np. "zrób z tego skill", "utrwal to", "żeby następnym razem poszło szybciej").
argument-hint: "[podpowiedź, np. notatka docx] [--sesja ID ...]"
disable-model-invocation: true
---

# Utrwalenie umiejętności z rozmowy jako skill

Podpowiedź użytkownika: **$ARGUMENTS** (może być pusta - wtedy sam wskaż najlepszego kandydata).

Cel: następnym razem to samo zadanie ma pójść szybciej, taniej i bez powtarzania błędów. Skill to **przepis, nie zapis rozmowy**: zostaje ostateczna działająca procedura, parametry zamiast konkretnych wartości, kod w skryptach i lekcje z błędów.

Pliki skilla: skrypty w `~/.claude/skills/utrwal-skill/scripts/`, materiały w `~/.claude/skills/utrwal-skill/references/`. Zmienne powłoki nie przetrwają między wywołaniami, więc w każdej komendzie podawaj pełną ścieżkę. Komendy uruchamiaj z katalogu projektu.

Pliki robocze (oś czasu sesji) zapisuj w katalogu scratchpad z kontekstu systemowego, a gdy go nie ma, w `/tmp/`.

## Zasady

- **Nic nie zapisuj przed akceptacją propozycji z kroku 3** (poza plikami roboczymi). Dotyczy też CLAUDE.md, pamięci i istniejących skilli.
- **Jeden skill na wywołanie.** Pozostałych kandydatów wymień w podsumowaniu.
- **"Nic" to poprawny wynik.** Skill z zadania jednorazowego kosztuje tokeny w każdej sesji (jego opis jest zawsze wczytany) i nic nie daje.
- Pisz w języku i formacie wymaganym przez CLAUDE.md projektu.

## Krok 1. Zebranie materiału

Głównym źródłem jest rozmowa, którą masz w kontekście. Skrypt uruchom tylko wtedy, gdy:
- rozmowa była streszczona (kompakcja) i brakuje szczegółów, albo
- umiejętność powstała we wcześniejszych sesjach (przed `/clear`) lub w kilku sesjach, albo
- użytkownik podał `--sesja`.

```bash
python3 ~/.claude/skills/utrwal-skill/scripts/wyciagnij_rozmowe.py --lista     # sesje projektu: id, data, rozmiar, tytuł
python3 ~/.claude/skills/utrwal-skill/scripts/wyciagnij_rozmowe.py --sesja ID [ID ...] --wyjscie <scratchpad>/os.md
```

Bez `--sesja` skrypt czyta bieżącą sesję (zmienna `CLAUDE_CODE_SESSION_ID`). Gdy użytkownik nie wie, które sesje wskazać, pokaż mu `--lista` i zapytaj.

Wynik to **skrót**: wiadomości użytkownika do ok. 3000 znaków, pozostałe wpisy do 300, z pominięciem treści zapisywanych plików i udanych wyników narzędzi. Gdy skrócony fragment jest kluczowy (np. wymagania wklejone przez użytkownika albo końcowe podsumowanie asystenta), uruchom skrypt ponownie z `--max-znakow 2000` (podnosi limit dla wszystkich wpisów). **Kod z sesji:** `--sesja ID --pliki` pokazuje pliki zapisane w sesji (Write/Edit) i to, czy są jeszcze na dysku. `--sesja ID --pliki <fragment ścieżki>` wypisuje ich treść: z dysku, jeśli plik istnieje, albo odtworzoną z sesji z ostrzeżeniem, czego nie udało się odtworzyć (zmiany przez Bash). Pliki utworzone wyłącznie przez Bash (`cp`, heredoc) nie są na tej liście, więc szukaj ich w projekcie. Kod w scratchpadzie (`/private/tmp/...` albo `/tmp/...`) jest tymczasowy i znika po restarcie komputera. Potrzebne fragmenty przenieś do `scripts/` nowego skilla, nie odwołuj się do nich. Praca subagentów nie jest w wyniku (widać tylko zlecenie i raport); jeśli była kluczowa, zapisz to w propozycji jako ograniczenie.

## Krok 2. Analiza

1. Wypisz lekcje z rozmowy i przypisz każdej jedną kategorię:
   - **skill** - procedura, która się powtórzy na innym wejściu (inna spółka, inny dokument, inny klient),
   - **CLAUDE.md** - reguła albo fakt, który trzeba znać, ale który nie jest procedurą (najpierw przeczytaj aktualny CLAUDE.md; jeśli to już tam jest, nie proponuj). Dotyczy projektu -> `CLAUDE.md` projektu. Dotyczy maszyny lub wszystkich projektów (np. "używaj LibreOffice, cask openoffice jest zablokowany") -> `~/.claude/CLAUDE.md`,
   - **nic** - jednorazowe, zbyt specyficzne albo powszechnie znane.
2. Dla kandydata na skill ustal:
   - **Wejście, które się zmienia** -> parametr (`$ARGUMENTS`).
   - **Ostateczną działającą ścieżkę.** Ślepe uliczki pomiń, ale ich wniosek zapisz jako pułapkę (objaw, przyczyna, rozwiązanie).
   - **Które błędy są pułapkami.** Pułapka to błąd, na który wykonawca skilla może trafić ponownie: zależy od wejścia (inny format danych, inna spółka), od środowiska albo od kolejności kroków. Błąd trwale naprawiony w kodzie skryptu NIE jest pułapką, bo się nie powtórzy. Jeśli jego naprawa wymaga kontroli przy każdym przebiegu (np. "sprawdź, że PDF ma 1 stronę"), zapisz tę kontrolę jako krok.
   - **Kod, który zadziałał i się powtórzy** -> skrypt w `scripts/`. Jeśli skrypty już leżą w projekcie, zdecyduj: przenieść (jedno źródło) czy skopiować (dwie kopie do utrzymania).
   - **Kod długi i specyficzny dla przypadku** (np. generator dokumentu z treścią na sztywno): nie zostawiaj go jako "napisz X". Zrób szkielet w `scripts/`: **zacznij od kopii działającego pliku** (`--pliki`), a potem zamień zaszytą treść i dane na odczyt z pliku JSON lub argumentów. Logika, układ i poprawki z sesji (np. przesunięte podpisy, wyrównania) zostają bez zmian. Nie pisz generatora od nowa, bo nowy kod nie przeszedł kontroli, którą przeszedł kod z sesji. Najwięcej tokenów kosztuje właśnie pisanie takiego kodu od zera.
   - **Kroki, które robi już inny skill lub skrypt** (lista skilli, `scripts/` istniejących skilli, skrypty projektu): odwołaj się do nich zamiast opisywać krok od nowa.
3. Sprawdź istniejące skille: lista z kontekstu systemowego oraz `ls .claude/skills/ ~/.claude/skills/` (skill utworzony w innej sesji może nie być na liście). Gdy któryś pokrywa się zakresem, zaproponuj **aktualizację** zamiast nowego skilla. Przeczytaj wtedy jego SKILL.md i proponuj tylko to, czego w nim brakuje. Typowy przypadek: skill zbudowano w analizowanej sesji, a wartościowe są błędy z późniejszego użycia, czyli nowe pułapki. Jeśli sesja kończy się na zbudowaniu skilla i nie było późniejszego użycia, wynik to "nic" (ewentualnie z propozycją do CLAUDE.md), chyba że w SKILL.md brakuje kroku, który w sesji okazał się potrzebny.
4. Miejsce zapisu:
   - **projekt** (`.claude/skills/<nazwa>/`), gdy skill używa plików, narzędzi lub reguł tego projektu,
   - **globalnie** (`~/.claude/skills/<nazwa>/`), gdy działa w każdym projekcie.

Jeśli nie ma kandydata na skill (także gdy istniejący skill nie wymaga zmian), pomiń kroki 3-6 i odpowiedz w tym formacie:

```
Wynik: nic do utrwalenia jako skill
Dlaczego: <1-2 zdania>
Do CLAUDE.md (propozycja): <plik i linia albo "brak">
Ograniczenia materiału: <jeśli były>
```

Jeśli jest propozycja do CLAUDE.md, zapytaj o akceptację i wprowadź ją dopiero po zgodzie. Potem zakończ.

**Przypadek graniczny - nie rozstrzygaj sam.** Gdy procedura powtórzy się na innym wejściu, ale wykonano ją tylko raz albo częściowo pokrywają ją istniejące skille, zapytaj użytkownika:

```
Kandydat graniczny: <nazwa> - <co by robił, 1 zdanie>
Za: <co oszczędzi przy następnym razie>
Przeciw: <pokrycie przez skill X / jednorazowość>
Tworzyć skill? (tak -> pokażę propozycję z kroku 3 / nie -> wynik "nic")
```

Błąd w rozmowie nie oznacza automatycznie skilla. Błąd bez powtarzalnej procedury to "nic" plus ewentualna linia do CLAUDE.md.

## Krok 3. Propozycja - STOP

Pokaż użytkownikowi i czekaj na akceptację. Wypisz najwyżej 8 najważniejszych pułapek, a resztę policz ("+N drobnych"):

```
Nazwa: <nazwa>  |  Nowy / aktualizacja: <...>  |  Miejsce: <projekt/globalnie> - <dlaczego>
Opis (description): <kiedy użyć>  (przy aktualizacji: "bez zmian" albo nowa wersja)
Parametry: <...>
Kroki: 1. ... 2. ...  (przy aktualizacji: tylko zmiany - dodane / zmienione / usunięte)
Skrypty: <plik> - <co robi> - <nowy / przenieść / skopiować / zaktualizować / bez zmian>
Pułapki: <objaw -> przyczyna -> rozwiązanie>
Do CLAUDE.md (propozycja): <...>
Ograniczenia materiału: <np. praca subagentów niewidoczna, rozmowa po kompakcji>
Odrzucone jako jednorazowe: <...>
```

## Krok 4. Budowa

1. Przeczytaj `~/.claude/skills/utrwal-skill/references/szablon.md` i według niego napisz SKILL.md (przy aktualizacji: dopisz tylko zaakceptowane zmiany, nie przepisuj całości).
2. Skrypty: zaczynaj od kodu, który w rozmowie zadziałał. Zamień konkretne wartości na argumenty, ścieżki bezwzględne na względne, a zależności dopisz do `scripts/requirements.txt`. Każdy skrypt uruchom raz (`--help` albo przebieg na przykładzie z rozmowy). Jeśli pełne uruchomienie jest niemożliwe (brak sieci, brak zależności), zrób przynajmniej kontrolę składni (`python3 -m py_compile`, `node --check`) i wpisz to do podsumowania jako niesprawdzone.
3. Zaakceptowane zmiany w CLAUDE.md wprowadź teraz.

## Krok 5. Weryfikacja

1. Przejdź `~/.claude/skills/utrwal-skill/references/lista_kontrolna.md` punkt po punkcie i popraw braki.
2. **Test suchy:** uruchom subagenta (narzędzie Agent) bez kontekstu rozmowy. Jako inne wejście wybierz, jeśli się da, prawdziwe pliki z projektu lub dysku (np. inną spółkę, inny dokument), żeby tester mógł sprawdzić dopasowanie do realnych danych. Treść zlecenia:
   > Przeczytaj `<ścieżka>/SKILL.md` (i pliki, do których odsyła). Wyobraź sobie, że użytkownik wywołał go z wejściem `<INNE wejście niż w rozmowie>`. NIE uruchamiaj żadnych skryptów ani komend zmieniających pliki - możesz tylko czytać. Opisz krok po kroku, co byś zrobił, i wypisz: miejsca niejasne, brakujące informacje, wartości, które wyglądają na zaszyte z jednego przypadku, oraz kroki, których nie dałoby się wykonać.
3. Popraw skill na podstawie raportu (jedna runda). Niejasności, których nie da się rozstrzygnąć bez użytkownika, przenieś do podsumowania.

## Krok 6. Podsumowanie

- Co powstało i gdzie (lista plików), nowy skill czy aktualizacja.
- Wynik testu suchego: co poprawiono, co zostało otwarte (niejasności do rozstrzygnięcia przez użytkownika jako pytania).
- Czego test nie sprawdził (skrypty nie były uruchamiane na nowym wejściu).
- Propozycja testu na żywo: konkretna komenda, np. `/<nazwa> <inne wejście>` w nowej sesji.
- Pozostali kandydaci na skille i propozycje do CLAUDE.md, jeśli były.

## Pułapki

| Objaw | Przyczyna | Co zrobić |
|-------|-----------|-----------|
| Skill działa tylko dla przykładu z rozmowy | zaszyte wartości (ticker, nazwa, data) | zamień na `$ARGUMENTS` i argumenty skryptów |
| Model wykonuje sam opis zamiast skilla | `description` streszcza kroki | w opisie tylko warunki użycia |
| Skrypty w projekcie i w skillu się rozjeżdżają | dwie kopie tego samego kodu | przenieś do jednego miejsca albo zapisz w pułapkach, że trzeba aktualizować razem |
| Brakuje kroków z wcześniejszej pracy | umiejętność powstała w kilku sesjach albo przed `/clear` | `--lista`, potem `--sesja ID1 ID2` |
| Skrypt nie znajduje sesji | zły id albo pusta `CLAUDE_CODE_SESSION_ID` (np. w subagencie) | podaj `--sesja` z `--lista` |
| W skrócie brakuje treści wymagań | domyślne obcięcie wpisów | ponów z `--max-znakow 2000` albo czytaj pliki projektu |
| `--lista` nie pokazuje starszych sesji | projekt przeniesiono, a stare sesje są pod starą ścieżką | skrypt dołącza foldery z tymi samymi 3 ostatnimi członami ścieżki; gdy to nie wystarcza, podaj `--projekt <stara ścieżka>` |
| Kod z sesji był w scratchpadzie i go nie widać | skrót pomija treść plików, a scratchpad jest poza projektem | `--sesja ID --pliki`, a potem `--pliki <nazwa>` |
