# Bausteinbibliothek freischalten

Der Code steht (Ticket #23 §9, Deploy-Schicht). Es fehlen **zwei Handgriffe**, die beide
Zugänge brauchen, die nur Sven hat.

## 1. Migrationen — ERLEDIGT (2026-08-25)

`supabase/0006_doc_analysis.sql` und `supabase/0016_bausteine_firmenebene.sql` sind auf
`tegznbkbvbbbgzhsvoza` angewandt. `psql` verbindet von dieser Maschine direkt
(`db.<ref>.supabase.co:5432`, Passwort in `.secrets/supabase_db.txt`) — Dashboard nicht
nötig, s. CLAUDE.md.

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

## Persönlich, mit Freigabe an die Firma (0016)

Ein Baustein gehört der Person, die ihn angelegt hat, und **sie** entscheidet, ob die Firma
ihn sieht. In der Karte steht dafür ein Schalter: „Nur ich" ↔ „Für die Firma".

* **Lesen** darf ein freigegebener Baustein jeder mit **belegter** Zugehörigkeit zu
  derselben Firma.
* **Ändern und archivieren** darf ihn ausschliesslich der Eigentümer — sonst nähme jemand
  anderes einem Menschen seinen Text weg.
* **Zurücknehmen** geht jederzeit; die Firma wird dabei aus dem Satz entfernt.
* **Firmenwechsel:** private Bausteine wandern mit, freigegebene bleiben, wo sie
  freigegeben wurden, bis der Eigentümer sie zurückzieht.

⚠ **Massgeblich ist der belegte Anspruch, NICHT das Profilfeld.**
`user_profiles.identity_id` ist eine Selbstauskunft — `saveIdentityCorrection` (§7.3) lässt
jeden Nutzer sie frei setzen. Eine Freigabe, die nur darauf schaut, wäre eine offene Tür:
wer den Namen einer fremden Firma einträgt, läse deren Bausteine. Die Regel prüft deshalb
`identity_claims` mit Status `belegt` oder `geprueft` — den vergibt `/api/entity-verify`
über die Firmen-Domain.

Am 2026-08-25 gegen die laufende Datenbank geprüft (Transaktion mit Rollback, es blieb
nichts zurück):

| Lage | sichtbar | erwartet |
|---|---:|---:|
| B hat keinen Anspruch | 0 | 0 |
| B trägt die Firma nur im Profil ein (Selbstauskunft) | 0 | 0 |
| B hat einen belegten Anspruch | 1 | 1 |
| B versucht zu archivieren | 0 Zeilen | 0 |
| privater Baustein von A | 0 | 0 |

⚠ **Solange niemand einen belegten Anspruch hat, ist der Schalter wirkungslos** — und die
Ansicht sagt das auch, statt ihn stumm auszugrauen. Belegt wird über die Firmen-Domain im
Onboarding.

## Verwendungshistorie (§9.3)

Übernimmt jemand in der Unterlagen-Checkliste einen Baustein („Kopieren & abhaken"), ist das
EIN Ereignis, nicht zwei: der Baustein entsteht **und** er ist in diesem Vorgang verwendet.
Beides schreibt dieselbe Anfrage — der Baustein nach `profile_text_blocks`, der Vermerk nach
`profile_block_usage`.

⚠ **Warum eine eigene Tabelle und nicht die Spalte `lead_id` am Baustein.** Ein Baustein
landet über die Jahre in vielen Vorgängen, eine Spalte behält nur einen. Die Tabelle zählt
mit, statt zu überschreiben; aus ihr kommt später die Zuordnung Thema/Stichworte.

⚠ **Der Vermerk reisst den Baustein nicht mit.** Schlägt er fehl, ist der Baustein trotzdem
gespeichert und die Antwort sagt es (`historie`). Eine verlorene Zeile Statistik ist kein
Grund, einem Menschen seinen Text wegzunehmen.

Am 2026-08-25 durchgespielt: drei Bausteine aus drei Vorgängen, einer davon zu kurz.
Ergebnis LEAD-B → referenzen, LEAD-C → nachhaltigkeit — der weggefallene LEAD-A ist
verschwunden statt verrutscht. Und die Regel hält: ein fremder Nutzer sieht keine
Verwendungen und kann auch mit bekannter Baustein-Kennung keine eintragen.

## Ein offener Punkt

**`profile_block_usage` wird noch von niemandem geschrieben.** Die Tabelle hält fest, welcher
Baustein in welchem Lead verwendet wurde (§10.4). Der Kombi-Knopf der Checkliste müsste das
melden; das ist nicht Teil dieser Verdrahtung.
