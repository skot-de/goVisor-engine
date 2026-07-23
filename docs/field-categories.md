# Feld-Kategorien — was noch nicht in Tabellen steht

**Stand:** 2026-07-17. Nach der Normalisierung von Silber (6 Tabellen) sind
noch ~144 Feldarten mit relevanter Häufigkeit nicht abgebildet. Sie stehen
weiterhin in **Bronze** (verlustfrei) und sind von dort nachziehbar.

Dies ist die Landkarte, welche als Nächstes promotet werden — nach Produktwert
geordnet, nicht nach Häufigkeit.

## Datenumfang (Kontext)

DE ist **komplett über alle CPV-Codes** — kein Branchenfilter im Import. IT
(CPV 72/48/30/32/50) ist nur ~9 % des Bestands; Bau (45) ist mit 38,6 % der
größte Block. IT ist eine `WHERE`-Sicht, kein Import-Filter.

## Kategorien

| # | Kategorie | Felder (Legacy / eForms) | Wert | Ziel |
|---|---|---|---|---|
| 1 | **Verfahrensmerkmale** | TYPE_CONTRACT/NC_CONTRACT_NATURE, PR_PROC/ProcurementTypeCode, AC_AWARD_CRIT, LEGAL_BASIS/RP_REGULATION, TY_TYPE_BID | hoch | Spalten in `notices` |
| 2 | **Käufer-Klassifikation** | AA_AUTHORITY_TYPE/CA_TYPE, MA_MAIN_ACTIVITIES/CA_ACTIVITY (COFOG) | hoch | Spalten in `notice_parties` (buyer) |
| 3 | **Erfüllungsort** | PERFORMANCE_NUTS/RealizedLocation, CA_CE_NUTS | mittel | neue Tabelle `place_of_performance` |
| 4 | **Fristen & Termine** | DT_DATE_FOR_SUBMISSION (Angebotsfrist), DATE_DISPATCH_NOTICE | mittel | Spalten in `notices` |
| 5 | **Wettbewerb** | NB_TENDERS_RECEIVED, NB_TENDERS_RECEIVED_SME, NB_TENDERS_RECEIVED_OTHER_EU | hoch | neue Tabelle `awards` |
| 6 | **Optionen & Verlängerung** | RENEWAL/RENEWAL_DESCR, OPTIONS/OPTIONS_DESCR, NB_RENEWAL, DURATION(TYPE) | **sehr hoch** | Spalten in `lots` + `notices` |
| 7 | Käufer-Kontakt-Extras | ADDRESS (Straße), FAX, IA_URL_GENERAL (Beschafferprofil), REFERENCE_NUMBER | niedrig | Spalten in `notice_parties` |
| 8 | Technisches Plumbing | RECEPTION_ID, DELETION_DATE, *_LINK, UBLVersionID, CustomizationID, VersionID | ignorieren | bleibt in Bronze |

## Reihenfolge der Promotion

1. **Kategorie 6 (Verlängerungen)** zuerst — trägt die Wechsel-Prognose. In der
   X-RAY-Analyse zeigte sich: „+48 Monate"-Faustregel zu 39 % falsch, die
   Wahrheit steht in RENEWAL_DESCR. Muss strukturiert nach Silber.
2. **Kategorie 5 (Wettbewerb)** — Bieterzahl = Verdrängbarkeit, direkt für die
   Lead-Qualität.
3. **Kategorie 1 + 2** — Verfahrensart und Käufertyp, für Filterung und
   Segmentierung.
4. **Kategorie 3 + 4** — Erfüllungsort und Fristen.
5. Kategorie 7 bei Bedarf; Kategorie 8 nie.

Jede Promotion folgt derselben Disziplin: Feldposition in beiden Generationen
messen (nicht annehmen), extrahieren, Spalte/Tabelle ergänzen, aus Bronze neu
bauen.
