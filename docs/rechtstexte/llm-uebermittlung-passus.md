# Übermittlung hochgeladener Vergabeunterlagen an einen KI-Dienst

**Vorlage für `web/app/datenschutz/page.tsx` (goVisor-SECOND).** Diese Datei ist kein
Rechtstext, sondern die gemessene Grundlage dafür plus ein fertiger Wortlaut. Sven hat am
2026-10-03 entschieden: **offen ausweisen**, nicht vorher schwärzen. Begründung: dort werden
offizielle, veröffentlichte Vergabedokumente hochgeladen, nichts Nutzerbezogenes.

---

## 1. Der gemessene Weg

```
web/app/api/lead-docs/route.ts:29     spawn python3 scripts/process_upload.py <id> <buyer> <land>
scripts/process_upload.py:33          from govisor import docpipe, docsignals, docparse,
                                           docupload, llm
scripts/process_upload.py:159         files = [(n, texts.get(n, "")) for n, _, _ in raw]
scripts/process_upload.py:170         with llm.kontext(zweck="upload", vorgang=nid):
                                          an = ad.analyze_notice(files, structured=structured)
```

Übermittelt wird der **vollständige Text** der hochgeladenen Dateien, nicht ein Auszug.

**Zweckbindung:** die Route heißt im Code „Vergabeunterlagen-Upload" und ist an eine
`notice_id` gekoppelt. Erlaubte Endungen: `zip, pdf, doc, docx, xls, xlsx, txt, htm, html`.
Es ist also der Weg für die Unterlagen EINES veröffentlichten Verfahrens, nicht für eigene
Angebotsunterlagen. Der zweite Upload-Weg (`/api/draft-check` → `scripts/draft_check.py`) ist
etwas anderes: er läuft **ohne LLM** (nur `docpipe`, `docsignals`) und speichert nichts.

## 2. ⚠ Es wird auf diesem Weg NICHT geschwärzt

`govisor/pii.py` wird von **genau einem** Modul benutzt: `govisor/blocks.py`, also am
Baustein-Import (`/api/blocks-import` → `scripts/import_blocks.py` → `blocks.py`, dort
`pii.is_mostly_personal` und `pii.redact` vor dem Speichern).

Zwischen Upload und Modellaufruf liegt in `process_upload.py` keine Zeile Schwärzung.
Gegengeprüft: `grep -n "pii\|schwaerz\|redact"` in `process_upload.py` und `analyze_docs.py`
ergibt null Treffer.

**Die Erklärung darf deshalb NICHT behaupten, personenbezogene Daten würden vor der Analyse
entfernt.** Das war meine eigene Fehlannahme am 2026-10-03; sie entstand, weil ich nur die
direkten Importe des einen Upload-Wegs geprüft hatte.

## 3. Wer verarbeitet

| Rolle | Wer |
|---|---|
| Vermittler | OpenRouter (US-Unternehmen), `openrouter.ai/api/v1` |
| Modell | `google/gemini-2.5-flash` (`govisor/llm.py:54`, Vorgabe) |
| Betreiber | Google, über Google AI Studio bzw. Google Vertex AI |

⚠ **Die Region ist nicht festgelegt.** `govisor/llm.py` hängt an das Modell die Endung
`:floor` und nimmt damit den **günstigsten** von sieben Endpunkten. Darunter sind sowohl
`google-vertex/eu` als auch `google-ai-studio/flex` und `google-vertex/global`. Der günstigste
ist nicht der EU-Endpunkt. Eine Verarbeitung außerhalb der EU ist also der Regelfall und muss
ausgewiesen werden.

ⓘ **Das ließe sich ändern**, und es ist Svens Entscheidung, nicht die des Textes: ein
Festnageln auf `google-vertex/eu` hielte die Verarbeitung in der EU, kostet aber den doppelten
Preis (0,300 statt 0,150 $/Mio Eingabe). Solange `:floor` gilt, gilt der Wortlaut unten.

## 4. Fertiger Wortlaut

> ### Analyse hochgeladener Vergabeunterlagen
>
> Wenn Sie zu einer Ausschreibung Vergabeunterlagen hochladen, werten wir diese automatisiert
> aus. Dazu übermitteln wir den Textinhalt der Dateien an einen KI-Dienst.
>
> **Empfänger.** Die Anfrage läuft über OpenRouter, einen Vermittler mit Sitz in den USA, der
> sie an ein Sprachmodell von Google weiterleitet (Google AI Studio bzw. Google Vertex AI).
> Der konkrete Rechenstandort wird nach Preis gewählt und liegt regelmäßig außerhalb der
> Europäischen Union.
>
> **Was übermittelt wird.** Der vollständige Textinhalt der von Ihnen hochgeladenen Dateien.
> Eine Entfernung personenbezogener Angaben findet vor dieser Übermittlung nicht statt.
>
> **Warum das in der Regel unkritisch ist.** Hochgeladen werden die von der Vergabestelle
> veröffentlichten Unterlagen eines Verfahrens. Diese sind öffentlich zugänglich. Soweit sie
> personenbezogene Daten enthalten, sind es typischerweise die Kontaktangaben der
> Ansprechpartner der Vergabestelle, die dort bereits veröffentlicht sind.
>
> **Was Sie dort nicht hochladen sollten.** Eigene Angebotsunterlagen, Lebensläufe oder andere
> Dokumente mit personenbezogenen Daten Ihrer Mitarbeiter. Für die Prüfung eigener Entwürfe
> gibt es einen getrennten Weg, der ohne KI-Dienst arbeitet und die Datei nicht speichert.
>
> **Rechtsgrundlage.** Die Verarbeitung erfolgt zur Erfüllung des mit Ihnen geschlossenen
> Vertrags (Art. 6 Abs. 1 lit. b DSGVO). Soweit die Unterlagen personenbezogene Daten Dritter
> enthalten, stützt sich die Verarbeitung auf unser berechtigtes Interesse an der
> automatisierten Auswertung öffentlich veröffentlichter Vergabeunterlagen (Art. 6 Abs. 1
> lit. f DSGVO).
>
> **Drittlandübermittlung.** Die Übermittlung in die USA und gegebenenfalls weitere
> Drittländer erfolgt auf Grundlage der Standardvertragsklauseln der Europäischen Kommission.

## 5. ⚠ Was der Wortlaut voraussetzt und was deshalb geprüft werden muss

1. **Der Satz „Für die Prüfung eigener Entwürfe gibt es einen getrennten Weg" muss in der
   Oberfläche auch sichtbar sein.** Steht er nur in der Datenschutzerklärung, lädt jeder
   weiterhin alles an derselben Stelle hoch. Das ist Oberflächenarbeit, nicht Rechtstext.
2. **Standardvertragsklauseln müssen tatsächlich vorliegen** — mit OpenRouter als
   Auftragsverarbeiter. Ohne abgeschlossenen Vertrag ist der letzte Absatz eine
   Falschbehauptung. Das ist eine kaufmännische Aufgabe, keine technische.
3. Ändert sich die Modellwahl oder fällt `:floor` weg, ändert sich Abschnitt 3 und damit der
   Wortlaut. `govisor/llm.py:54` ist die Stelle.
