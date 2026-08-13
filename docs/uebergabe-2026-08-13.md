# Übergabe 2026-08-13 — Dokument-Pipeline & Marktpuls

Für die nächste Sitzung. Erst lesen, dann anfangen. Ergänzt `CLAUDE.md`, ersetzt es nicht.

---

## 1. Was als Nächstes zu tun ist

**Auftrag: Jahres-Layer + Historie für Marktpuls, zusammen mit den nationalen Quellen.**
Vier Entscheidungen stehen bereits fest, sie sind nicht neu zu diskutieren:

1. **Historie ab 2004** (Gold hat 2004–2026 lückenlos, 1,83 Mio. DE-Notices; Marktpuls nutzt
   heute nur 2021–2025). Über einen eigenen Schalter `--ab-jahr`, **nicht** per Default —
   `build_marktpuls.py` läuft seit heute im Tageslauf und darf dort nicht minutenlang werden.
2. **Schema-Brüche markieren, nicht glätten.** Über 22 Jahre wechselt das TED-Schema viermal
   (`legacy` / `eforms` / `text` / `ojs`), dazu Schwellenwert- und Meldepflicht-Änderungen.
   Ein Knick ist dann eine Regeländerung, kein Marktereignis.
3. **Quellen-Zusammensetzung je Jahr mitführen.** Das ist der Mechanismus, der einen
   Quellen-Start sichtbar macht, statt ihn als Marktwachstum durchgehen zu lassen.
4. **Nationale Quellen — Regel statt Sonderfall je Land:** eine nationale Quelle wird mit TED
   *zusammengeführt*, wenn sie über das ganze Fenster durchgehend liefert; sonst bekommt sie
   eine **eigene Serie ab ihrem Beginn**. Nicht addieren.

   | Land | heute | Konsequenz |
   |---|---|---|
   | DE | TED durchgehend, **DÖE ab 2023** | DÖE als eigene Serie |
   | CH | TED durchgehend, **simap ab 2024** | simap als eigene Serie |
   | AT | TED + atverg, beide durchgehend | bleibt zusammengeführt (schon so) |

   DÖE steckt in den **Stichtags-Kennzahlen bereits drin** — ausgeschlossen ist es nur aus der
   Zeitreihe. Wer „DÖE fehlt" liest, prüft zuerst, welche der beiden Zahlen gemeint ist.

**Einstiegspunkt:** `verfahren_tabelle(con, land, ab_jahr)` in `scripts/build_marktpuls.py`
(545 Z.) legt die TEMP TABLE `v_<land>` an — Spalten `land, jahr, monat, branche, quelle,
verfahren_key, frist, hat_frist`. Heute mit `jahre[0]` (2021) aufgerufen.

---

## 2. Die Falle, die alles kippt

**In eForms ist eine Korrekturbekanntmachung wieder ein normales `ContractNotice`**
(`notice_kind='cn'`) — DE 2025 gemessen: **17.552 von 87.862 = 20 %**. Und
`ref_publication_number`, die alte Klammer, ist ab 2024 praktisch leer.

Wer für den Jahres-Layer neu aggregiert und diese Klammer nicht mitnimmt, **überzählt ab 2023
um ein Fünftel** und sieht ein Wachstum, das es nicht gibt. Die Auflösung liegt in
`verfahren_tabelle()`: Erkennung über `EformsExtension.Changes.ChangedNoticeIdentifier`,
Schlüssel-Wasserfall `ContractFolderID` (BT-04, 100 % Abdeckung bei eForms-CN) → Wurzel der
Rückverweis-Kette → `publication_number`. Änderungsbekanntmachungen bleiben **in** der Gruppe
(nur für `max(frist)` — die Fristverlängerung steht ausschließlich in ihnen; ohne sie fielen
355 laufende Verfahren fälschlich raus), eröffnen sie aber nicht.

---

## 3. Stand: fertig und verifiziert

| Baustein | Ergebnis |
|---|---|
| Preisblatt-Leser | 883 Positionen / 39 Vorgänge (Kopfzeile gesucht, Spalten über Überschrift) |
| GAEB-Flat (D81/D83/P83) | +125 Vorgänge, die sonst gar kein LV hätten |
| LV + Kriterien im Frontend | Unterlagen-Tab, 273 Leads, CSV-Download je Vorgang |
| `index-docs` im Tageslauf | Kette war unterbrochen: 2.114 geladen, 241 ausgewertet |
| Portal-Vorprüfung | 14 Plattformen, **keine Anmelde-Wand** — Hindernis ist JS, nicht Zugang |
| RIB-Connector | Abdeckung offener Leads 33 % → 40 % |
| Marktpuls | läuft, im Tageslauf, Browser geprüft, EN/FR vollständig |

**Gesamt: 1.053 Vorgänge mit maschinenlesbarem Leistungsverzeichnis** (vorher 856),
236.314 Positionen. 235 Tests grün.

**Marktpuls-Befund, gemessen: kein Sommerloch.** Juli +12,2 % (zweitstärkster Monat), August
+1,7 %. Das Loch ist der **Januar** (−24,4 %), schwächer der November (−10,4 %). Gegengeprüft
an rohen CN ohne jede Dedup — gleiche Form in jedem der fünf Jahre, kein Artefakt.
`pct` ist ein **Saisonindex** (erst je Jahr normiert, dann gemittelt), weil das Fenster eine
Niveauverschiebung enthält (DE-TED 2021 55,8k → 2025 70,3k). Naiver Wert liegt als `pct_naiv`
daneben, Abweichung max. 0,8 pp.

---

## 4. Offen — nach Hebel sortiert

1. **60 % der offenen Leads liegen auf ungedeckten Portalen** (7.220 von 10.797). Das ist die
   größte Lücke im ganzen Dokument-Strang, größer als jede Parser-Verbesserung. Die
   Vorprüfung (`scripts/probe_portals.py`) zeigt: keine Anmelde-Wand, die Dateilisten kommen
   per JavaScript. Nächste Kandidaten: subreport (581), staatsanzeiger-eservices (203),
   had.de (189), vergabe24 (173). `evergabe-online` (791) antwortete durchgehend 503 — neu
   messen. `subreport-elvis` und `aumass` haben Bot-Schutz.
   Verdrahtung über `_waehle_connector()` in `govisor/docfetch.py`: neue Plattform = ein Modul
   plus eine Zeile.
2. **Die Dokument-Pipeline ist eine DE-Funktion, keine fertige.** CH/simap verlangt für den
   Download eine Registrierung (nicht umgehbar), AT liefert als `documents_url` nur die
   TED-Bekanntmachung, übrige EU-Länder gar nichts. Nach dem EU-weit-Grundsatz in `CLAUDE.md`
   ist das ein offener Punkt, kein Nebenschauplatz.
3. **Marktpuls-Einbauort.** `/marktpuls` ist Vorschau; die Platzierung auf Landing/Blog/
   Strategie ist im Briefing §9-1 offen.
4. **Änderungserkennung der Unterlagen.** Beide Connectoren laden einmal und sind danach
   idempotent. Vergabeunterlagen ändern sich aber während der Frist (Bieterfragen,
   Berichtigungen). Eigenes Ticket, betrifft cosinex und RIB gleichermaßen.
5. **Konsolenfehler `Cannot read properties of undefined (reading 'sprachen')`** — älter als
   diese Sitzung, nicht analysiert.
6. Kleinere, bewusst so belassene Grenzen: Preisblatt ~50 % ohne erkennbare Kopfzeile;
   Kriterienmatrix nur 8 Vorgänge (das UfAB-Formblatt ist selten, kein Parser-Problem).

---

## 5. Arbeitsweise, die sich hier bewährt hat

- **Ein Prüfstein aus echten Daten schlägt Testfixtures.** 174 Vorgänge liefern ihr LV in
  beiden GAEB-Formaten — damit ließ sich der neue Leser gegen den bewährten rechnen
  (99,7 % bei den Mengen). Ohne das hätte niemand einen Spaltenversatz bemerkt.
- **Wenn alle Fälle gleich aussehen, misst man sich selbst.** 14 von 14 Portalen meldeten
  denselben Fehler → es war `urllib` gegen einen TLS-Proxy, nicht die Portale. Ebenso: der
  Prüfstein meldete 0,1 % Übereinstimmung → er verglich `'1.000'` mit `'1'`.
- **Eine Grenze, die die Hälfte der Fälle trifft, ist stiller Datenverlust.** 3 von 5
  RIB-Vorgängen landeten exakt auf der 80-Dateien-Obergrenze.
- **Guards prüfen, was sie sehen.** Der i18n-Guard sah nur inline-`t("…")`; 53 Sätze in einer
  Konstanten-Tabelle blieben unbemerkt deutsch. Jetzt erweitert — und die Gegenprobe mit
  künstlich eingebauter Lücke gemacht: ein Guard, den man nicht hat scheitern sehen, ist
  keiner.
