# Bausteinbibliothek freischalten

Der Code steht (Ticket #23 §9, Deploy-Schicht). Es fehlen **zwei Handgriffe**, die beide
Zugänge brauchen, die nur Sven hat.

## 1. Migration 0006 anwenden

Die sieben Tabellen aus `supabase/0006_doc_analysis.sql` existieren auf
`tegznbkbvbbbgzhsvoza` noch nicht — gemessen am 2026-08-25 über die REST-Schnittstelle
(15 von 22 Tabellen aller Migrationen sind da, die sieben fehlenden sind genau diese).

Die Datei ist wiederholbar (`create table if not exists`, `drop policy if exists`). Im
Supabase-Dashboard unter **SQL Editor** den Inhalt von `supabase/0006_doc_analysis.sql`
einfügen und ausführen.

Gebraucht werden davon nur zwei Tabellen — `profile_text_blocks` und `profile_block_usage`.
Die übrigen fünf gehören zur Dokumentenanalyse und stören nicht.

Danach prüfen:

```bash
python3 - <<'PY'
import urllib.request, ssl, re, certifi
from pathlib import Path
env = dict(re.findall(r"^([A-Z_]+)\s*=\s*(.*)$", Path("web/.env.local").read_text(), re.M))
url, key = env["NEXT_PUBLIC_SUPABASE_URL"].rstrip("/"), env["SUPABASE_SECRET_KEY"]
req = urllib.request.Request(f"{url}/rest/v1/profile_text_blocks?select=id&limit=1",
                             headers={"apikey": key, "Authorization": f"Bearer {key}"})
print(urllib.request.urlopen(req, timeout=20,
      context=ssl.create_default_context(cafile=certifi.where())).status)
PY
```

## 2. Hauptschlüssel setzen

Die Inhalte liegen **verschlüsselt** in der Spalte `content_encrypted` (§12.3). Ohne
Schlüssel speichert die Route NICHTS und antwortet mit 503 — bewusst, denn ein stiller
Rückfall auf Klartext sähe aus wie Erfolg.

```bash
openssl rand -base64 32
```

Den Wert als `BLOCKS_KEK` setzen: lokal in `web/.env.local`, im Deployment in den
Umgebungsvariablen.

⚠ **Der Schlüssel ist nicht wiederherstellbar.** Geht er verloren, sind alle gespeicherten
Bausteine unlesbar — die Route zählt sie dann und sagt es (`unlesbar` in der Antwort),
statt sie stillschweigend wegzulassen.

## Was danach passiert

* Ohne Anmeldung bleibt die Bibliothek wie bisher rein lokal (`localStorage.govisor.blocks`).
* Bei der ersten Anmeldung wandert der lokale Bestand **einmalig hoch**. Ohne diesen Schritt
  wäre die Anmeldung ein Datenverlust: die Bibliothek stünde plötzlich leer.
* Löschen archiviert (§9.2), es löscht nicht.

## Zwei offene Punkte

**Die Oberfläche verspricht mehr, als das Schema hält.** Auf `/bausteine` steht: „Eure
Textbausteine für Angebote — gehören dem **Unternehmen**, nicht der einzelnen Person." Die
RLS-Regel im Schema ist aber `auth.uid() = profile_id`, also **pro Person**. Zwei Personen
derselben Firma sehen die Bausteine der jeweils anderen nicht. Entweder der Satz ändert
sich, oder das Schema bekommt eine Firmen-Ebene — beides eine Entscheidung, kein Fehler.

**`profile_block_usage` wird noch von niemandem geschrieben.** Die Tabelle hält fest, welcher
Baustein in welchem Lead verwendet wurde (§10.4). Der Kombi-Knopf der Checkliste müsste das
melden; das ist nicht Teil dieser Verdrahtung.
