# Umzug nach Azure: was steht, was fehlt, was es kostet

**Sven am 2026-08-18:** „mach das setup cloud ready. ich würde es perspektivisch zu azure
hochladen und operations mit dem azure sre automatisieren."

Dieses Dokument ist die Landkarte dafür. Es beschreibt den **heutigen Zustand nach dem
Umbau** und die Punkte, die noch jemand entscheiden oder anlegen muss.

## Die Grundform: zwei Hälften, die nicht zusammengehören

```
  Datenfabrik (Python)                     Anwendung (Next.js)
  ────────────────────                     ───────────────────
  17 GB Rohdaten, 125 GB Unterlagen        liest NUR fertige JSONs
  Stunden Rechenzeit je Lauf               Millisekunden je Anfrage
  läuft einmal am Tag                      läuft immer
  braucht Platte                           braucht keine Platte
```

Diese Trennung ist der Grund, warum ein Umzug überhaupt möglich ist: die Anwendung kennt
die Datenfabrik nicht. Sie liest, was in `web/data` liegt, über
`web/lib/dataSource.ts` — und zwar aus einem Objektspeicher, sobald `DATA_BASE_URL` gesetzt
ist. Nichts anderes verbindet die beiden Hälften.

## Was der Umbau am 2026-08-18 verändert hat

| vorher | jetzt | warum |
|---|---|---|
| `web/data` in Git | ignoriert, per Upload verteilt | GitHub weist Dateien über 100 MB ab; `doc-text.json` lag bei 294 MB |
| Volltext als ein 294-MB-Block | eine Datei je Vorgang, Ø 61 KB | in der Cloud lud jede Instanz den ganzen Block, um EINEN Vorgang zu beantworten |
| kein Upload-Weg | `scripts/upload_web_data.py` | S3-kompatibel **und** Azure Blob, lädt nur Geändertes |
| kein Betriebsendpunkt | `/api/health` | eine Überwachung braucht einen Punkt ohne Anmeldung |

## Azure-Zuordnung

| Baustein | Azure-Dienst | Anmerkung |
|---|---|---|
| `web/data` (642 MB, täglich neu) | **Blob Storage**, Cool-Tier | Zugriff per SAS-Token, nicht per Kontoschlüssel: begrenzt auf Container und Rechte, läuft ab |
| Next.js-Anwendung | **Static Web Apps** oder **Container Apps** | Vercel kann bleiben; die Anwendung ist an nichts gebunden ausser `DATA_BASE_URL` |
| Datenfabrik (Python) | **Container Apps Job** (geplant, täglich) oder eine kleine VM | braucht Platte für `data/`; die 125 GB Unterlagen bleiben besser dort, wo sie entstehen |
| Zugangsdaten | **Key Vault** | heute `.secrets/openrouter.key` und `web/.env.local` |
| Überwachung | **Azure Monitor** auf `/api/health` | `status: veraltet` ist der Alarm, der wirklich zählt |
| Anmelde-Mails | eigenes SMTP (z. B. **Communication Services**) | der eingebaute Supabase-Mailer drosselt auf wenige Mails pro Stunde |

## Der Upload

```bash
# Azure (empfohlen: SAS statt Kontoschlüssel)
DATA_AZURE_URL="https://<konto>.blob.core.windows.net/<container>?<sas>" \
  python3 scripts/upload_web_data.py --alles
```

Danach in der Anwendung `DATA_BASE_URL` auf dieselbe Basis zeigen lassen — ohne SAS, wenn
der Container öffentlich lesbar ist, sonst mit einem Lese-SAS.

Der Tageslauf ruft den Upload nach den Exporten selbst auf. Ist nichts konfiguriert, sagt er
das und bricht **nicht** ab: lokal bleibt die Platte die Quelle.

## Was noch offen ist, ehrlich

1. **Speicher anlegen und `DATA_BASE_URL` setzen.** Bis dahin findet ein Deployment keine
   Daten. Die Datenrouten antworten dann leer mit Begründung, nicht mit falschen Zahlen.
2. **`/firma` ist nicht serverless-fähig** (ruft Python zur Laufzeit). Entweder vorberechnen
   wie alles andere oder ein eigener kleiner Dienst.
3. **`/api/leads` hat kein Auth-Gate.** Heute schützt allein die Coming-Soon-Sperre. Vor dem
   Go-live zu entscheiden (steht auch in `CLAUDE.md`).
4. **`ADMIN_EMAILS`** ist nur lokal gesetzt; in der Cloud gilt sonst die Vorgabe `sk@skot.de`.
5. **Mail-Vorlagen** auf `{{ .TokenHash }}` umstellen, sonst funktionieren Anmeldelinks nur
   in dem Browser, der sie angefordert hat.
6. **Die 125 GB Unterlagen** bleiben lokal. Sie sind Arbeitsmaterial, kein Auslieferungsgut
   (s. `docs/entscheidung-dokumente.md`) — aber sie haben **kein Backup**.

## Für die Betriebsautomatik

`/api/health` antwortet ohne Anmeldung:

```json
{ "status": "ok" | "veraltet" | "keine_daten", "alter_stunden": 0 }
```

HTTP 200 bei `ok`/`veraltet`, **503** bei `keine_daten`. Bewusst ohne Mengenangaben: eine
Gesundheitsprobe fragt jeder ab, der die URL kennt, und „wie viele Ausschreibungen habt ihr"
ist eine Geschäftszahl, kein Betriebszustand.

Die interessante Störung ist nicht der Ausfall, sondern der **stille Stillstand**: der
Tageslauf bricht ab, die Anwendung liefert weiter Daten von vorgestern, und alles sieht
gesund aus. Genau dafür ist `alter_stunden` da; die Schwelle steht bei 30 Stunden, damit ein
verpasster Lauf durchgeht und zwei nicht.

Die ausführliche Innensicht bleibt unter `/intern/lauf` (Admin-Anmeldung): Trichter,
Arbeiter-Zustand, Logauszug.
