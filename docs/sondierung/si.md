# Sondierung Slowenien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Der einfachste Abruf der ganzen Sondierung

| | |
|---|---:|
| `enarocanje.si` am Unterlagen-Feld | **100,0 %** (6.463 von 6.466, 12 Monate) |
| Domains insgesamt | 2 (die zweite ist `ec.europa.eu` mit 3 Nennungen) |
| Links ohne Verfahren | **0,0 %** |
| robots.txt | **HTTP 404, 0 Bytes** — nichts untersagt |

**Und TED verlinkt nicht die Vergabeseite, sondern die DATEI:**

```
https://www.enarocanje.si/api/datoteka/get?id=NTUyNjg2O1JEIHphIG9iamF2by56aXA
```

`datoteka` heisst Datei. Die Kennung ist Base64 und enthält beides:

```
NTUyNjg2O1JEIHphIG9iamF2by56aXA   →   552686;RD za objavo.zip
NTUyNDE0O1JEX1BCQl9vcHJlbWFfxI1pc3RvcGlzLnppcA   →   552414;RD_PBB_oprema_čistopis.zip
```

Ein GET, keine Sitzung, kein Zwischenschritt, kein Browser. **Das ist noch einfacher als
AcinGov in Portugal** — dort musste die Kennung wenigstens noch aus einer laufenden Nummer
gebildet werden; hier steht die vollständige Adresse in TED.

## 2. 39 von 39, 150 MB

Nicht ein Glückstreffer, sondern **jede Adresse eines Monats**:

| | |
|---|---:|
| geprüfte Adressen | 39 |
| erfolgreich abgerufen | **39 (100 %)** |
| Gesamtumfang | **150,3 MB** |
| im Schnitt je Datei | **3,9 MB** |

Ein ZIP von innen (1,9 MB, 13 Dateien):

```
02_RD/NAVODILA.docx                                   ← Anweisungen an die Bieter
02_RD/OBR-Vzorec pogodbe.docx                         ← Vertragsmuster
02_RD/OBR-Garancija za dobro izvedbo posla.docx       ← Erfüllungsbürgschaft
02_RD/OBR-Menična izjava za odpravo napak …           ← Gewährleistungssicherheit
02_RD/Projektna naloga.docx                           ← Projektaufgabe
02_RD/LE ON luna 143 tloris_final.pdf                 ← Grundriss
02_RD/OBR-Referencni posli gospodarskega subjekta.docx ← Referenznachweise
```

⚠ **Zwei davon sind Felder, die goVisor ohnehin auswertet**: `Garancija za dobro izvedbo`
ist die Erfüllungsbürgschaft, `Referencni posli` sind die Referenzanforderungen. Sie liegen
hier als eigene Formulardateien vor, nicht als Absatz in einem PDF.

⚠ **Umfang:** 6.466 Adressen im Jahr × 3,9 MB ≈ **25 GB jährlich** allein für Slowenien.
Anders als in Bulgarien ist hier **jede Datei ein eigener TED-Link** — die Zahl ist also
Dateien, nicht Vergaben.

## 3. ✅ Die unterschwellige Ebene, vom Ministerium selbst herausgegeben

Nach der Regel [[govisor-api-vor-abgriff]] zuerst nach der offiziellen Quelle gefragt —
und diesmal gibt es eine.

`podatki.gov.si` führt einen Datensatz des **Innenministeriums**:

> *„Seznam aktualnih javnih naročil v Informacijskem sistemu e-JN"*
> → `https://ejn.gov.si/ponudba/pages/aktualno/aktualna_javna_narocila.xhtml`

**Servergerendert, keine robots-Sperre (404), kein CAPTCHA, HTTP 200, 115 KB.** Eine
gewöhnliche Tabelle mit Käufer, Titel, Aktenzeichen, Verfahrensart, Zeitstempel und
Veröffentlichungsnummer (`JN006979/2026-SL1/01`).

**Und sie trägt weit mehr als TED.** Die 50 Vergaben einer Seite nach Verfahrensart:

| Verfahrensart | Anzahl | Ebene |
|---|---:|---|
| **Naročilo male vrednosti** (Kleinauftrag) | **31** | unterschwellig |
| Odprti postopek (offenes Verfahren) | 12 | oberschwellig |
| **Evidenčno naročilo z javno objavo** | **4** | unterhalb der Kleinauftragsschwelle |
| übrige (Verhandlung, Wettbewerb) | 3 | gemischt |

**70 % der amtlichen Liste erreicht TED nie.** Das ist die polnische Lage — eine zentrale
unterschwellige Quelle — und nicht die deutsche Zersplitterung.

⚠ Die Seite blättert über PrimeFaces-Formulare (12 Blättermarken gefunden); wie weit sie
zurückreicht und ob man ohne Sitzung durchblättern kann, ist **ungeprüft**.

## 4. ⚠ Zwei Dinge zum Merken

**Das Portal lädt reCAPTCHA — der Dateiabruf braucht es nicht.** Die Startseite von
`enarocanje.si` bindet als erstes Skript `google.com/recaptcha/api.js` ein. Trotzdem liefen
**39 von 39** Dateiabrufen ohne jede Prüfung durch.

> Die Lehre gilt über Slowenien hinaus: **ein CAPTCHA auf der Suchmaske heisst nicht, dass
> der Dateiendpunkt eines hat.** Umgekehrt hat Frankreichs AWS-Achat genau dort eines
> gesetzt, wo es zählt. Wer nach dem ersten CAPTCHA abbricht, verwechselt die beiden Fälle —
> und hätte hier ein vollständig offenes Land als gesperrt eingetragen.

**Die Kennung ist ratbar, und das nutzen wir nicht.** `552686;RD za objavo.zip` ist eine
laufende Nummer plus Dateiname. Man könnte Nummern durchprobieren; der Dateiname müsste
zwar stimmen, aber das ist keine ernsthafte Hürde. **Wir folgen nur den Adressen, die TED
nennt** — alles andere wäre ein Abgriff jenseits des Veröffentlichten und ist nicht
geprüft worden.

## 5. Fonds-Ebene

**Nicht recherchiert.** Slowenien ist Kohäsionsempfänger und gehört damit nach der Regel aus
[`fonds-ebene.md`](fonds-ebene.md) zu den Kandidaten. Ungeprüft.

## 6. Ergebnis

| | |
|---|---|
| Dokumente | ✅ **100 %**, ein einziger GET, direkt aus TED |
| robots | ✅ 404, 0 Bytes — nichts untersagt |
| Unterschwellig | ✅ amtliche Liste des Innenministeriums, **70 % der Einträge** |
| Aufwand | **ein Abrufer ohne Zustand** — der billigste der Sondierung |
| ⚠ Vorsicht | 3,9 MB je Datei, ≈ 25 GB im Jahr · Blättern der amtlichen Liste ungeprüft |

Zusammen mit Bulgarien das zweite vollständig offene Ein-Plattform-Land dieser Runde — und
im Abruf sogar einfacher, weil es keine Zwischenaufrufe braucht.
