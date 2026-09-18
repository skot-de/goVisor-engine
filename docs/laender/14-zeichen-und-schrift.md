# 14 · Zeichen und Schrift — was ausserhalb von DACH zerbricht

> Gehört zu Tor 3 und 5. Dieses Kapitel entstand am 2026-08-23 beim Durchspielen eines
> neuen Landes. Innerhalb von DACH fällt nichts davon auf; beim ersten Land mit anderen
> Buchstaben fällt **alles** davon auf.

## Der Befund

Die Wortfaltung in `scripts/region_ableiten.py` kennt genau vier Sonderzeichen (ä, ö, ü, ß)
und behandelt danach **jedes** nicht-ASCII-Zeichen als Worttrenner:

```python
s = s.lower()
for a, b in (("ä","ae"), ("ö","oe"), ("ü","ue"), ("ß","ss")):
    s = s.replace(a, b)
return [w for w in re.split(r"[^a-z]+", s) if w]
```

Gemessen, was dabei herauskommt:

```
Kraków          → ['krak', 'w']        ó wird zum Trenner, das Wort zerfällt
Gdańsk          → ['gda', 'sk']
Łódź            → ['d']                von vier Buchstaben bleibt einer
Plzeň           → ['plze']
Ústí nad Labem  → ['st', 'nad', 'labem']
Zürich          → ['zuerich']          ✓ DACH funktioniert
```

**Für Polen wäre die Regionsableitung wertlos**, und zwar ohne eine einzige Fehlermeldung:
`Łódź` würde als „d" gesucht, nichts gefunden, das Feld bliebe leer — und ein leeres Feld
sieht aus wie eine Quelle, die nichts hergibt.

## ⚠ Es sind ZWEI Faltungen, nicht eine (nachgemessen 2026-09-18)

Hier stand bis heute, der Dublettenwall trage „dieselbe Faltung". Das stimmt nicht.
`govisor/dedupe.worte()` arbeitet ganz anders: `[a-zà-ÿA-ZÀ-Þ0-9]{3,}` — ein
**Latin-1-Bereich**, der Akzente BEHÄLT und alles darüber als Trenner nimmt. Gemessen:

| Ort | `dedupe.worte()` | `region_ableiten._worte()` |
|-----|------------------|----------------------------|
| Łódź | `[]` | `['d']` |
| Gdańsk | `['gda']` | `['gda', 'sk']` |
| Kraków | `['kraków']` | `['krak', 'w']` |
| Częstochowa | `['stochowa']` | `['cz', 'stochowa']` |
| Ústí nad Labem | `['labem','nad','ústí']` | `['st','nad','labem']` |
| Zürich | `['zürich']` | `['zuerich']` |

Die letzte Zeile ist die wichtigste: **die beiden weichen schon in DACH voneinander ab.**
Wer eine der Faltungen repariert, hat die andere nicht mit repariert, und wer sie für
identisch hält, prüft die falsche.

### Der Blindgänger, den das freilegt

`dedupe._wiederholung()` (seit 2026-09-18) verlangt **identische Wortmengen**, um zwei
Bekanntmachungen derselben Quelle als Wiederholung desselben Vorgangs zu werten. Ein Ort,
der bei der Faltung spurlos verschwindet, trägt zur Unterscheidung nichts bei:

```
Przebudowa drogi gminnej w miejscowości Łódź    → ['drogi','gminnej','miejscowo','przebudowa']
Przebudowa drogi gminnej w miejscowości Łomża   → ['drogi','gminnej','miejscowo','przebudowa']

_wiederholung()  →  True
```

Zwei **verschiedene** Strassenbauvergaben derselben Gemeinde, gleiche CPV, kleine Gruppe.
Eine davon würde in `gold.py` aus der ausgelieferten Liste ausgeschlossen. Kein Fehler,
keine Meldung, ein Lead weniger.

⚠ **Das Netz `MIN_WORTE = 3` fängt das NICHT.** Es verwirft nur Titel mit weniger als drei
Wörtern; hier bleiben vier übrig. Es schützt gegen den offensichtlichen Fall (`Łódź` allein
ergibt `[]`) und gerade nicht gegen den gefährlichen. Umgekehrt ist auch die Trennung im
Beispiel `Łódź` gegen `Gdańsk` weiter oben **Zufall**: sie unterscheiden sich nur, weil von
`Gdańsk` das Bruchstück `gda` übrig bleibt und von `Łódź` nichts.

Im Ist-Zustand richtet das keinen Schaden an: Polen steht in `BEWUSST_OHNE_GOLD`, die
Firewall läuft nur über DACH. Es ist ein Blindgänger, kein Brand — und er liegt genau auf
dem Weg, den der erste Nicht-DACH-Connector nimmt. Wächter:
`tests/test_zeichen_faltung.py` wird rot, sobald ein Land ausserhalb DACH in
`laender.AKTIV` steht, ohne dass die Faltung seine Buchstaben kennt.

## Die zweite Faltung ist besser, aber nicht vollständig

`govisor/entities.strip_accents()` arbeitet über NFKD und entfernt kombinierende Zeichen:

```
Kraków  → 'krakow'   ✓        Plzeň  → 'plzen'   ✓
Gdańsk  → 'gdansk'   ✓        Ústí   → 'usti'    ✓
Łódź    → 'łodz'     ✗        das Ł bleibt stehen
```

Der Grund: **`Ł` ist ein eigener Buchstabe**, keine Basis mit Akzent — NFKD zerlegt ihn
nicht. Dieselbe Klasse:

| Zeichen | Sprache | NFKD hilft |
|---------|---------|------------|
| Ł ł | Polnisch | nein |
| Ø ø | Dänisch, Norwegisch | nein |
| Đ đ | Kroatisch, Serbisch | nein |
| Þ þ, Ð ð | Isländisch | nein |
| ı (punktloses i) | Türkisch | nein |
| Æ æ, Œ œ | Dänisch, Französisch | nein |
| ó ń ě ú ą | die meisten | **ja** |

## Was für ein neues Land zu tun ist

1. **Die Wortfaltung um die Buchstaben des Landes erweitern**, bevor irgendetwas gemessen
   wird. Andernfalls sind alle Messungen dieses Kapitels und der Kapitel 04 und 07 falsch.
2. **Nicht nur ä/ö/ü/ß-Stil ersetzen, sondern über NFKD gehen** und die „eigener
   Buchstabe"-Klasse per Tabelle nachziehen (`ł→l`, `ø→o`, `đ→d`, `þ→th`, `ð→d`, `ı→i`,
   `æ→ae`, `œ→oe`).
3. **Den Regex-Trenner erweitern.** `[^a-z]+` verwirft alles Nicht-ASCII; nach der Faltung
   ist das richtig, **vorher** ist es zerstörerisch. Reihenfolge: erst falten, dann trennen.
4. **Gegenprobe an echten Ortsnamen des Landes**, nicht an Kunstbeispielen. Die
   geonames-Datei des Landes liefert sie frei Haus.

## Nicht-lateinische Schriften

Bulgarien und Griechenland schreiben kyrillisch bzw. griechisch. Dann greift keine
Akzentfaltung mehr, sondern es braucht eine **Transliteration** — oder man verzichtet auf
die namensbasierten Wege (Ortsname im Käufernamen, Namensvergleich im Dublettenwall) und
stützt sich auf Kennungen und NUTS.

Das ist eine Architekturentscheidung und keine Kleinigkeit. Sie gehört **vor** den ersten
Connector, nicht danach.

## Kodierung der Quelle

Nicht verwechseln mit der Faltung: manche Quellen liefern kein UTF-8. Die deutsche
Historie brauchte dafür `flatten.decode_text()` mit cp1252-Rückfall — damals wurden 11.448
Bekanntmachungen wurden so verlustfrei zurückgeholt und rund 115.000 `�`-Zeilen
verschwanden.

**Für jede neue Quelle einmal prüfen**, ob die Zeichen ankommen. Ein `�` im Titel
überlebt sonst bis ins Frontend.

## Sprachcodes

ISO-639-1, klein (`govisor/languages.py`). Wer eine Quelle anbindet, die `deu`/`ger`/`DE`
liefert, normalisiert **beim Parsen**, nicht später — sonst stehen drei Schreibweisen
derselben Sprache in `lead_text` und die Oberfläche zeigt drei Knöpfe für eine Fassung.

## Prüfung für die Abnahme

```python
from govisor.entities import strip_accents
for ort in ("<fünf echte Ortsnamen des Landes>",):
    print(ort, "→", strip_accents(ort.lower()))
```

Bleibt ein nicht-ASCII-Zeichen stehen, fehlt es in der Tabelle. Zerfällt ein Wort in
Bruchstücke, ist der Trenner vor der Faltung gelaufen.
