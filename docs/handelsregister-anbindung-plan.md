# Handelsregister in goVisor: Plan für eine anlassbezogene Anbindung

Stand 2026-10-06. Auftrag von Sven: das Modul aus `C13_handelsregister` fest in goVisor
einbauen, erst als Plan, dann umsetzen.

⚠ **Dieses Dokument ist der Plan, nicht die Umsetzung.** Die Umsetzung liegt in
`govisor/` und `scripts/`, also im Gebiet von goVisor-MAIN.

---

## 1. Die Grenze gehört an den Anfang, nicht in eine Fußnote

Das Projekt `C13_handelsregister` wurde am **2026-10-04 gestoppt** (`STOPP.md` dort), weil
Ziffer 3 der Nutzungsordnung des Registerportals wörtlich sagt:

> Die Einsichtnahme in die Rechtsträgerregister der Justiz [...] ist jedem zu
> Informationszwecken durch **einzelne Abrufe** gestattet. **Systematische Abrufe, um
> parallele Voll- oder Teilregister aufzubauen, auszubauen oder zu aktualisieren, sind
> unzulässig.**

Nicht die Geschwindigkeit ist das Problem, sondern der Zweck. Gerechnet, damit niemand aus
Versehen über die Linie läuft:

| | |
|---|---:|
| Entitäten in Gold (DE) | 325.388 |
| davon mit Registernummer | 95.107 (29,2 %) |
| Gewinner-Entitäten mit ≥ 3 Zuschlägen **ohne** Registerbezug | **28.166** |
| Abrufe, um die zu füllen (3 je Firma) | **84.498** |
| Dauer bei zulässigen 60/Stunde | **59 Tage Dauerabruf** |

⭐ **Der Zweck ist Validierung, und das ist der Unterschied.** Sven am 2026-10-06: „Es ist
kein Parallelregister. Wir validieren nur unsere Daten." Das Verbot in Ziffer 3 hängt
grammatisch am Zweck („**um** parallele Voll- oder Teilregister aufzubauen"), und
Datenvalidierung ist genau die Formulierung, die `STOPP.md` selbst als tragfähig für einen
Antrag nennt. Die Absicht ist also nicht das Problem.

⚠ **Aber die Speicherung entscheidet, ob die Aussage auch technisch stimmt.** Wer zu 28.166
Firmen Gericht, Registernummer, Status und Zweigniederlassungen ablegt, hat ein Teilregister
— unabhängig davon, wie die Tabelle heißt und was er damit vorhatte. Deshalb die
Entwurfsregel, die „wir validieren nur" wahr macht statt nur behauptet:

> **Das Urteil wird gespeichert, nicht der Registerinhalt.**
> In `register_abruf.parquet` steht, OB die Identität bestätigt wurde, ob eine
> Zweigniederlassung existiert und wann geprüft wurde. Nicht der Datensatz selbst.
> Registernummer und Gericht nur dort, wo sie ohnehin schon in den Vergabedaten stehen
> und bestätigt werden — nie als Neuzugang aus dem Register.

Damit bleibt der eigene Bestand der eigene Bestand, angereichert um eine Prüfmarke. Das ist
sachlich kein Register.

⛔ **Unabhängig vom Zweck bleibt die Mengenfrage.** Ziffer 6 erlaubt dem Portal, bei
**Verdacht** IP-Adressen zu sperren, möglicherweise dauerhaft. 84.498 Anfragen von einer
Adresse über 59 Tage erzeugen diesen Verdacht, gleichgültig wie gut die Absicht ist — und
eine Sperre träfe auch goValid. Deshalb: **kein Schritt im Nachtlauf, keine Warteschlange,
die sich selbst leert.**

Der Weg zur Menge ist der Antrag nach Ziffer 5/7 bei der Servicestelle Registerportal am
AG Hagen, mit Angabe von Umfang und Zweck — und mit genau Svens Zweckformulierung hat er
gute Aussichten. Das ist eine Geschäftsentscheidung; der Plan unten funktioniert ohne sie
und wird mit ihr nur grösser.

⚠ Ziffer 6: bei Verdacht sperrt das Portal **IP-Adressen, möglicherweise dauerhaft**. Eine
Sperre träfe jede weitere Nutzung vom selben Anschluss, auch die von goValid.

---

## 2. Wo es hilft, nach Wert geordnet

### 2.1 Identitätsnachweis vor Kundenkontakt ⭐ belegt

Am 2026-10-06 an einem echten Fall durchgeführt, drei Abrufe: vor dem Versand von Folien
an die Geschäftsführerin von H. Klostermann Baugesellschaft mbH war zu klären, ob die 513
Zuschläge, die goVisor dieser Firma zurechnet, wirklich ihre sind.

Ergebnis: **Zweigniederlassung Oranienburg, Sitz Velten 16727, eingetragen** — vorher nur
aus 320 Adressnennungen erschlossen. Und die Ansprechpartnerin steht als Person im
Register. Beides ist mit Vergabedaten grundsätzlich nicht entscheidbar.

**Nutzen:** ein falsch zugerechneter Auftrag im Profil eines Kunden beendet das Gespräch.
Drei Abrufe verhindern das. Das ist der stärkste Anwendungsfall und zugleich der
unstrittigste.

### 2.2 Beleg für einen menschlichen Merge-Entscheid

Die Verdrahtung gibt es schon: `curated/DE_entity_merge_entscheidung.csv` ist der Ort für
menschliche Entity-Entscheide (nicht `entity_aliases`, s. Auto-Memory
`govisor-merge-entscheid-wiring`). Bisher fehlte der **Beleg** für so einen Entscheid.

Der Registerabruf liefert ihn: gleicher Rechtsträger oder nicht. Am 11.09. wurde die
naheliegende Namensregel gemessen und verworfen (transitiv 1.679 Identitäten mit 25.250
Zuschlägen in einem Klumpen; `ASE GmbH` = `ASEG mbH`). Ein Abruf entscheidet den
Einzelfall, den keine Regel entscheiden kann.

⚠ Am selben Tag gegengeprüft: für „Heinrich Klostermann GmbH & Co KG" (`hr:R2404_HRA29`)
fand das Portal **0 Treffer**, und die Rückfallsuche lieferte eine fremde Firma aus
Coesfeld. Die zwei Entitäten bleiben deshalb getrennt. Ein Abruf kann also auch gegen
einen Merge entscheiden, und das ist genauso wertvoll.

### 2.3 Zweigniederlassungen → Regionszuordnung

goVisor leitet die Region eines Gewinners aus Adressen in Vergaben ab. Der Klostermann-Fall
zeigt, was dabei passiert: ihre Leistungsorte liegen in Brandenburg, der Firmensitz in NRW,
und der Käufer sitzt in Hessen. Eine **eingetragene** Zweigniederlassung ist ein Beleg
statt einer Vermutung.

Betrifft jede regionale Aussage über einen Gewinner, inklusive der Zielliste.

### 2.4 Aktueller Status, gegen einen sieben Jahre alten Bestand

goVisor nutzt den **OffeneRegister-Massenexport** (`de_companies_ocdata.jsonl`, 260 MB) —
und der ist laut eigenem Wächter `scripts/refresh_register.py` **seit dem 2019-02-05
eingefroren**. Status und Geschäftsführer darin sind sieben Jahre alt.

Für einen Lead heißt das: der Amtsinhaber kann gelöscht, verschmolzen oder insolvent sein,
und wir zeigen ihn als aktiv. ⚠ Nicht als Lauf über alle Amtsinhaber lösen (s. Abschnitt 1),
sondern anlassbezogen, wenn jemand einen konkreten Lead ansieht.

### 2.5 goValid

Anderes Projekt, gleiche Mechanik: Registerabruf als neutrale Quelle gegen selbst
beschriftete Felder (Auto-Memory `govalid-handelsregister-anbindung`). Hier nur erwähnt,
weil eine IP-Sperre beide Projekte treffen würde.

---

## 3. Was gebaut werden soll

```
govisor/register.py          Hülle um C13/scripts/erfasse_firma.py
  firma_abrufen(name, grund) → Datensatz + Protokollzeile
  aus_puffer(name)           → vorhandener Abruf, ohne Netz

data/gold/<L>/register_abruf.parquet
  je Abruf: Zeitpunkt, Suchbegriff, Grund, Gericht, Registerart, Nummer,
  Trefferzahl, Suchstufe, identitaet_bestaetigt, Zweigniederlassungen

scripts/pruefe_register_nutzung.py     ⛔ der wichtigste Teil
```

**Der Puffer ist Pflicht, nicht Komfort.** Eine Firma wird einmal abgerufen und danach
gelesen. Ohne Puffer entsteht bei jeder Ansicht ein neuer Abruf, und aus
anlassbezogener Einsicht wird unbemerkt ein Bestandsaufbau.

**Der Grund ist ein Pflichtfeld.** Ziffer 7 verlangt im Antragsfall die Angabe des Zwecks;
unabhängig davon gilt: wer nicht aufschreibt, warum er abgerufen hat, kann nicht belegen,
dass es anlassbezogen war. Erlaubte Gründe als Aufzählung im Code, nicht als Freitext.

### Die Wache, die den Missbrauch unmöglich macht

`pruefe_register_nutzung.py` schlägt an, wenn:

1. mehr als **N Abrufe am Tag** erfolgt sind (Vorschlag: 30 — die Schwelle aus der
   erwarteten Anlassmenge ableiten, sobald sie gemessen ist, nicht aus dem Gefühl),
2. ein Abruf **ohne Grund** in der Tabelle steht,
3. `register_abruf` in einem Nachtlauf-Protokoll auftaucht,
4. die Abrufe eines Tages **mehr als die Hälfte** auf denselben Grund entfallen — das ist
   das Muster eines Durchlaufs, nicht einer Einsichtnahme.

Dazu ein Test, der rot wird, wenn jemand `register.firma_abrufen` in `daily_leads.sh`,
`waechterlauf.sh` oder einen Arbeiter einträgt. ⚠ Die Prüfung muss **Kommentare strippen**,
sonst schlägt sie an diesem Dokument und an ihren eigenen Erklärtexten an (Auto-Memory
`waechter-messen-prosa-statt-code`).

---

## 4. Fallen, die beim ersten Lauf schon zugeschlagen haben

**`identitaet_bestaetigt: true` heißt NICHT, dass die gefundene Firma die gesuchte ist.**
Das Feld vergleicht Unterlagen gegen Trefferzeile, nicht Trefferzeile gegen Suchbegriff.
Bei der Coesfelder Firma stand es auf `true`, obwohl die Suche am Ziel vorbeigegangen war.
Die Hülle muss zusätzlich prüfen: stimmt der gefundene Name mit dem gesuchten überein, und
steht `stufe` auf einer Rückfallsuche (`weit_ohne_sitz`)? Beides gehört in den Datensatz
und beides muss die Oberfläche sehen.

**Die Gesellschafterfrage bleibt offen.** Das Werkzeug holt UT, SI und AD. Im SI stehen als
Organisationen nur Amtsgericht und Zweigniederlassung, keine Muttergesellschaft. Wer wissen
will, wer eine GmbH hält, braucht die **Gesellschafterliste** als eigenes Dokument. Das ist
ein eigener Baustein, kein Nebeneffekt (s. `govalid-gesellschafterliste`).

**Stille Fehlschläge im Portal.** Die Komponenten-ID wechselt je Seitenaufbau; bei einem
falschen Klick kommt die Trefferliste zurück, mit HTTP 200 und ohne Fehlermeldung.

**Personendaten.** Ein Abruf liefert Namen, Geburtsdaten und Wohnorte. Ziffer 4 bindet die
Verwendung an die DSGVO, § 8 Abs. 2 HGB untersagt die Weiterverwendung unter der
Bezeichnung „Handelsregister". In `register_abruf.parquet` gehören deshalb **keine
Personendaten**; was gespeichert wird, ist auf die Felder in Abschnitt 3 begrenzt.

**Die Drossel.** `DROSSEL = 60 s` in `erfasse_firma.py` darf nicht gesenkt werden. Die
Hülle darf sie nicht umgehen, auch nicht durch Parallelaufrufe.

---

## 5. Reihenfolge

1. Hülle + Puffer + Protokolltabelle, ohne jede Verdrahtung in einen Lauf
2. `pruefe_register_nutzung.py` + der Test gegen Lauf-Einträge — **vor** dem ersten
   produktiven Aufruf, mit Selbstprobe in beide Richtungen
3. Anwendungsfall 2.1 verdrahten: ein Knopf am Firmenprofil, „Identität prüfen"
4. Anwendungsfall 2.2: der Abruf als Beleg am Merge-Entscheid
5. Erst danach 2.3 und 2.4

⚠ Schritt 2 vor Schritt 3. Eine Anbindung ohne Wache ist der Zustand, aus dem `STOPP.md`
entstanden ist.
