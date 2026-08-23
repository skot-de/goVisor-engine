# 00 · Reihenfolge und Tore

> Teil der [Länder-Bibel](../land-onboarding.md). Lies dieses Kapitel zuerst, auch wenn
> du nur eine Kleinigkeit nachbessern willst.

## Warum es Tore gibt und keine Checkliste

Eine Checkliste kann man abhaken, ohne dass etwas funktioniert. Österreich galt sechs
Wochen lang als „fertig"; beim Nachmessen am 2026-08-14 standen Bindefrist, Bürgschaft,
Nebenangebote und Lose bei **0 %**, und bei 57 % der Vergaben fehlte sogar ein Link zur
Quelle. Kein einziger dieser Punkte war ein Denkfehler. Es waren durchweg Reste einer
Funktion, die für Deutschland gebaut und für den Rest vergessen wurde.

Der Grund, warum das niemandem auffiel, steht in einem Satz:

> **Ein leeres Feld sieht aus wie eine Quelle, die nichts hergibt.**

Deshalb arbeitet dieses Vorgehen mit **Toren**: jedes hat eine Zahl, die man messen muss,
und ein Tor fällt erst, wenn die Zahl stimmt. „Läuft durch" ist kein Tor.

## Die sechs Tore

| # | Tor | Fällt, wenn … | Kapitel |
|---|-----|---------------|---------|
| 1 | **Quellen bekannt** | alle drei Vergabeebenen geprüft und je Ebene entschieden: Quelle, Konto nötig?, API vorhanden? | [01](01-quellenlandschaft.md) |
| 2 | **Ausschreibungen fliessen** | Bronze→Silber gebaut, Feldabdeckung je Quelle gemessen, IDs kanonisch | [02](02-input-ausschreibungen.md) |
| 3 | **Dubletten erkannt** | Wall läuft mit dem **Locale des Landes**, Belegklassen gemessen, Selbsttest unter 15 % | [04](04-dublettenwall.md) |
| 4 | **Gold vollständig** | jede country-fähige Tabelle wird auch für dieses Land gebaut (`pruefe_verdrahtung.py` sauber) | [05](05-gold-kette.md) |
| 5 | **Frontend zeigt es** | keine Kennzahl liegt in Gold und fehlt in der Oberfläche; Feldabdeckung je Land nebeneinander gemessen | [06](06-cross-verdrahtung.md) |
| 6 | **Dokumente** | Portale gemessen, Ausbeute je Portal bekannt, Sperrtypen klassifiziert | [03](03-input-dokumente.md) |

Tor 6 steht bewusst hinten: **AT und CH haben bis heute 0 % Dokumentabdeckung** und sind
trotzdem produktiv. Ein Land ohne Dokumente ist ein halbes Land, kein unbrauchbares.

## Die drei Fragen, die man an JEDE Zahl stellt

Diese Reihenfolge ist der Kern der ganzen Bibel. Wer bei Frage 2 aufhört, liefert
Kennzahlen aus, die niemandem nützen.

1. **Gibt es das Feld?** — steht es im Schema, wird es geparst?
2. **Ist es gefüllt?** — Füllgrad in Prozent, je Quelle getrennt.
3. **Trägt es Inhalt?** — und das ist die Frage, die regelmässig vergessen wird.

Drei gemessene Beispiele, warum Frage 3 zählt:

- Schweizer **Zuschlagskriterien**: 13.656 Zeilen, 100 % „gefüllt". 29 % davon tragen als
  Namen das Wort „Zuschlagskriterien" und **gar kein Gewicht**. Ein Etikett, kein Kriterium.
- Schweizer **Eignungsanforderungen**: 595 Zeilen, 100 % gefüllt, **595 davon** lauten
  sinngemäss „Plus d'informations dans la publication officielle sur simap.ch". Ein
  Verweis, kein Inhalt.
- Österreichische **Regionen** (vor dem 2026-08-23): 36 % Abdeckung, und jede einzelne
  Angabe lautete „Ostösterreich", „Südösterreich" oder „Westösterreich". Formal befüllt,
  als Filter wertlos — „Ostösterreich" umfasst Burgenland, Niederösterreich und Wien.

## Was „fertig" heisst

Ein Land ist fertig, wenn die Abnahme aus [Kapitel 10](10-abnahme-und-messung.md)
durchläuft **und** die Verdrahtungsprüfung schweigt:

```bash
python3 scripts/pruefe_verdrahtung.py --offen
```

Alles andere ist ein Zwischenstand, und ein Zwischenstand gehört als solcher benannt —
in `docs/quellen-landkarte.md` und in der Auto-Memory, nicht im Kopf.

## Reihenfolge der Arbeit

```
01 Quellen  →  02 Ausschreibungen  →  04 Dubletten  →  05 Gold  →  06 Frontend
                                                                      │
                        07 Geo  ·  08 Entitäten  ·  09 i18n  ─────────┤
                                                                      ▼
                                              10 Abnahme  →  11 Betrieb
                        03 Dokumente (jederzeit, blockiert nichts)
```

**Nicht abkürzen.** Wer Gold baut, bevor der Dublettenwall lief, bekommt Kennzahlen über
einen Bestand, der dieselbe Vergabe mehrfach zählt. Wer das Frontend verdrahtet, bevor
Gold vollständig ist, baut gegen Tabellen, die es noch nicht gibt — und merkt später
nicht, dass sie inzwischen da sind.
