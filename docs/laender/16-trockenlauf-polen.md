# 16 · Trockenlauf Polen — die Bibel am echten Fall

> Kein Onboarding, sondern ein **Test der Anleitung**. Durchgeführt am 2026-08-23 an
> Polen, weil dort 326.485 Bekanntmachungen in Silber liegen und niemand mehr hinsah.
> Was hier steht, ist der Befund — und die Stellen, an denen die Bibel gehalten hat.

## Ausgangslage

```
Silber      326.485 Sätze · 2023-07-03 bis 2026-06-29 · 143.808 Zuschläge
Gold        nichts
Registry    „TED Polen" stand auf `candidate` — also „nie angefasst"
Locale      kein PL-Profil (nur DE, AT, CH, FR)
geonames    kein PL.txt
Eintragung  in KEINER `LAENDER`-Liste ausser der Baustellen-Zeile der Sonde
```

Die Quelle ist **TED allein**. Die nationale Pflichtveröffentlichung — das *Biuletyn
Zamówień Publicznych*, laut [Kapitel 01](01-quellenlandschaft.md) Polens zentrale
Unterschwellenquelle und einer der Gründe, warum Polen ein günstiger Markteintritt wäre —
ist nicht angebunden. Die Fonds-Ebene (`bazakonkurencyjnosci.funduszeeuropejskie.gov.pl`)
ebenso wenig.

## Die zwei Vorab-Kapitel greifen beide

**[13 Währung](13-waehrung-und-werte.md):** PLN 148.850 gegen EUR 2.067. Ohne Umrechnung
verlöre Polen jede wertbasierte Kennzahl — genau wie die Schweiz heute.

**[14 Zeichensatz](14-zeichen-und-schrift.md):** an echten polnischen Käufernamen gemessen,
und schlimmer als die synthetischen Beispiele vermuten liessen. Die Namen **zerfallen**:

```
Zarząd Dróg Wojewódzkich  →  ['zarz','d','dr','g','wojew','dzkich']
Śląski Uniwersytet        →  ['l','ski','uniwersytet']
Państwa                   →  ['pa','stwa']
```

Aus jedem Namen werden zwei bis drei Bruchstücke. Das trifft die Wortmengen des
Dublettenwalls **und** die Ortsnamen-Ableitung. `strip_accents` kommt besser durch
(`zarzad drog wojewodzkich`), scheitert aber wie vorhergesagt an **Ł**: `zakład` bleibt
`zakład`.

## Was gut aussieht

Die Feldabdeckung ist besser als in Österreich:

```
schema_gen   Sätze     Titel  CPV  Frist  NUTS  Beschreibung
eforms     275.640      100%  100%   54%   88%          100%
legacy      50.845      100%  100%   27%  100%           94%
```

Titel, CPV und Beschreibung sind vollständig, NUTS bei 88–100 %. Nur die Frist ist dünn —
dieselbe Lage wie überall (s. [Kapitel 10](10-abnahme-und-messung.md)).

## Der Fund, den der Trockenlauf ausgelöst hat

Die Registry sagte `candidate` — „Machbarkeit belegt, Connector geplant". Bei 326.485
Sätzen in Silber ist das schlicht falsch. Die Ursache war kein Tippfehler, sondern
Bauart: **alle EU-Länder bekamen pauschal `candidate`**, weil die Einträge automatisch
erzeugt wurden.

Damit konnte die Registry nicht unterscheiden zwischen „nie angefasst" und „ingestiert und
liegengelassen" — und derselbe Fehler steckte in einem **von Hand** geschriebenen Eintrag:
`ted-at` stand auf `prepared`, obwohl Österreich seit Wochen täglich durch die Kette läuft.

**Seit 2026-08-23 wird der Status der `ted-*`-Landeseinträge aus der Datenlage abgeleitet:**

```
Gold liegt      → live
nur Silber      → prepared   (angefangen und liegengeblieben)
nichts          → candidate
```

Portale und nationale Quellen behalten ihren kuratierten Status: dort sagt die Datenlage
nichts über den Anbindungsstand.

⚠ Was weiterhin hinterherhinkt und bewusst so bleibt: `govisor.dtvp` läuft im Tageslauf und
steht in **keinem** Eintrag; `atverg` steht auf `prepared`, obwohl `ingest-atverg` täglich
läuft. Das sind Produktaussagen über fremde Quellen, keine Ableitung.

## Was das über die Bibel sagt

Sie hat gehalten, wo sie etwas versprach:

- Die Reihenfolge stimmte — 13 und 14 gehören vor die erste Messung, und beide griffen.
- Kapitel 14 sagte die Zerlegung voraus, inklusive des `Ł`-Sonderfalls.
- [Kapitel 15](15-eintragungsliste.md) listete genau die Stellen auf, an denen Polen fehlt.
- Kapitel 01 nannte das Biuletyn als Polens zentrale Quelle — und deshalb fiel auf, dass
  nur TED angebunden ist.

Sie hat **nicht** vorhergesagt, dass der Registry-Status selbst unzuverlässig ist. Das kam
aus dem Vergleich zwischen dem, was sie zu prüfen verlangt, und dem, was die Daten sagen.

> **Die Lehre für den nächsten Trockenlauf:** was die Bibel als Prüfschritt nennt, prüft
> man gegen die DATEN, nicht gegen das Feld, das die Antwort behauptet. Genau so ist auch
> `has_documents` aufgeflogen (s. [Kapitel 03](03-input-dokumente.md)).

## Wenn Polen wirklich onboardet werden soll

In dieser Reihenfolge, alles offen:

1. **Zeichensatz** (Kapitel 14) — vor jeder Messung, sonst sind alle Zahlen falsch.
2. **Währung** (Kapitel 13) — PLN-Umrechnung mit Kursreihe, sonst keine Wert-Kennzahlen.
3. **Locale-Profil** — polnische Rechtsformen (`sp. z o.o.`, `S.A.`, `spółka`).
4. **geonames PL.txt** + NUTS-Ebene entscheiden (PL: Woiwodschaft = NUTS-2).
5. **Gold** über `build_dach_gold.py`, dann [Kapitel 05](05-gold-kette.md) und
   [Kapitel 06](06-cross-verdrahtung.md) abarbeiten.
6. **Biuletyn Zamówień Publicznych** als zweite Ebene prüfen — laut Kapitel 01 der
   eigentliche Hebel.
