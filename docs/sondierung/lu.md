# Sondierung Luxemburg

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Ein Portal, eine Kennung, und eine ausdrückliche Erlaubnis

| | |
|---|---:|
| `pmp.b2g.etat.lu` am Unterlagen-Feld | **87,0 %** (1.618 von 1.859) |
| verschiedene `orgAcronyme` | **1** (`t5y`, 1.252 Vorkommen) |
| Links ohne Verfahren | 1,5 % |

Die robots.txt (116 Bytes):
```
User-agent: *
Disallow:
```
⚠ Ein **leeres** `Disallow` heisst „alles erlaubt". Nach Bulgariens `Allow: /` die zweite
ausdrückliche Erlaubnis der Sondierung — und die häufigere Form davon.

Die Adressen (`/entreprise/consultation/<id>?orgAcronyme=t5y`) verraten die Software:
**ATEXO/MPE**, dieselbe Familie wie Frankreichs PLACE. ⚠ Dort scheiterte die Sondierung an
CAPTCHA und Anmeldung — **hier gibt es beides nicht.** Gleiche Software, andere
Konfiguration; das ist der Beleg, dass die Hersteller-Achse allein nicht entscheidet.

## 2. 🇪🇺 Eine Besonderheit, die kein anderes Land hat

8 % der „luxemburgischen" Ausschreibungen stammen von **EU-Institutionen mit Sitz in
Luxemburg**:

```
ec.europa.eu     6,9 %   (Funding & Tenders Portal)
eib.org          1,6 %   (Europäische Investitionsbank)
curia.europa.eu  1,5 %   (Gerichtshof der EU)
```

Wer Luxemburg anschliesst, bekommt also einen Anteil europäischer Institutionen mit — und
wer LU-Zahlen mit anderen Ländern vergleicht, vergleicht nicht dasselbe.

## 3. ⏳ Der eigentliche Fund: die Unterlagen verschwinden nach Fristende

**Das ist der erste Zeitfenster-Fall der ganzen Sondierung**, und er hat mich beinahe eine
falsche Aussage kosten.

Alle 30 Vergaben, die ich aus den TED-Paketen der letzten drei Monate zog, meldeten:

> *„Pièces de la consultation — **Aucune pièce n'a été jointe à cette consultation**"*

30 von 30. Nach der finnischen Lehre ist genau diese Regelmässigkeit verdächtig, also
habe ich **laufende** Vergaben direkt aus der Portalsuche geprüft:

| Vergabe | „Pièces de la consultation" |
|---|---|
| 543959 | **Dossier de soumission — 4,41 Mo** |
| 544217 | **Dossier de soumission — 1,41 Mo** |
| 530991 | **Dossier de soumission — 26,15 Mo** |

**Die Unterlagen sind da, solange die Frist läuft, und danach nicht mehr.**

⚠ **Folge für den Betrieb, und sie ist hart:** für Luxemburg gibt es **keine nachträgliche
Ernte**. Wer erst nach Fristende abruft, bekommt garantiert nichts — egal wie offen das
Portal ist. Ein Abrufer muss hier dem laufenden Bestand folgen, nicht dem TED-Archiv.

Kein anderes bisher geprüftes Land verhält sich so. Es gehört als eigene Frage in jede
weitere Prüfung: **wie lange bleiben die Unterlagen liegen?**

## 4. Der Abrufweg — und wo ich angehalten habe

```
/index.php?page=Entreprise.EntrepriseDemandeTelechargementDce&id=543959&orgAcronyme=t5y
```

Diese Seite ist **ohne Anmeldung und ohne CAPTCHA** erreichbar (beides geprüft). Sie ist ein
Formular mit drei Auswahlmöglichkeiten, und die dritte lautet wörtlich:

> *„Je souhaite télécharger **anonymement** le Dossier de Consultation des Entreprises et je
> ne serai donc pas informé en cas de modification de la consultation."*

Feldname: `choixAnonyme`. **Der Betreiber bietet den anonymen Bezug ausdrücklich an**, ohne
Personendaten — dieselbe Konstruktion wie Litauens `downloadDocForAnonymous`, nur als
Formular statt als Verweiskette. Frankreich hat an dieser Stelle ein CAPTCHA, Luxemburg
nicht.

⚠ **Und hier habe ich angehalten.** Ein Formular abzusenden ist eine Handlung, keine
Beobachtung — auch wenn sie keine Daten verlangt. Die stehende Regel dieser Sitzung sagt,
dass ich das nicht ohne ausdrückliche Zustimmung tue.

**Was damit belegt ist:** die Unterlagen existieren, sind bezifferbar (4,41 / 1,41 / 26,15
MB), die Seite ist ohne Anmeldung erreichbar, und der Betreiber benennt den anonymen Weg
selbst.
**Was nicht belegt ist:** dass das Absenden tatsächlich die Datei liefert. Das ist **ein
POST** — die Entscheidung darüber gehört Sven, nicht mir.

## 5. ⚠ Zwei eigene Fehler auf dem Weg

**Erstens: eine `grep`-Prüfung, die nie treffen konnte.** Nach den 8 leeren Vergaben wollte
ich das an 30 gegenprüfen und schrieb `grep -q "Aucune pièce n'a été jointe"` — auf das
**rohe HTML**, wo der Text maskiert steht (`&#39;`, Entities). Ergebnis: **„30 von 30 MIT
Anlagen"**, das exakte Gegenteil.

Zwei Messungen widersprachen sich, und beide waren meine. Aufgelöst wurde es erst, als ich
**eine einzelne Vergabe aus jeder Gruppe nebeneinander** legte — beide waren leer.

> **Die Lehre:** wer HTML durchsucht, sucht im entmaskierten Text, nie im Quelltext.
> Ein Muster mit Apostroph oder Umlaut trifft dort **systematisch nichts** — und ein
> systematischer Nichttreffer sieht aus wie ein sauberes Ergebnis.

**Zweitens: ich hätte fast „Luxemburg hängt keine Unterlagen an" geschrieben.** Acht von
acht, dann dreissig von dreissig — die Aussage war messtechnisch sauber und inhaltlich
falsch. Gerettet hat sie nur der Widerspruch zum Text der Bekanntmachungen selbst:

> *„Le cahier des charges est à la disposition des intéressés sous forme électronique, sur le
> portail des Marchés publics."*

**Wenn die Quelle etwas anderes behauptet als die Messung, hat meistens die Messung ein
Problem.**

## 6. Ergebnis

| | |
|---|---|
| robots | ✅ ausdrücklich alles erlaubt (`Disallow:` leer) |
| Anmeldung / CAPTCHA | ✅ keine |
| Unterlagen vorhanden | ✅ bei **laufenden** Vergaben (4–26 MB) |
| ⏳ nach Fristende | ⛔ **entfernt** — keine nachträgliche Ernte möglich |
| Abrufweg | 🟡 Formular mit ausdrücklicher **anonymer** Wahl — **ein POST, nicht abgesendet** |
| Besonderheit | 8 % EU-Institutionen (EIB, EuGH, Kommission) |

**Nicht geprüft:** die unterschwellige Ebene und die Fonds-Ebene.
