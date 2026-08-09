# Feature #28: Unsere Bilanz & Chancenanalyse

**Produkt:** goVisor
**Version:** 1.0
**Status:** Bau-Spezifikation
**Erstellt:** 2026-07-30
**Abhängigkeiten:** #10 (Strategie), #11 (Ergebnisdaten), #23 (Dokumentkorpus), #25 (Firmenprofil), #27 (Eignungsprofil)

---

## 1. Umfang und Abgrenzung

Zwei Auswertungen auf dem eigenen Profil:

1. **Unsere Bilanz** — die eigene Vergabehistorie aus öffentlichen Zuschlägen **plus** eigenen
   Meldungen. Zeigt erstmals die echte Gewinnquote statt der sichtbaren.
2. **Chancenanalyse** — was die eigenen Angaben über die Marktposition aussagen und wo sich eine
   Investition lohnen würde.

**Abgrenzung zu bestehenden Ansichten — kein Duplikat:**

| Ansicht | Frage | Datenbasis |
|---|---|---|
| Strategie → Position (#10) | Wo stehen wir im Markt? | öffentliche Daten |
| Firmenprofil (#25) | Wer ist ein Unternehmen? | öffentliche Daten, jede Entität |
| **Unsere Bilanz (#28)** | **Was haben wir tatsächlich erreicht?** | **öffentlich + eigene Meldungen** |

Der Unterschied ist die zweite Quelle. Öffentlich sichtbar sind nur Gewinne — die eigenen
Teilnahmen kennt goVisor ausschließlich aus `user_outcomes` (#11). Genau daraus entsteht der Wert,
den keine andere Ansicht liefern kann.

**Kein Duplizieren:** Top-Vergabestellen, CPV-Verteilung und Volumen stehen bereits in #10 und #25.
Diese Ansicht **verlinkt** dorthin, statt sie nachzubauen.

---

## 2. Unsere Bilanz

### 2.1 Die zentrale Kennzahl: echte gegen sichtbare Quote

| Kennzahl | Grundlage | Aussage |
|---|---|---|
| **Sichtbare Gewinne** | öffentliche Zuschläge | „12 Zuschläge in 36 Monaten" |
| **Gemeldete Teilnahmen** | `user_outcomes` | „bei 34 Verfahren beworben" |
| **Echte Gewinnquote** | Gewinne ÷ gemeldete Teilnahmen | „35 %" |
| **Abdeckungsgrad** | gemeldete Teilnahmen ÷ geschätzte Gesamtteilnahmen | „34 von vermutlich 40 gemeldet" |

**Pflichtangabe zur Vollständigkeit.** Ohne sie ist die Quote irreführend:

> Diese Quote beruht auf 34 gemeldeten Teilnahmen. Verfahren, die ihr nicht gemeldet habt, fehlen —
> die tatsächliche Quote kann abweichen.

**Bei zu wenigen Meldungen (< 10) wird keine Quote gezeigt**, sondern die Aufforderung, weitere
Ergebnisse zu melden — mit der Angabe, wie viele noch fehlen.

### 2.2 Weitere Auswertungen

| Auswertung | Inhalt | Quelle |
|---|---|---|
| Entwicklung über Zeit | Teilnahmen, Gewinne, Quote je Jahr/Quartal | eigene Zuschläge + Meldungen |
| Nach Vergabestelle | wo gewinnen wir überdurchschnittlich, wo nicht | `agg_buyer_supplier` + Meldungen |
| Nach Segment | Quote je CPV-Bündel | dito |
| Nach Auftragsgröße | Quote je Wertband | dito |
| **Volumen öffentlicher Aufträge** | Entwicklung über die Jahre — **berechnet**, nicht abgefragt | eigene Zuschläge |
| Verlustgründe | Verteilung der beim Verwerfen angegebenen Gründe (#11) | `user_outcomes` |

### 2.3 Die nützlichste Aussage

Nicht „hier sind eure Zahlen", sondern **wo sich Bewerbungen lohnen**:

> Bei Vergabestellen, mit denen ihr bereits zusammengearbeitet habt, liegt eure Quote bei 58 % —
> bei neuen Stellen bei 19 %.

> In Aufträgen zwischen 200.000 und 500.000 € gewinnt ihr überdurchschnittlich. Darüber deutlich
> seltener.

Solche Aussagen erscheinen nur ab ausreichender Fallzahl je Kategorie (Mindestwert 5) und immer mit
Fallzahl.

---

## 3. Chancenanalyse

### 3.1 Was die Daten hergeben — und was nicht ⚠

**Ehrliche Einschränkung, die den Umfang bestimmt:** goVisor kennt die Zertifikate und Nachweise
**anderer** Firmen nicht. Sie stehen weder in TED noch im Dokumentkorpus — dort stehen die
*Anforderungen* der Vergabestellen, nicht die *Ausstattung* der Anbieter.

| Nicht möglich | Möglich |
|---|---|
| „Nur 12 von 62 Anbietern haben ISO 27001" | „In 34 % der Verfahren eures Segments wird ISO 27001 gefordert" |
| „Euer Zertifikat ist selten" | „Diese Anforderung schließt euch aus 18 Verfahren im letzten Jahr aus" |

Die zweite Formulierung ist schwächer, aber belegbar — und für die Investitionsfrage ausreichend.

### 3.2 Die Aussagen

| Aussage | Berechnung | Beispiel |
|---|---|---|
| **Anforderungshäufigkeit** | Anteil der Verfahren im Segment, die einen Anforderungstyp fordern | „Präqualifikation wird in 41 % eurer Verfahren gefordert" |
| **Entgangene Verfahren** | Verfahren, die an einer fehlenden Anforderung scheiterten | „18 Verfahren über 4,2 Mio € im letzten Jahr erforderten ISO 27001" |
| **Wirkung einer Investition** | wie viele zusätzliche Verfahren mit der Anforderung erreichbar wären | „Mit ISO 27001 kämen 18 Verfahren hinzu" |
| **Ungenutzte Stärke** | vorhandene Anforderung, die selten gefordert wird | „Eure SCC-Zertifizierung wird nur in 3 % der Verfahren gefordert" |

**Grundlage:** Dokumentkorpus (#23) + Segmentzuordnung (#27). Alle Aussagen mit Fallzahl und
Zeitraum, keine ohne.

### 3.3 Grenzen der Aussage

| Grenze | Umsetzung |
|---|---|
| Korpus-Abdeckung | Die Anforderungshäufigkeit gilt nur für Verfahren **mit analysierten Unterlagen**. Anteil ausweisen: „auf Basis von 89 von 240 Verfahren" |
| Keine Empfehlung zur Investition | goVisor zeigt die Zahl, nicht den Rat. Ob sich eine Zertifizierung lohnt, hängt an Kosten, die goVisor nicht kennt |
| Mindestfallzahl | keine Aussage unter 10 Verfahren im Segment |

---

## 4. Darstellung

Eigener Bereich unter „Unser Unternehmen" (#27), zwei Reiter: **Bilanz** und **Chancen**.

**Bilanz** beginnt mit der echten Quote plus Vollständigkeitshinweis, darunter die Aufschlüsselungen.
Wo die Datenlage dünn ist, steht die Aufforderung zum Melden statt einer schwachen Zahl.

**Chancen** listet die Anforderungstypen des Segments nach Häufigkeit, mit dem eigenen Status daneben
— erfüllt, nicht erfüllt, unbeantwortet. Die Zeilen mit „nicht erfüllt" und hoher Häufigkeit stehen
oben; das ist die Investitionsfrage.

Verweise statt Duplikate: Aus jeder Kategorie führt ein Link in die Strategie (#10) oder die
Lead-Liste, gefiltert auf die betreffende Kategorie.

---

## 5. Gate

| Element | Free | + | ++ |
|---|:---:|:---:|:---:|
| **Eigene Bilanz aus eigenen Meldungen** | ○ | ○ | ○ |
| Aufschlüsselung nach Stelle, Segment, Größe | — | ○ | ○ |
| Entwicklung über Zeit | — | ○ | ○ |
| Chancenanalyse (Anforderungshäufigkeit) | — | — | ○ |
| Entgangene Verfahren, Investitionswirkung | — | — | ○ |

**Die eigene Bilanz aus eigenen Meldungen bleibt in jeder Stufe frei.** Wer meldet, muss sehen, was
daraus wird — sonst bricht die Reziprozität (#11). Eine Bezahlschranke vor dem Ergebnis des eigenen
Beitrags wäre das falsche Signal.

Alles, was **Marktvergleich** oder **Korpusauswertung** erfordert, ist Premium — es geht über
Ausschreibungen hinweg (Preismodell §1).

---

## 6. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Zwei Reiter unter „Unser Unternehmen": Bilanz und Chancen |
| 2 | Kein Duplikat vorhandener Ansichten; Verweise auf #10 und #25 |
| 3 | Echte Quote nur ab 10 gemeldeten Teilnahmen |
| 4 | Vollständigkeitshinweis bei jeder Quotenangabe |
| 5 | Aufschlüsselungen nur ab Fallzahl 5 je Kategorie, immer mit Fallzahl |
| 6 | Volumen öffentlicher Aufträge berechnet, nicht abgefragt |
| 7 | Chancenanalyse macht **keine** Aussagen über die Ausstattung anderer Firmen |
| 8 | Anforderungshäufigkeit mit ausgewiesener Korpus-Abdeckung |
| 9 | Keine Investitionsempfehlung, nur Zahlen |
| 10 | Keine Aussage unter 10 Verfahren im Segment |
| 11 | Eigene Bilanz aus eigenen Meldungen in allen Stufen frei |

---

## 7. Offene Punkte

| # | Punkt | Zu klären |
|---|---|---|
| 1 | Schätzung der Gesamtteilnahmen (Abdeckungsgrad) | Wie viele Verfahren hat eine Firma vermutlich beworben? Näherung über Marktpräsenz — vorsichtig formulieren oder weglassen |
| 2 | Zeitpunkt der Umsetzung | Setzt genug Ergebnisdaten voraus (#11). Vor der Bootstrapping-Phase wenig sinnvoll |
| 3 | Verhältnis zur Strategie-Sektion „Position" | Prüfen, ob Teile dort besser aufgehoben sind — Doppelpflege vermeiden |
