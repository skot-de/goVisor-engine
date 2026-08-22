# web/data liegt nicht in Git — wie die Daten zum Frontend kommen

**Entschieden am 2026-08-18.** Vorher stand hier eine Migrations-Notiz („wenn du so weit
bist"). Jetzt ist der Schnitt gemacht, und das ist der Betriebszustand.

## Was den Ausschlag gab

Nicht die Gesamtgrösse, sondern eine harte Grenze: **GitHub weist jeden Push mit einer Datei
über 100 MB ab.** `web/data/doc-text.json` wuchs nach dem Formate-Ausbau von 1 MB auf
**294 MB**. Wäre sie versioniert, liesse sich der Branch ab diesem Commit nicht mehr pushen,
bis die Datei aus der Historie entfernt ist.

Dazu die Mengenrechnung, die schon vorher gegen Git sprach: der Tageslauf schreibt jede Nacht
rund **150 MB** neu (`leads-bau.json` 42 MB, `suppliers.json` 38 MB, `detail-bau.json` 30 MB).
Versioniert heisst das 150 MB pro Nacht dauerhaft in der Historie, und Historie schrumpft
nicht. Dass es nicht früher auffiel, lag daran, dass 79 Commits nicht gepusht waren.

## Wie es jetzt läuft

```
scripts/daily_leads.sh
  → export_web_leads / export_suppliers / export_strategie / export_regionen …   web/data/
  → scripts/upload_web_data.py                     S3-kompatibler Speicher
  → Frontend: web/lib/dataSource.ts liest DATA_BASE_URL
       ist sie NICHT gesetzt → lokale Platte (Entwicklung, dieser Rechner)
```

Der Upload lädt **nur Geändertes** (HEAD-Abfrage auf die Grösse), spricht R2, S3, B2 und
MinIO, und braucht **keine zusätzliche Abhängigkeit**: die SigV4-Signatur steht in 40 Zeilen
Standardbibliothek im Skript. Ein Test prüft sie gegen den dokumentierten AWS-Testvektor —
ein Signaturfehler sähe sonst wie „HTTP 403" aus, also wie falsche Zugangsdaten, und man
sucht an der falschen Stelle.

## Was einzurichten ist (einmalig)

1. **Bucket anlegen.** Empfehlung Cloudflare R2: 10 GB frei, **keine Egress-Kosten**, und
   S3-kompatibel. Alternativen: S3, Backblaze B2, Supabase Storage. ⚠️ Supabase Storage hat
   im Free-Tarif 1 GB **und** eine Grenze je Datei, an der `doc-text.json` (294 MB) scheitert.
2. **Zugangsdaten** in `web/.env.local` (lokal) bzw. in den Runner:
   ```
   DATA_S3_ENDPOINT=https://<konto>.r2.cloudflarestorage.com
   DATA_S3_BUCKET=govisor-data
   DATA_S3_KEY_ID=…
   DATA_S3_SECRET=…
   DATA_S3_PREFIX=web-data          # optional
   ```
3. **Einmal vollständig hochladen:** `scripts/upload_web_data.py --alles`
   (Stand 2026-08-22: **984 MB, 9.125 Dateien** — die Dokumenttexte wachsen schnell,
   am 18.08. waren es noch 624 MB und 2.022 Dateien).
4. **Dieselben vier Variablen auch im Deployment setzen** (`DATA_S3_ENDPOINT`,
   `DATA_S3_BUCKET`, `DATA_S3_KEY_ID`, `DATA_S3_SECRET`, optional `DATA_S3_PREFIX`).
   Das Frontend liest damit **signiert** — der Bucket bleibt privat.

   ⚠️ **Den Bucket NICHT öffentlich schalten.** `DATA_BASE_URL` allein (blankes `fetch`)
   gibt es weiterhin, aber nur, um einen bestehenden offenen Bucket nicht zu brechen. Unter
   dieser Basis liegt `suppliers.json` mit den Kontaktdomains von 16.454 Firmen — Felder,
   die `lib/suppliers.ts` ausdrücklich als „NUR SERVERSEITIG" führt —, dazu 6.563
   Dokumentvolltexte und 253 MB LLM-Auswertungen. Offen wäre die Ratenbremse auf
   `/api/entity-search` gegenstandslos: ein einziger GET liefert den ganzen Bestand.
   Nachträglich schliessen heisst annehmen, dass in der Zwischenzeit niemand hingesehen hat.

## ⚠️ Solange Schritt 1 bis 4 nicht erledigt sind

Lokal ändert sich nichts, die Platte bleibt die Quelle. **Das Deployment aber findet keine
Daten**: `web/data` ist nicht mehr im Repo, und ohne `DATA_BASE_URL` gibt es keinen Ersatz.
Die Datenrouten antworten dann ehrlich leer (503 mit Begründung), nicht mit falschen Zahlen.
Für govisor.eu ist das derzeit verkraftbar, weil die Seite hinter der Coming-Soon-Sperre liegt.

## Ein frisches Klon

`web/data` ist leer. Entweder `DATA_BASE_URL` setzen oder die Exporte einmal laufen lassen.
Der Rohbestand dahinter (`data/`, 17 GB, plus 125 GB Dokumente) liegt ohnehin nur auf der
externen Platte dieser Maschine — s. `docs/entscheidung-dokumente.md`.
