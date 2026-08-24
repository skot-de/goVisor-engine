# Ein neues Land aufnehmen

**Das ist die Nabe.** Die Einzelheiten stehen in `docs/laender/`; dieses Dokument sagt, was
zu tun ist, in welcher Reihenfolge, und woran man merkt, dass man fertig ist.

> **goVisor ist EU-weit geplant. Deutschland ist der Testfall, nicht der Zielmarkt.**
> Wer ein Feature nur für DE baut, hat es nicht fertig gebaut, sondern angefangen.

## Warum es dieses Dokument gibt

Österreich galt sechs Wochen lang als fertig. Beim Nachmessen am 2026-08-14 standen
Bindefrist, Bürgschaft, Nebenangebote und Lose bei **0 %**, bei 57 % der Vergaben fehlte
ein Link zur Quelle, und die Schweiz lag bei 51 % — während die Daten vollständig in
Silber lagen.

Keiner dieser Fehler war ein Denkfehler. Es waren durchweg Reste einer Funktion, die für
Deutschland gebaut und für den Rest vergessen wurde. Und sie fielen nicht auf, weil:

> **Ein leeres Feld bleibt leer, statt zu scheitern — und sieht aus wie eine Quelle, die
> nichts hergibt.**

## Die Kapitel

| | Kapitel | Beantwortet |
|---|---------|-------------|
| **00** | [Reihenfolge und Tore](laender/00-reihenfolge-und-tore.md) | Was heisst „fertig"? Sechs Tore, drei Fragen an jede Zahl. |
| **01** | [Quellenlandschaft](laender/01-quellenlandschaft.md) | Drei Vergabeebenen, API vor Abgriff, Recht, Registry-Status. |
| **02** | [Input Ausschreibungen](laender/02-input-ausschreibungen.md) | Bronze→Silber, Parser, IDs, Sprachfassungen, Attribute. |
| **03** | [Input Dokumente](laender/03-input-dokumente.md) | Portale, Abrufwarteschlange, Sperrtypen, Doktypen. **Enthält den Prüfgang für einen Abrufer** — fünf von fünf Statusmeldungen hielten der Prüfung nicht stand. |
| **04** | [Dublettenwall](laender/04-dublettenwall.md) | Belegklassen, Locale je Land, Kennung vs. Name. |
| **05** | [Gold-Kette](laender/05-gold-kette.md) | Builder-Reihenfolge, Verdrahtungsprüfung, bewusste Lücken. |
| **06** | [Cross-Verdrahtung](laender/06-cross-verdrahtung.md) | `_union`, Land im Schlüssel, Silber-Globs, Determinismus. |
| **07** | [Geo und Regionen](laender/07-geo-und-regionen.md) | NUTS-Ebene je Land, Ableitung, Ortsnamen-Fallen. |
| **08** | [Entitäten und Locale](laender/08-entitaeten-und-locale.md) | Rechtsformen, `normalize_company`, amtliche Kennungen. |
| **09** | [Frontend und Sprache](laender/09-frontend-und-i18n.md) | Vertrag englisch, `tk()`, Herkunft anzeigen. |
| **10** | [Abnahme und Messung](laender/10-abnahme-und-messung.md) | Die Zahlen, die man verlangen muss. |
| **11** | [Betrieb](laender/11-betrieb.md) | Nachtlauf, Sperren, launchd, Geldwache. |
| **12** | [Fallenkatalog](laender/12-fallenkatalog.md) | Jede Falle mit ihrer Messung. |
| **13** | [Währung und Werte](laender/13-waehrung-und-werte.md) | ⚠ **Zuerst lesen, wenn das Land nicht in Euro rechnet.** |
| **14** | [Zeichen und Schrift](laender/14-zeichen-und-schrift.md) | ⚠ **Zuerst lesen, wenn das Land andere Buchstaben hat.** |
| **15** | [Eintragungsliste](laender/15-eintragungsliste.md) | Jede Datei, in der ein Land bekannt gemacht wird. |
| **16** | [Trockenlauf Polen](laender/16-trockenlauf-polen.md) | Die Bibel am echten Fall geprüft — was hielt und was fehlte. |
| **17** | [Eine Quelle anbinden](laender/17-quelle-anbinden.md) | Das **Wie**: Portale finden, Ausschreibungs- und Dokument-Connector bauen. |

## Der Ablauf in einem Bild

```
        ┌─ 13 Währung   ⚠ wenn nicht Euro
VORAB ──┤                                     … beide VOR der ersten Messung,
        └─ 14 Schrift   ⚠ wenn andere Buchstaben   sonst misst man Unsinn

01 Quellen  →  02 Ausschreibungen  →  04 Dubletten  →  05 Gold  →  06 Frontend
                                                                      │
                        07 Geo  ·  08 Entitäten  ·  09 Sprache ───────┤
                                                                      ▼
                                              10 Abnahme  →  11 Betrieb

                        03 Dokumente — jederzeit, blockiert nichts
                        15 Eintragungsliste — durchgehend abarbeiten
```

## Die zwei Fragen vor allem anderen

Beide Kapitel entstanden am 2026-08-23 beim Durchspielen eines fiktiven neuen Landes. Sie
fehlten, und beide hätten ein Land vom ersten Tag an unbrauchbar gemacht:

1. **Rechnet das Land in Euro?** Wenn nein: die Schweiz zeigt, was passiert — `value_eur`
   ist dort bei **1 %** gefüllt (DE 91 %), und damit fällt jede wertbasierte Kennzahl aus.
   → [Kapitel 13](laender/13-waehrung-und-werte.md)
2. **Hat das Land andere Buchstaben?** Die Wortfaltung kennt ä/ö/ü/ß und zerlegt alles
   andere: `Łódź` wird zu `['d']`. Ohne Erweiterung ist **jede** Messung der Kapitel 04
   und 07 falsch — und zwar lautlos.
   → [Kapitel 14](laender/14-zeichen-und-schrift.md)

## Was zwischen Ländern übertragbar ist — und was nicht

| Baustein | Überträgt sich | Warum |
|----------|----------------|-------|
| TED-Parser (eForms/legacy) | **ja** | EU-einheitlich |
| CPV-Vokabular | **ja** | EU-Recht, `dim_cpv_label` gilt überall |
| Dubletten-**Logik** | **ja** | Wortmengen und Enthaltung sind sprachunabhängig |
| Gold-Builder | **ja**, wenn country-fähig | prüfen, nicht annehmen |
| Nationaler Parser | **nein**, ausser bei einem Standard | eigenes Schema je Quelle — **aber** OCDS und DECP sind Standards: ein Parser trägt dort über viele Länder ([Kapitel 17](laender/17-quelle-anbinden.md)) |
| **Locale** (Rechtsformen) | **nein** | national |
| **NUTS-Ebene** der Region | **nein** | DE 3 / AT 4 / CH 5 Stellen |
| Ortsnamen-Ausschlussliste | **nein** | Behördendeutsch ist national |
| Dokument-Connectoren | **nein** | je Portalfamilie |
| Entity-Register | **nein** | HR/Firmenbuch/Handelsregister je Land |
| Destatis-Kontext | **nein** | endet an der deutschen Grenze |
| Wortfaltung / Zeichen | **nein** | kennt nur ä ö ü ß |
| Währungsumrechnung | **nein** | gibt es bisher gar nicht |
| Regionskennung der Quelle | **nein** | liefert sie NUTS oder ein nationales Kürzel? |
| Behördenvokabular-Sperrliste | **nein** | „stadt" ist in AT ein Ortsname |

## Die eine Frage, die alles trägt

Wenn ein Feld leer ist, ein Wert fehlt, eine Ansicht nichts zeigt:

> ### Fehlt der Wert, oder fehlt die Leitung?

Die Antwort steht fast immer in Silber. Trägt Silber den Wert und Gold nicht, ist es die
Leitung — und dann gilt [Kapitel 12](laender/12-fallenkatalog.md).

## Werkzeuge, die man dabei braucht

```bash
scripts/laeuft_was.sh                          # ⛔ vor JEDEM schreibenden Schritt
python3 scripts/pruefe_verdrahtung.py --offen  # Sonde 1-4: Frische, Parität, Pfade, Länder
python3 scripts/verdrahtungskarte.py <tabelle> # wer erzeugt es, wer liest es
python3 -m govisor.cli verify --country XX     # FK-Integrität
python3 -m pytest tests/ -q                    # muss grün sein, vor dem Commit
```

## Verwandte Dokumente

- [`docs/quellen-landkarte.md`](quellen-landkarte.md) — Registry und Ausbau-Strategie
- [`docs/data-sources.md`](data-sources.md) — gemessene TED-Datenrealitäten
- [`docs/dokument-zugang-map.md`](dokument-zugang-map.md) — wer Unterlagen herausgibt
- [`docs/laender-onboarding-checkliste.md`](laender-onboarding-checkliste.md) — ältere
  Planungs-Checkliste (2026-07-30), **abgelöst** durch diese Bibel; sie enthält noch
  brauchbare Fragen für den Steckbrief eines Landes
