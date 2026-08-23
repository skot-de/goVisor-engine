# 04 · Dublettenwall — eine Prüfung für alle Quellen

> Tor 3. Fällt, wenn der Wall mit dem **Locale des Landes** läuft, die Belegklassen
> gemessen sind und der Selbsttest unter 15 % Widerspruch liegt.

## Das Grundgesetz: markieren statt löschen

Der Wall (`govisor/dedupe.py`) **entfernt nichts**. Er schreibt Paare nach
`gold/<LAND>/notice_duplicates.parquet` und überlässt jedem Verbraucher die Entscheidung.
Wer löscht, kann nicht mehr nachsehen, ob er recht hatte.

```bash
python3 -m govisor.dedupe --country XX --ab-jahr 2004 --alle-arten --anreichern
```

⚠ **Genau diese Parameter.** Der Nachtlauf verwendet sie; ein Lauf mit `--ab-jahr 2026`
ohne `--alle-arten` schreibt dieselbe Datei **schmaler** und niemand sieht es. Selbst
gemacht am 2026-08-23 und erst beim Vergleich der Beleglage bemerkt.

Sonntags läuft die volle Historie, sonst ein rollendes Fenster von 190 Tagen
(`--fenster-tage 190`).

## ⚠ Das Locale des Landes aktivieren

`normalize_company()` liest das **aktive** Locale (`govisor/locales.py`, vorbelegt auf DE).
`dedupe.py` reichte `country` jahrelang durch, ohne es je zu setzen — der Wall verglich
österreichische und Schweizer Käufernamen mit **deutschen Rechtsformen**.

```python
_locales.use(country)     # gehört in finde(), nicht in die CLI
```

In `finde()` und nicht in die CLI, weil die Funktion auch aus Skripten kommt
(`build_dach_gold.py`); dort hätte die CLI-Variante lautlos gefehlt.

Gemessener Gewinn allein durch das Umstellen: **AT +31 Paare** bekamen einen Käuferbeleg.

## Die Belegklassen — und warum die schwachen absichtlich schwach sind

Jedes Paar bekommt eine **Beleglage**, keine Schwelle:

| Beleg | Bedeutung | Verwendbar für |
|-------|-----------|----------------|
| `kaeufer_und_titel` | Titel enthalten **und** derselbe Käufer | Anreicherung, Ausblenden |
| `nur_titel` | Titel enthalten, anderer Käufer | nur ansehen |
| `nur_titel_kurz` | wie oben, aber **kurzer** Titel (< 6 Wörter) | nur ansehen |
| `geschwister` | **beide** Titel tragen eigene Wörter | nur ansehen |

Die beiden schwachen Klassen sind kein Versäumnis:

- **`nur_titel_kurz`**: „Sanitär, Lüftung, Heizung" steckt vollständig in *jedem* längeren
  Titel desselben Gewerks. Enthaltung 1,0 ist dort **kein** Identitätsbeleg. Gemessen
  hätte eine Lockerung auf „Titel identisch genügt" die Anreicherung von 28 auf 393 Werte
  gehoben — **und dabei fremde Fristen übernommen**.
- **`geschwister`**: der beidseitige Eimer enthält neben echten Losen auch völlig
  unverwandte Vergaben desselben Käufers („Sanierung Freibad" gegen „Neubau Schulmensa",
  „Mittagessen Regelschule" gegen „Kopierpapier").

**Die Anreicherung fasst nur `kaeufer_und_titel` an.** Alles andere steht in der Tabelle
und wird nicht verwendet. Das ist die Regel, an der man nicht dreht.

## Käufergleichheit: zwei Wege

```python
def _kaeufer_gleich(s, t):
    if s["buyer"] and s["buyer"] == t["buyer"]:      # Weg 1: Normalform des Namens
        return True
    if not (s["bid"] and s["bid"] == t["bid"]):      # Weg 2: amtliche Kennung …
        return False
    a, b = set(s["buyer"].split()), set(t["buyer"].split())
    return bool(a and b and (a <= b or b <= a))      # … UND kein Namenswiderspruch
```

**Weg 2 ist nötig**, weil dieselbe Stelle je Quelle völlig anders geschrieben wird: TED
meldet „ASFINAG Autobahnen- und Schnellstrassen-Finanzierungs-AG", offenevergaben.at den
ausgeschriebenen Namen ohne das Kürzel. Keine Normalisierung führt diese beiden zusammen.

⚠ **Die Kennung allein reicht NICHT, und das ist der teuer gemessene Teil.** Die
österreichischen GLN sind **Dachkennungen**:

```
9110027589349   →  ÖGK Landesstelle Wien, Steiermark UND Kärnten
FN92191a        →  60 verschiedene ASFINAG-Namen
9110002556748   →  104 verschiedene Namen (Land Niederösterreich)
```

Wer auf Kennungsgleichheit allein merged, wirft die Landesstelle Wien mit der steirischen
zusammen — bei kurzen Gewerketiteln passiert das sofort. Deshalb: Kennung **und** die
Namen dürfen sich nicht widersprechen (einer ist Teilmenge des anderen). Gemessen an AT:
**+147 Paare belegt, 1.055 widersprüchliche bleiben bewusst aussen vor.**

## Müllkennungen

```python
_KENNUNG_MUELL = {"0", "1", "at", "de", "ch", "n a", "na", "keine", "999999"}
```

Gemessen an AT: „0" steht bei **510** verschiedenen Käufern, „1" bei 178, „AT" bei 133.
Zusätzlich gilt eine Mindestlänge von 6 Zeichen. Wer sie als Gleichheitsbeleg nimmt,
verschmilzt fremde Häuser.

## Weitere eingebaute Sperren

- **Zahlen-Sperre.** Losnummern und Aktenzeichen trennen Vorgänge klar; wer sie ignoriert,
  wirft „Los 1" und „Los 2" zusammen.
- **Geschwister-Sperre.** Siehe oben.
- **Quellenrang.** `QUELLEN_RANG` entscheidet, welche Seite Master wird: die reichere
  Quelle, bei Gleichstand der frühere Satz.

## Ein Ausschluss ist sicher

**DTVP** ist der eine Fall, bei dem ein Ausschluss ohne Beleglage zulässig ist.

## Erwartungswerte für ein neues Land

Gemessen DACH (2026-08-23), Kreuzquellen-Paare:

```
AT   kaeufer_und_titel 65.618 · geschwister 57.812 · nur_titel 3.102 · kurz 2.088
CH   kaeufer_und_titel 14.805 · nur_titel_kurz 2.181 · geschwister 1.697 · nur_titel 128
```

**Sichtbar bleibende Paare sind normal.** Von 18.428 offenen Leads blieben 672 Paare
beidseitig sichtbar (DE 647, CH 20, AT 5) — und **kein einziges** in der starken Klasse.
Der Wall hat genau die entfernt, bei denen er sicher ist.

⚠ Und man prüfe, was man sieht, bevor man es repariert: die sichtbaren CH-Paare waren
fast alle **Lose eines Projekts** („Réaménagement du Centre sportif" gegen „CFC 211
Travaux", „CFC 222 Ferblanterie"). Die sollen getrennt bleiben.

## Sprachübergreifende Dubletten — meist ein Phantom

Naheliegende Hypothese: mehrsprachige Länder veröffentlichen dieselbe Vergabe zweimal.
**Für die Schweiz widerlegt.** simap veröffentlicht einsprachig je Satz, aber mit allen
Fassungen **im** Satz; alle 164 mehrsprachigen CH-Leads stammten aus TED, keiner aus simap.

Der Wall könnte solche Paare ohnehin nicht finden (er vergleicht Wörter, und
„Assainissement" hat nichts mit „Sanierung" zu tun). Wer die Hypothese prüfen will, braucht
einen anderen Test: gleicher Käufer + gleiche Frist + gleicher CPV bei verschiedenen Titeln.
Gemessen CH: 54.495 solcher Kandidaten, **dominiert von Losen**, nicht von Sprachvarianten.

## Ergebnis dieses Kapitels

- `gold/<LAND>/notice_duplicates.parquet` existiert
- Beleglage gemessen und abgelegt
- Locale des Landes ist aktiviert (Test: `test_dedupe_aktiviert_das_locale_des_landes`)
- die sichtbar gebliebenen Paare wurden **angesehen**, nicht nur gezählt
