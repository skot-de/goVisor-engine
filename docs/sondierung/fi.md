# Sondierung Finnland

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Ein Land, zwei getrennte Welten

Finnland ist das erste Land dieser Runde, das **nicht** eine Plattform hat — und die
Aufteilung ist so scharf, dass sie erklärt werden muss:

| Plattform | Anteil | Ergebnis |
|---|---:|---|
| **`tarjouspalvelu.fi`** (Cloudia) | **82,4 %** (6.404) | ⛔ **Anmeldung** |
| **`hankintailmoitukset.fi`** (HILMA) | **9,2 %** (714) | ✅ **vollständig offen** |
| Schwanz (83 weitere Domains) | 8,4 % | gemischt |

**Und die beiden schliessen einander aus.** Über 668 finnische Ausschreibungen eines Monats:

```
546  nur Cloudia
 55  nur HILMA
  0  BEIDE
```

⚠ **Null Überschneidung.** HILMA ist damit **kein Hintereingang** zu den 82 % — eine
finnische Vergabe liegt entweder hinter der Anmeldung oder offen, nie beides.

## 2. Warum, und die Plattform sagt es selbst

Auf der HILMA-Unterlagenseite steht sinngemäss:

> *„Wenn die Bekanntmachung aus einem anderen System an Hilma gesendet wurde, findet sich
> unter ‚Anlagen und Links' nur das PDF der in Hilma veröffentlichten Bekanntmachung. Auf
> dem Reiter ‚Teilnahme und Kontakt' ist angegeben, unter welcher Adresse die
> Vergabeunterlagen erhältlich sind."*

**HILMA hostet Unterlagen nur für Verfahren, die in HILMA selbst angelegt wurden.** Alles,
was aus Cloudia kommt, bekommt dort nur die Bekanntmachung — und einen Verweis zurück.

Das ist keine Vermutung: die 0 Überschneidungen bestätigen es an den Daten.

## 3. ⛔ Cloudia (82,4 %) — Anmeldung

Sieben Adressen aus TED, jede einzeln geprüft. **Alle sieben** liefern dieselbe Hülle mit
`<input type="password">` und der Werbung für einen „Premium"-Dienst. Im Browser antwortet
die Anwendung wörtlich:

```
The tender cannot be edited
No access right to the function
```

Keine robots-Sperre (weiches 404) — die Grenze ist ein Konto, keine Regel. Nach der
stehenden Regel wird keines angelegt.

## 4. ✅ HILMA (9,2 %) — offen, und die Kette ist reine Schnittstelle

```
1  GET /web/api/public/procedure/<pid>/enotice/<nid>
       → attachments: [{ id, name, status, attachmentEntityType }, …]

2  GET https://cdn.hankintailmoitukset.fi/public-attachments/<id>
       → 200, die Datei
```

⚠ Der Pfad `/web/api/**public**/…` war nicht zu erraten — meine vier Versuche
(`/api/notices/…`, `/api/public/procedure/…`, …) gaben alle sauberes JSON-404. Gefunden
wurde er, indem die Anwendung laufen gelassen und mitgelesen wurde. **Das `/web/` davor
war der ganze Unterschied.**

**Gemessen: 6 von 7 HILMA-Vergaben tragen Anhänge, 29 von 29 Dateien geladen, 0
Fehlschläge, 6,6 MB.** Die siebte hat schlicht keine.

Der Dateihost ist ein Azure-Speicher; seine `robots.txt` gibt **401**. Wie Bulgariens S3-403
ist das die Antwort eines Objektspeichers auf ein nicht vorhandenes Objekt, keine Regel.

**Zwei Beigaben, die HILMA mitliefert:**

- Die Bekanntmachungsansicht rendert **eForms mit BT-Feldnummern** im Klartext
  (`TED BT-27: Arvioitu arvo`, `TED BT-262: Pääasiallinen luokituskoodi`). Wer die
  Feldzuordnung prüfen will, sieht sie hier ohne Umweg.
- Das CDN liefert die **eForms-SDK-Codelisten** (1.10 und 1.13) als JSON aus —
  `nuts_*`, `selection-criterion`, `contract-nature`, `number-weight` und weitere.

## 5. Der Schwanz (8,4 %, 83 Domains)

Drei Stichproben, und ein Muster in den Adressen selbst:

```
bem.buildercom.net/html/rfq2registration/index?rfqId=…
sokobid.sokopro.fi/fi/register/<hash>
public.sokopro.fi/Quotations/Signup.aspx?crypt=…
```

⚠ **`registration`, `register`, `Signup` stehen im Pfad** — die kleineren finnischen
Plattformen verlangen eine Anmeldung, und sie sagen es in der Adresse.

Dazu: `bem.buildercom.net` (1,9 %) hat eine robots.txt von 26 Bytes:
```
User-Agent: *
Disallow: /
```
⛔ Ausdrücklich gesperrt.

`sokobid.sokopro.fi` und `pris.haahtela.fi` untersagen nichts, sind aber Anwendungen ohne
sichtbaren Inhalt. **Nicht weiter geprüft** — zusammen 1,6 %.

## 6. ⚠ Ein Messfehler bei mir, der wie ein Befund aussah

Der erste Durchlauf meldete **in jeder Vergabe genau eine Datei weniger** als gelistet
(3→2, 8→7, 10→9, 3→2, 2→1, 3→2). Das sah nach einer Systematik aus — etwa ein Anhangstyp,
der nicht öffentlich ist.

Es war meine Schleife. Die Kennungsliste wurde **ohne abschliessenden Zeilenumbruch**
geschrieben, und `while read -r` verwirft eine letzte Zeile ohne Umbruch. Einzeln geprüft
lieferten alle drei Kennungen HTTP 200.

⚠ **Die Regelmässigkeit war das Verdächtige, nicht die Ausnahme.** Ein echter Ausfall trifft
mal die eine, mal die andere Datei; „immer genau eine" ist fast immer ein Zählfehler. Mit
`while IFS= read -r g || [ -n "$g" ]` waren es 29 von 29.

## 7. Ergebnis

| | |
|---|---|
| Belegt offen | **9,2 %** (HILMA), 29 von 29 Dateien |
| Anmeldung | **82,4 %** (Cloudia) + Teile des Schwanzes |
| Ausdrücklich gesperrt | 1,9 % (buildercom) |
| Hintereingang über HILMA | ❌ **nein** — 0 von 668 Vergaben liegen auf beiden |

Finnland ist damit **kein Ein-Plattform-Land**, sondern ein Zwei-Klassen-Land: wer in HILMA
ausschreibt, ist offen; wer bei Cloudia ausschreibt, ist zu. Der Anteil entscheidet sich
nicht an der Technik, sondern daran, welches Werkzeug die Vergabestelle gekauft hat.

**Nicht geprüft:** die unterschwellige Ebene (HILMA führt sie, aber der Anteil wurde nicht
gemessen) und die Fonds-Ebene.
