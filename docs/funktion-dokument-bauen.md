# Funktion: aus Bausteinen ein Dokument bauen

**Plan, Stand 2026-10-05.** Zahlen tragen ihr Messdatum.

**Warum diese Funktion und nicht eine andere.** Die Wettbewerbsanalyse vom 4./5. Oktober kommt zu
einem unbequemen Ergebnis: wir haben mehrere Alleinstellungen (Dinge, die sonst keiner anbietet),
aber **praktisch keinen Burggraben** — nichts, was einen Wettbewerber aufhält. Die kürzesten
Vorsprünge sind Wochen.

Der einzige echte Wechselkosten-Graben sind **die Daten des Kunden selbst**. Sobald Referenzen,
Zertifikate und zusammengestellte Dokumente einer Firma bei uns liegen, kostet ein Wechsel sie
etwas. Die Bausteinbibliothek ist der Anfang davon; diese Funktion macht sie nützlich genug, dass
jemand sie wirklich füllt.

⚠ **Das steht auf keiner der acht Blocker-Zeilen in `docs/go-live.md`.** Kein Backup, kein
Mailversand, kein Server — das bleibt daneben offen. Diese Funktion baut den Graben, sie macht das
Produkt nicht startfähig.

---

## 1. Was ein „Dokument" ist

Eine benannte, geordnete Folge von **Teilen**. Ein Teil ist entweder

- ein **Verweis auf einen Baustein** aus der Bibliothek,
- eine **Überschrift**, oder
- **freier Text**.

Optional an einen Vorgang gehängt. Zusammenstellen in der App, Export als Word oder PDF.

⚠ **Verweis, nicht Kopie — das ist die wichtigste Entscheidung im Modell.** Ein kopierter Baustein
veraltet still: wer seine ISO-Zertifikatsnummer in der Bibliothek pflegt, hätte sie in zwölf alten
Dokumenten weiterhin falsch stehen, ohne es zu merken. Ein Verweis folgt der Pflege. Wer eine
Fassung einfrieren will, wandelt den Teil ausdrücklich in freien Text um (ein Knopf, kein
Automatismus).

## 2. Phase 1 — Zusammenstellen

### Datenmodell (Migration 0038)

| Tabelle | Spalten |
|---|---|
| `profile_dokument` | `id`, `profil_id` → `user_profiles(id)`, `org_id`, `titel`, `lead_id?`, `erstellt_at`, `updated_at` |
| `profile_dokument_teil` | `id`, `dokument_id`, `position`, `art` (`baustein`\|`ueberschrift`\|`text`), `baustein_id?` → `profile_text_blocks(id)`, `inhalt_encrypted?`, `ebene?` |

⚠ **`profil_id`, nicht `org_id` allein** — dieselbe Falle wie in 0037: `profile_text_blocks` hängt
am NUTZER (`user_profiles.id` IST die Auth-Kennung), die Mehrfachprofile aus `profiles` (0033) sind
etwas anderes.

⚠ **`inhalt_encrypted` mit demselben Umschlagverfahren wie die Bausteine** (`web/lib/blockCrypto.ts`
/ `govisor/blockcrypto.py`). Es wäre absurd, Bausteine zu verschlüsseln und den daraus gebauten
Text eine Tabelle weiter offen liegen zu lassen.

⚠ **Fremdschlüssel in `scripts/pruefe_gold_integritaet.py` eintragen** — Pflicht für jede neue
Tabelle mit Schlüssel.

**RLS:** lesen und schreiben nur in der eigenen Organisation, Form aus 0027
(`org_id = (select org_id from public.user_profiles where id = auth.uid())`), beim Anlegen
zusätzlich `profil_id = auth.uid()`.

### Route

`/api/dokument` — GET (Liste oder eins samt Teilen, entschlüsselt), POST (anlegen), PATCH
(Titel, Teile, Reihenfolge), DELETE.

⚠ Datenbankmeldungen **nicht** durchreichen (Lehre aus 0037: „Could not find the table … in the
schema cache" stand im Gesicht des Nutzers).

### Oberfläche

Links die Bibliothek mit Themenfilter, rechts das Dokument als sortierbare Liste, dazwischen
„übernehmen". Überschriften und freier Text als eigene Teilarten. Vorschau darunter.

## 3. Phase 2 — Export

### Word (.docx), selbst geschrieben

Eine `.docx` ist ein ZIP mit festgelegter XML-Struktur, und **`fflate` liegt seit dem
Fragebogen-Leser bereits als Abhängigkeit vor** — `zipSync` statt `unzipSync`. Rund 200 Zeilen,
volle Kontrolle über Überschriftenebenen und Absatzformate.

**Warum nicht die Bibliothek `docx`:** rund 2 MB für etwas, das wir in einer Datei beherrschen, und
eine weitere Abhängigkeit im geteilten `node_modules` (Symlink in den Haupt-Baum).

⚠ **Wächter:** ein Test, der die erzeugte Datei wieder entpackt und die XML-Struktur prüft. Eine
`.docx`, die Word nicht öffnet, merkt man sonst beim Kunden. Das Muster steht in
`tests/test_fragebogen_lesen.py`: echte Datei erzeugen, echten Leser darauf loslassen.

### PDF über den Druckdialog

Ein Druck-Stylesheet plus `window.print()`. Null Abhängigkeit, der Nutzer bekommt sein eigenes
Papierformat.
⚠ **Ehrliche Grenze:** keine Kontrolle über Seitenzahlen, Kopf- und Fusszeilen. Wer echte
Satzkontrolle braucht, braucht einen Server-Renderer — eigene Phase, eigener Aufwand.

### Herkunftsanhang

Abschaltbar, **standardmässig aus**: welcher Teil kam aus welchem Baustein, mit Datum. Unsere
Hausform, nützlich für die interne Freigabe, peinlich im Angebot.

## 4. Phase 3 — Verbindung zum Fragebogen  ✅ gebaut 2026-10-05

Ein fertiger Lauf aus `user_antwortauftrag` schiebt seine `fertig`-Vorschläge als Teile in ein
neues Dokument. Damit schliesst sich der Kreis: Fragebogen rein, geprüftes Dokument raus.
⚠ Nur `fertig`, nie `unbelegt` — dieselbe Regel wie in der Ansicht, und seit dem Bau durch
`tests/test_antwortvorschlag.py::test_uebernahme_ins_dokument_nimmt_nur_fertig` gehalten: die
Regel gilt an **zwei** Stellen (Rechenseite und Übertrag), geprüft war bis dahin nur die erste.

**Abweichung von diesem Plan, bewusst.** Hier stand „**mitsamt Beleg**". Umgesetzt ist es nicht,
und zwar aus zwei Gründen: im Dokument gibt es kein Feld dafür (`profile_dokument_teil` kennt
`baustein`, `ueberschrift`, `text`), und der Beleg gehört in die **Prüfung**, nicht in die
Ausgabe — im abgegebenen Angebot wäre er peinlich, genau wie der Herkunftsnachweis in §3.
Die Rückverfolgung entsteht stattdessen über die **Form**: jede Frage wird zur Überschrift, die
Antwort steht darunter. Wer wissen will, woher ein Absatz kommt, sieht die Frage über ihm.

Die Antworten wandern als Teile der Art `text`, **nicht** als Baustein-Verweise: der Entwurf ist
aus mehreren Bausteinen zusammengesetzt und vom Modell umformuliert. Ein Verweis wäre eine Lüge
über seine Herkunft, und eine spätere Baustein-Änderung würde eine bereits abgegebene Antwort
rückwirkend verändern.

**Das Drucklayout ist angesehen** (2026-10-05, zum ersten Mal: in Phase 2 war es gebaut und
ungeprüft). Es zeigt Titel, Überschriften und Antworten, ohne Werkzeugleisten, Knöpfe und
Seitenleiste. Geprüft, indem `@media print` vorübergehend auf `@media screen` gestellt wurde.
Die grauen Bahnen darin kommen vom **Seitenkörper**, nicht vom Dokument (alle Dokumentelemente
sind `transparent`, nachgemessen) — Browser drucken Körperhintergründe standardmässig nicht.

**Gemessen am laufenden System** (2026-10-05, Prüfkonto, 4 Bausteine, 5 Fragen): 4 belegt, 1 ohne
passenden Baustein; das Dokument bekam 8 Teile in der richtigen Reihenfolge, die unbeantwortete
Frage fehlt korrekt. ⚠ Der **Modellaufruf** war dabei durch eine Attrappe ersetzt (OpenRouter-
Guthaben leer); alles andere, Verschlüsselung und Belegprüfung eingeschlossen, lief echt.

`POST /api/dokument` nimmt die Teile seit Phase 3 gleich mit. Ohne das wären es zwei Anfragen,
und scheitert die zweite, bleibt ein **leeres Dokument** stehen, das der Nutzer für vollständig
hält. Zwei Aufrufe über PostgREST sind keine Transaktion, deshalb wird das Dokument bei einem
Fehler beim Schreiben der Teile wieder entfernt — gemessen: ohne diesen Rückbau bleibt der Rumpf
tatsächlich liegen.

## 5. ⛔ Die Grenze, die in den Plan gehört

**Die Vergabestelle schreibt meistens ihre eigenen Formulare vor.** Unser Export deckt die **freien
Teile** ab — Konzept, Referenzen, Unternehmensdarstellung — nicht die vorgeschriebenen Vordrucke.

BidFix wirbt mit „arbeitet in Ihren Vorlagen, nicht in fremden Templates" (Produktseite, gelesen
2026-10-04). **Das können wir in Phase 2 nicht, und der Vertrieb darf es nicht andeuten.**
Vorlagen-Treue wäre eine eigene Phase und deutlich teurer.

## 6. Fallen, die vorher bekannt sind

1. **Das Versprechen „wir speichern nichts" gilt hier NICHT.** Es stammt aus dem Fragebogen-Teil
   (`supabase/0037`) und darf nicht übernommen werden: ein Dokument wird absichtlich gespeichert.
   Also verschlüsselt, löschbar, und in der Oberfläche sichtbar gemacht.
2. **Die Sprache darf nicht einfrieren.** `web/components/explorer/ExportMenu.tsx` beschreibt die
   Falle für die Excel-Spaltenköpfe: übersetzt wird beim Bauen der Datei, nicht beim Import.
3. **Keine dritte Fassung des Verschlüsselungsformats.** Es gibt zwei (TS und Python), gesichert
   durch den sprachübergreifenden Test in `tests/test_blockcrypto.py`. Läuft der Export im Browser,
   kommt keine dazu.
4. **Keine Gedankenstriche in Oberflächentexten** (Vorgabe Sven).
5. **Analytics:** Export-Ereignisse wie im bestehenden `ExportMenu` mitzählen.

## 7. Aufwand

| Phase | grob |
|---|---|
| 1 Zusammenstellen (Migration, Route, Ansicht) | ~1 Tag |
| 2 Export Word und PDF | ~1 Tag |
| 3 Verbindung zum Fragebogen | ~halber Tag |

## 8. Was diese Funktion NICHT löst

Sie macht das Produkt nicht startfähig (s. `docs/go-live.md`), sie ersetzt keine Vorlagen-Treue,
und sie hilft einem Neuling nicht über die eigentliche Hürde: **die geforderten Referenzen, die er
nicht hat.** Gemessen 2026-10-05: nur **27,7 %** der Erstgewinner von 2022/23 haben je wieder
gewonnen, und Erstgewinne finden im normalen Wettbewerb statt (Ø 6,41 Bieter). Ein Werkzeug zum
Zusammenstellen von Angeboten verschiebt diese Quote nicht von allein.
