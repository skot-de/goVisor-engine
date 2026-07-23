# Entscheidungen & Kontext (Nicht-Code-Wissen)

**Stand:** 2026-07-17. Diese Datei hält fest, was *nicht* im Code oder in
`concept-v3.md`/`data-sources.md` steht: getroffene Entscheidungen, Arbeitsweise,
Preis-Analyse und offene Punkte. Fachliche Messwerte stehen in `data-sources.md`.

---

## Architektur-Entscheidungen (und warum)

- **XML-Bulk statt CSV.** Der CSV-Export hat keinen Freitext und endet 2023. Die
  monatlichen XML-Pakete tragen Freitext *und* strukturierte Felder, 2004–heute.
- **Normalisiertes Schema, kein JSON-Blob.** Silber = echte typisierte Tabellen,
  per SQL joinbar. Nicht gemappte Felder landen in `attributes` (jede Notice als
  (Pfad, Wert)-Zeilen), nicht in einem JSON-String.
- **Bronze ist der Verlust-Rückversicherer.** Original-XML unverändert. Silber/
  Gold jederzeit daraus neu baubar → Parser-Fix kostet Re-Run, keinen Download.
  Verlustfreiheit ist bewiesen: attributes-Zeilenzahl == XML-Blattwerte.
- **Fakt in Silber, Interpretation in Gold.** CPV-Code = Fakt (Silber). Branche,
  Firmengruppe, Deflator = redaktionell/versioniert (Gold, editierbar, überlebt
  Rebuild). „Was zählt als IT" ändern = eine Zeile in `cpv.py`, kein Rebuild.
- **DuckDB/Parquet lokal** für Bronze+Silber+Gold (Bauphase). Supabase erst für
  die Serving-Ebene.
- **DE komplett, alle CPV.** Kein Branchenfilter beim Import. IT (~9%) ist eine
  `WHERE`-Sicht, kein Import-Filter. Land ist überall Parameter (EU-erweiterbar).

## Firmengruppen (redaktionell, editierbar)

`data/curated/DE_company_groups.csv` — von Hand pflegbar, überlebt Rebuild.
Gruppe „CANCOM" ist *deine Setzung*, NICHT die echte Konzernmutter (die ist oft
nicht sauber auflösbar). Seed (Namensstamm) nur zum Bootstrappen; danach editierst
du `group_label`, setzt `source=manual`, und der Seed fasst deine Zeilen nie mehr
an. ARGE dagegen = pro-Auftrag-Team, KEINE Gruppe → zerlegen + Partnergraph.

## Arbeitsweise (von Sven eingefordert)

- **Messen statt annehmen.** Jede Zahl/Feldposition an echten Daten prüfen. Bei
  abgeleiteten Tabellen gibt es keine Ground Truth — die Zeilenzahl/Verteilung
  auf Plausibilität prüfen ist die einzige Kontrolle. (15-Mio-Ketten-Explosion,
  7%-Incumbent-Artefakt, 29%-Konsortium waren alle nur durch Hinsehen sichtbar.)
- **Kein Datenverlust, markieren statt wegwerfen.** Nichts nach eigener Relevanz
  filtern. Unbekanntes → „sonstiges"/`attributes`. Zweifelsfälle → `review`-Queue
  mit Beleg-XML. Erschlossenes trägt Konfidenz, nie ein sauberer FK.

## Preismodell (an Daten belegt)

Erkennung „hat gewonnen" ist zuverlässig (national_id ~100% ab 2024), der WERT
fehlt bei ~50% der Vergaben (2024: 27%). **Empfehlung: monatliche SaaS-Fee als
Basis + FIX pro gewonnenem in-platform-Lead** (abrechenbar an ~100% der aktuellen
Gewinne) — NICHT %-vom-Volumen (nur 31–51% abrechenbar, plus Wertstreit).
Größen-Bänder: für Analytik/Dashboard schätzbar (mehrere Signale nötig, CPV allein
zu grob), fürs Billing nur auf echten Werten. Attribution-Gate: Fee nur auf
in-platform bearbeitete Leads (TED zeigt „gewonnen", nicht „wegen goVisor").

## Offene Punkte (benannt, nicht gebaut)

- **Entity-ID-Härtung verifizieren** — Incumbent-Rate sollte von 7% (Artefakt
  instabiler IDs) auf 40–60% springen; Beweis, dass HRB-zuerst-Auflösung trägt.
- **ARGE-Namen zerlegen** (die 1–5% Ein-Namen-Fälle) + Konsortial-Partnergraph.
- **Rahmenvertrags-Abruf-Tracking** (Einzelabrufe gegen Maximalvolumen).
- **LLM-Schritte** (nicht gebaut): Maximallaufzeit aus RENEWAL_DESCR, konkrete
  Zertifikate aus requirements.text, für Auto-Match strukturieren.
- **Externe Quellen** (nicht TED): Haushaltsdaten, News/Insolvenz, Vergabekammer.
- **Harte Quellgrenze:** TED nennt nur Gewinner, nie Verlierer → keine echte
  Gewinnquote ohne User-Input.
