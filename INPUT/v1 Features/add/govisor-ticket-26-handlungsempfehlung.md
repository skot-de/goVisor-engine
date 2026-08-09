# Feature #26: Handlungsempfehlung

**Produkt:** goVisor
**Version:** 1.1
**Status:** Bau-Spezifikation
**Erstellt:** 2026-07-30
**Ersetzt:** #19 (Bid/No-Bid-Ansicht) — geht hierin auf
**Ausgelagert:** Eignungsprofil → **#27**. Dieses Ticket definiert nur, *was* es vom Profil braucht.
**Abhängigkeiten:** #2 (Relevanz), #3 (Incumbent), #11 (Ergebnisdaten), #15 (Anforderungen), #18 (Aufwand), #23 (Unterlagen-Analyse)

---

## 1. Umfang

**Handlungsempfehlung je Lead** — eine klare Aussage mit Begründung und nächstem Schritt, statt
mehrerer Einzelwerte, die der Nutzer selbst verrechnen muss.

Das **Eignungsprofil**, ohne das keine belastbare Empfehlung möglich ist, wird in **#27** spezifiziert.
Dieses Ticket legt nur die Anforderungen daran fest (§6).

**Kein Gesamtscore.** Relevanz, Chance und Aufwand haben keine gemeinsame Einheit; eine Verrechnung
zu einer Zahl behauptet eine Präzision, die nicht existiert, und lässt sich nicht begründen. Statt
einer Zahl steht eine Empfehlung, die jede Einzelbedingung erfüllen muss und in einem Satz erklärbar ist.

---

## 2. Die zwei Aussageebenen

| Ebene | Aussage | Grundlage | Stufe |
|---|---|---|---|
| **Einordnung** | beschreibt den Lead: „Hohe Passung · Amtsinhaber angreifbar" | Metadaten (E2, E3, E5, E8, E9, E10) | **Free**, unbegrenzt |
| **Handlungsempfehlung** | sagt, was zu tun ist: „Bewerben — alle Kriterien erfüllt" | zusätzlich E1, E4 aus den Vergabeunterlagen | **Pro** · in Free 3× über die Lead-Slots |

**Die Trennung läuft über die Stufe, nicht über den eigenen Upload.** Ein Pro-Kunde erhält die
Empfehlung auch dann, wenn die Unterlagen aus dem geteilten Korpus (#23) stammen und er selbst nichts
hochgeladen hat. Das ist ein Argument für Pro, kein Nachteil.

### 2.1 Drei Datenzustände — unterschiedliche Belastbarkeit

| Zustand | Verfügbar | Empfehlung |
|---|---|---|
| **A — keine Unterlagen im System** | nur Metadaten | Einordnung. Keine Empfehlung möglich; Hinweis: „Für eine Empfehlung fehlen die Vergabeunterlagen." |
| **B — Unterlagen im Korpus, nicht vom Nutzer** | Anforderungen bekannt, Abgleich gegen Profil möglich | Vollständige Empfehlung. Hinweis auf den Dokumentstand, siehe §2.2 |
| **C — Unterlagen vom Nutzer selbst** | zusätzlich Fundstellen, Checkliste, eigene Textbausteine | Vollständige Empfehlung, Belege direkt anspringbar |

### 2.2 Was der eigene Upload zusätzlich bringt

Ehrlich benannt, nicht künstlich erzeugt:

| Mehrwert | Warum |
|---|---|
| **Aktualitätssicherheit** | Die Korpus-Fassung kann veraltet sein. Nur der eigene Upload belegt den aktuellen Stand |
| **Belegkette** | Fundstellen im eigenen Dokument, nachprüfbar — entscheidend bei K.-o.-Aussagen |
| **Arbeitsebene** | Checkliste mit den eigenen Textbausteinen (#23) |

Formulierung im Zustand B:

> Diese Einschätzung beruht auf den zuletzt hinterlegten Unterlagen (Stand 15.07.2026).
> Lade deine Fassung hoch, um die Aktualität zu bestätigen und die Checkliste zu erhalten.

**Nicht verschweigen, dass Unterlagen aus dem Korpus stammen** — aber auch nicht offenlegen, wer sie
hochgeladen hat. Die Existenz einer Analyse verrät sonst, dass ein Wettbewerber am Lead arbeitet
(#23 §12.4).

### 2.3 Veraltete Korpus-Fassung

Ist für den Lead eine Änderungsbekanntmachung erkannt (#23 §7.6) und liegt keine neuere Fassung vor,
wird die Empfehlung **abgeschwächt**: aus „Bewerben" wird „Prüfen — die Unterlagen wurden am 27.07.
geändert, unsere Fassung ist vom 15.07." Keine stillschweigende Fortschreibung.

### 2.4 Korpus-Qualität als Voraussetzung

Eine Checkliste, die die Bestätigungsschwelle aus #23 §12.2 **nicht** erreicht hat, darf **keine**
Grundlage einer Empfehlung für andere Nutzer sein. Sie bleibt bis dahin auf den hochladenden Nutzer
beschränkt (Zustand C für ihn, Zustand A für alle anderen).

### 2.5 Wenn Einordnung und Empfehlung auseinanderfallen

Die beiden Kaskaden können bei demselben Lead widersprechen: Free sieht „Hohe Passung", Pro zeigt
„Nicht bewerben", weil ein Zertifikat fehlt. Inhaltlich richtig — die Einordnung kannte die
Anforderungen nicht. Ohne Erklärung wirkt es jedoch wie Willkür, gerade nach einem Upgrade.

**Regel:** Weicht die Empfehlung von der zuvor angezeigten Einordnung ab, wird der Grund benannt:

> Die Einordnung beruhte auf Metadaten. Die Vergabeunterlagen zeigen eine Pflichtanforderung
> (ISO 27001), die euer Profil nicht abdeckt.

Gilt in beide Richtungen — auch wenn aus „Geringe Passung" ein „Bewerben" wird, etwa weil die
Losstruktur ein gut passendes Einzellos enthält.

**Umsetzung:** Die zuletzt angezeigte Einordnung wird je Lead und Nutzer gespeichert. Bei Abweichung
erscheint der Hinweis einmalig im Detail, nicht dauerhaft.

---

## 3. Die Entscheidungslogik

### 3.1 Die zehn Eingangsgrößen

Alle aus vorhandenen Quellen. Keine neue Berechnung außer der Verknüpfung.

| # | Größe | Quelle | Wertebereich | Verfügbar ab |
|---|---|---|---|---|
| **E1** | **Pflichtanforderungen** | #15 + #23, Abgleich gegen Eignungsprofil | je Anforderung: erfüllt / knapp verfehlt / verfehlt / unbekannt — siehe §3.2a | Unterlagen |
| **E2** | **Relevanz** | `calculate_relevance` (#1/#2): 40 % CPV + 30 % Region + 30 % Volumen | 0–100 | Metadaten |
| **E3** | **Wettbewerbslage** | `incumbent_tenure`, `head_to_head` (Marktretention 28,3 %) | Erstvergabe / Amtsinhaber schwach / mittel / fest | Metadaten |
| **E4** | **Aufwand im Verhältnis zum Wert** | #18 (Aufwandsstufe) ÷ Auftragswert-Band | angemessen / grenzwertig / unverhältnismäßig / unbekannt — siehe §3.2b | Unterlagen |
| **E5** | **Frist** | #16: Angebotsfrist minus heute | Tage | Metadaten |
| **E6** | **Beziehung** | eigene Zuschläge bei dieser Vergabestelle (`agg_buyer_supplier`) | Anzahl, letzter Zuschlag | Metadaten |
| **E7** | **Vertragsart** | `contract_kind` (46,5 %) | Einzelauftrag / Rahmen / unbekannt | Metadaten |
| **E8** | **Vergabeart** | `award_tender_link`, `head_to_head`, `istEigen` | Erstvergabe / Folgevergabe fremd / **Folgevergabe eigen** | Metadaten |
| **E9** | **Bieterdichte** | `agg_buyer_profile.bieter_median` (Stelle) + Segment-Median über vergleichbare Verfahren | Median + Fallzahl, je Bezug | Metadaten |
| **E10** | **Losstruktur** | `lead_lot` (#12) | Anzahl Lose, Relevanz je Los | Metadaten |

**Nicht verwendet und warum:**

| Nicht verwendet | Grund |
|---|---|
| Auftragswert als absolute Größe | nur 65 % echt, Bandtreffer 42 % — fließt über E2 (Volumen-Match) und als Bezugsgröße in E4 ein, nie als eigene Bedingung |
| **Kapazität des Nutzers** | Ob Ressourcen frei sind oder extern nachgerüstet wird, ist eine Unternehmensentscheidung — goVisor maßt sie sich nicht an |
| Zuschlagskriterien-Gewichtung (Preis/Qualität) | in 52 % der Verfahren nicht auffindbar — als Hinweis anzeigen, nicht als Bedingung |
| Eigene Gewinnquote | erst ab 10 eigenen Meldungen belastbar (#11) — später ergänzen, siehe §3.6 |
| Bieterzahl-Prognose | nur für die Käuferseite gemessen, für Bieter nicht validiert |

### 3.2 Die Schwellen

| Größe | Schwelle | Herleitung |
|---|---|---|
| **E1 erfüllt** | alle als *Zitat* belegten Pflichtanforderungen im Profil mit „ja" beantwortet | — |
| **E1 verletzt** | mindestens eine als *Zitat* belegte Pflichtanforderung mit „trifft nicht zu" beantwortet | — |
| **E2 hoch** | ≥ 70 | CPV-Treffer plus mindestens eine weitere Dimension |
| **E2 mittel** | 45–69 | eine Dimension trägt allein |
| **E2 niedrig** | < 45 | — |
| **E3 günstig** | Erstvergabe **oder** Amtsinhaber < 3 Jahre **oder** Segment-Wechselquote > 40 % | Marktretention liegt bei 28,3 %; darüber ist Verdrängung überdurchschnittlich häufig |
| **E3 ungünstig** | Amtsinhaber ≥ 3 Verlängerungen **oder** Segment-Wechselquote < 15 % | — |
| **E4 vertretbar** | angemessen oder grenzwertig (§3.2b) | Verhältnis Aufwand ÷ Auftragswert |
| **E5 ausreichend** | verbleibende Tage ≥ Median-Bearbeitungszeit vergleichbarer Verfahren | segmentabhängig aus `lead_duration` |
| **E5 knapp** | 50–99 % dieses Medians | — |
| **E5 unzureichend** | < 50 % | — |
| **E6 vorhanden** | ≥ 1 eigener Zuschlag bei dieser Vergabestelle in 36 Monaten | — |
| **E8 Erstvergabe** | kein Vorgängerverfahren über `award_tender_link` auffindbar | strukturell offenes Feld — kein Amtsinhaber-Vorsprung |
| **E8 eigen** | das eigene Profil ist der Amtsinhaber (`istEigen`) | kehrt die Logik um → §3.7 |
| **E9 belastbar** | Fallzahl ≥ 8 vergleichbare Verfahren | darunter wird der Wert **nicht angezeigt**, sondern als unbekannt markiert |
| **E9 günstig** | Median ≤ 3 Bieter | wenig Konkurrenz |
| **E9 ungünstig** | Median ≥ 7 Bieter | starkes Feld |
| **E10 teilbar** | ≥ 2 Lose **und** Relevanz mindestens eines Loses ≥ 70 | Bewerbung auf ein Los senkt Aufwand und Risiko |

Alle Schwellen sind **konfigurierbar** und werden gegen die Ergebnisdaten kalibriert (§8).

### 3.2a Anforderungstypen — binär oder schwellenbasiert

Nicht jede Anforderung ist ein Ja-Nein. Zwei Typen mit unterschiedlicher Behandlung:

| Typ | Beispiele | Auswertung |
|---|---|---|
| **Binär** | Zertifikat, Präqualifikation, Eigenerklärung, Berufshaftpflicht | erfüllt / verfehlt / unbekannt |
| **Schwellenbasiert** | Mindestumsatz, Referenzanzahl, Referenzwert, Mitarbeiterzahl, Jahre am Markt | Vergleich Profilwert gegen Anforderungswert |

**Auswertung schwellenbasierter Anforderungen:**

| Verhältnis Profilwert ÷ Anforderung | Ergebnis |
|---|---|
| ≥ 1,0 | **erfüllt** |
| 0,85 – 0,99 | **knapp verfehlt** |
| < 0,85 | **verfehlt** |

**Wirkung auf die Regeln:**
- *verfehlt* löst B1 aus (nicht bewerben)
- *knapp verfehlt* löst **nicht** B1 aus, sondern führt über B5 zu **NOCH ZU KLÄREN** mit Benennung:
  „Geforderter Mindestumsatz 2,0 Mio € — euer hinterlegter Wert 1,9 Mio €. Prüft, ob eine
  Eignungsleihe oder ein aktuellerer Abschluss in Frage kommt."

Begründung für die 85-%-Grenze: Ein knappes Verfehlen ist häufig durch aktuellere Zahlen,
Eignungsleihe oder Bietergemeinschaft heilbar — ein klares Verfehlen selten. Ein hartes Nein wäre
hier eine Fehlentscheidung.

**Referenzen mit Zeitfenster** („drei Referenzen aus den letzten fünf Jahren über je 500.000 €")
werden dreifach geprüft: Anzahl, Wert, Alter. Fällt eine Referenz aus dem Zeitfenster, zählt sie nicht.

### 3.2b Aufwand im Verhältnis zum Wert (E4)

Ein absoluter Aufwandswert ist wertlos ohne Bezug. Fünf Personentage bei 80.000 € sind
unverhältnismäßig, bei 2 Mio € trivial.

| Aufwandsstufe (#18) | angemessen ab Auftragswert |
|---|---|
| gering | immer |
| mittel | ≥ 150.000 € |
| hoch | ≥ 500.000 € |

⚠ **Diese Schwellen sind vorläufige Startwerte, nicht hergeleitet.** Sie müssen kalibriert werden:
Aus `lead_export` je Aufwandsstufe die Verteilung der Auftragswerte auswerten und die Schwelle dort
setzen, wo Bewerbungen in der Praxis noch stattfinden. Bis dahin als Annahme kennzeichnen, nicht als
gemessenen Wert (§10).

| Ergebnis | Bedingung |
|---|---|
| **angemessen** | Auftragswert erreicht die Schwelle der Aufwandsstufe |
| **grenzwertig** | Wert liegt bei 60–99 % der Schwelle |
| **unverhältnismäßig** | Wert unter 60 % der Schwelle |
| **unbekannt** | kein echter Wert vorhanden (35 % der Fälle) |

**Bei unbekanntem Wert wird E4 auf die absolute Aufwandsstufe zurückgesetzt** und die Unsicherheit
in der Begründung benannt: „Aufwand hoch, Auftragswert nicht veröffentlicht — Verhältnis nicht
bewertbar." Kein geschätzter Wert als Entscheidungsgrundlage (Bandtreffer nur 42 %).

**Bei Rahmenverträgen (E7)** wird der Nennwert nicht als Obergrenze behandelt — Hinweis aus dem
Rahmenvertrag-Signal: real wird oft ein Vielfaches abgerufen. Die Verhältnisprüfung entfällt, der
Aufwand wird absolut bewertet.

### 3.3 Die Entscheidungsregel

Zwei Kaskaden — je nach Datenzustand (§2.1).

#### A · Einordnung (Zustand A, und Free-Ansicht in allen Zuständen)

Beschreibt, ohne zu empfehlen. Reihenfolge bindend, erste zutreffende gewinnt.

```
A1  E8 = eigen
    → BESTANDSVERTRAG    "läuft aus — Folgeausschreibung"

A2  E2 < 45
    → GERINGE PASSUNG    Grund: CPV/Region/Volumen

A3  E5 unzureichend
    → FRIST ZU KNAPP     Grund: verbleibende Tage

A4  E2 ≥ 70 UND E3 günstig
    → HOHE PASSUNG       Gründe: Passung + Wettbewerbslage

A5  E2 ≥ 70
    → HOHE PASSUNG       Grund: Passung

A6  sonst
    → PASSUNG MITTEL
```

Zusätzlich ein Hinweis, wenn keine Unterlagen vorliegen:
„Für eine Empfehlung fehlen die Vergabeunterlagen."

#### B · Handlungsempfehlung (Zustand B und C, Pro)

```
B0  E8 = eigen
    → VERTEIDIGEN        (eigener Zweig, §3.5)

B1  E1 verfehlt (Zitat belegt UND Profil sagt ausdrücklich nein
    ODER Schwellenwert < 85 %)
    → NICHT BEWERBEN     Grund: das konkrete Kriterium
    Ausnahme: Zusatz "mit Partner" (§3.4) → NOCH ZU KLÄREN

B2  E5 unzureichend (< 50 % der Median-Bearbeitungszeit)
    → NICHT BEWERBEN     Grund: Frist reicht für den Aufwand nicht

B3  E2 < 45
    → NICHT BEWERBEN     Grund: geringe Passung zum Profil

B4  E4 unverhältnismäßig (Aufwand ÷ Auftragswert, §3.2b)
    → NICHT BEWERBEN     Grund: Aufwand steht nicht im Verhältnis
    Ausnahme: E10 teilbar → NOCH ZU KLÄREN mit Zusatz "einzelnes Los"

B5  E1 unbekannt ODER knapp verfehlt (85–99 %)
    → NOCH ZU KLÄREN     Grund: die konkrete offene Frage

B6  E1 erfüllt UND E2 ≥ 70 UND E3 günstig UND E4 vertretbar
    UND E5 ausreichend UND NICHT E9 ungünstig
    → BEWERBEN           Gründe: die drei stärksten Bedingungen

B7  E1 erfüllt UND genau eine Bedingung aus {E3, E4, E5, E9} ungünstig
    → NOCH ZU KLÄREN     Grund: die ungünstige Bedingung

B8  E1 erfüllt UND ≥ 2 Bedingungen aus {E3, E4, E5, E9} ungünstig
    → NICHT BEWERBEN     Gründe: alle ungünstigen Bedingungen

B9  sonst
    → NOCH ZU KLÄREN
```

**Reihenfolge-Begründung:** B1–B4 sind Ausschlussgründe und stehen vor allen Abwägungen. B3 (geringe
Passung) muss vor den Abwägungsregeln liegen — sonst greift sie nie, weil B7/B8 vorher zuschlagen.

#### „Noch zu klären" — die Regel dahinter

Ersetzt das frühere „Prüfen". **Nie ohne konkrete offene Frage.** Eine Empfehlung, die nur zum
Nachdenken auffordert, nimmt dem Nutzer nichts ab.

| Auslöser | Ausgabe |
|---|---|
| B5, E1 unbekannt | „Habt ihr ISO 27001? Eine Angabe genügt." → direkt beantwortbar |
| B5, knapp verfehlt | „Mindestumsatz 2,0 Mio € gefordert, hinterlegt 1,9 Mio €. Eignungsleihe prüfen." |
| B7, E3 ungünstig | „Amtsinhaber seit 8 Jahren, 3 Verlängerungen — Verdrängung ist unwahrscheinlich." |
| B7, E9 ungünstig | „Bei dieser Stelle traten im Median 8 Bieter an (n=22)." |
| B1-Ausnahme Partner | „Fachplanung fehlt — über eine Bietergemeinschaft abdeckbar." |

Jede Ausgabe endet mit einer **Handlung**: Angabe ergänzen, Partner suchen, Lead verwerfen.

### 3.4 Die Zusätze

Unabhängig von der Hauptempfehlung, kumulierbar.

| Zusatz | Bedingung | Wirkung |
|---|---|---|
| **mit Partner** | E1 verletzt, aber die fehlende Anforderung ist durch Bietergemeinschaft erreichbar (Mehr-Los-Vergabe **oder** ergänzende Leistung, die ein Netzwerkpartner abdeckt) | wandelt B1 von „nicht bewerben" in „noch zu klären — mit Partner möglich" |
| **Frist knapp** | E5 knapp | Hinweis, ändert die Empfehlung nicht |
| **Rahmenvertrag** | E7 = Rahmen | Volumenhinweis: Nennwert ist Ober-/Schätzgrenze |
| **bekannte Stelle** | E6 vorhanden | verstärkender Grund bei „bewerben", kein eigener Auslöser |
| **Erstvergabe** | E8 = Erstvergabe | verstärkender Grund: kein Amtsinhaber-Vorsprung, offenes Feld |
| **einzelnes Los** | E10 teilbar | „Bewerbung auf Los N möglich — geringerer Aufwand" |
| **Bieterdichte** | E9 belastbar | Kontextangabe, siehe §3.6 |
| **Zuschlagsgewichtung** | Preis-/Qualitätsanteil aus den Unterlagen erkannt | Hinweis zur Angebotsstrategie, siehe §3.7 |
| **Entfernung** | Geodaten vorhanden (`lead_geo`, 99,8 %) | Hinweis: Luftlinie zum Leistungsort |

**Anzeige-Priorisierung:** Höchstens **zwei** Zusätze gleichzeitig, in dieser Rangfolge:
mit Partner → einzelnes Los → Frist knapp → Bieterdichte → Rahmenvertrag → Erstvergabe →
bekannte Stelle → Zuschlagsgewichtung → Entfernung. Die übrigen erscheinen im Detail, nicht in der Liste.

**„Mit Partner" ist die einzige Ausnahme von B1** — und nur, wenn die Lücke tatsächlich teilbar ist.
Eine fehlende Firmenzertifizierung ist es nicht, eine fehlende Fachleistung schon.

### 3.5 Der Verteidigungsfall (B0)

**Abgrenzung zuerst:** Es gibt zwei verschiedene Zustände, die nicht vermischt werden dürfen.

| Zustand | Wo | Zuständig |
|---|---|---|
| Eigener Vertrag läuft aus, **noch keine Ausschreibung** | Cockpit (#17), Auslauf-Radar | nicht dieses Ticket |
| Die Folgeausschreibung **ist veröffentlicht** | Lead-Liste, Phase „Ausschreibung offen" | **B0** |

Nur der zweite Fall gehört hierher. B0 greift, wenn das eigene Profil über `award_tender_link` als
Vorgänger des ausgeschriebenen Verfahrens erkannt wird.

**Was sich ändert:** Es geht nicht um Chance und Aufwand, sondern um Bestandsschutz. Die Frage
„lohnt sich das" stellt sich nicht — der Umsatz ist bereits da und steht zur Disposition.

| Element | Verhalten |
|---|---|
| Empfehlung | **Verteidigen** — eigener Zweig, keine der Regeln B1–B9 |
| Dringlichkeit | aus E5 und dem Volumen des Bestandsvertrags |
| Kontext | eigene Bindungsdauer, bisherige Verlängerungen, Segment-Wechselquote |
| Warnung bei hoher Wechselquote | „In diesem Feld wechseln Verträge zu 44 % — Verteidigung nicht selbstverständlich" |
| **K.-o.-Prüfung läuft trotzdem** | Sind die Anforderungen gegenüber dem Vorverfahren gestiegen und erfüllt ihr sie nicht mehr, wird das ausdrücklich benannt |

Der letzte Punkt ist der wichtigste: Eine Folgeausschreibung kann strengere Kriterien enthalten als
die vorige. Wer sich auf den Bestand verlässt, übersieht das leicht. Erkennbar durch Vergleich der
Anforderungen beider Verfahren, sofern für beide Unterlagen vorliegen.

### 3.6 Bieterdichte (E9) — zwei Bezüge

| Bezug | Quelle | Aussage |
|---|---|---|
| **Vergabestelle** | `agg_buyer_profile.bieter_median` | Zuschnittspraxis dieser Stelle |
| **Segment** | Median über vergleichbare Verfahren (CPV + Region + Größenordnung) | Marktlage im Feld |

**Auswahl:** Bei Erstvergaben (E8) trägt der **Segmentwert**, da für diese Leistung keine Historie
der Stelle existiert. Bei wiederkehrenden Vergaben ist der **Stellenwert** aussagekräftiger.
Liegen beide vor, werden beide gezeigt.

**Die Differenz ist selbst eine Aussage.** Zieht eine Stelle im Schnitt 2 Bieter an, das Segment aber
6, liegt es an ihrem Zuschnitt — weniger Konkurrenz, aber möglicherweise eine Hürde.

**Pflichtangaben:** immer mit Fallzahl („Median 4 über 38 vergleichbare Verfahren"). Unter 8 Fällen
wird der Wert nicht gezeigt, sondern als unbekannt markiert.

**Formulierung:** rückwärtsgewandt, nie als Prognose. „Bei vergleichbaren Verfahren traten im Median
4 Bieter an" — nicht „es werden 4 Bieter antreten". Wie viele bei dieser Ausschreibung antreten,
weiß niemand vorher.

### 3.7 Hinweise ohne Regelwirkung

Zwei Größen informieren, ohne die Empfehlung zu verändern. Grund: Sie sind entweder zu lückenhaft
(Gewichtung) oder branchenabhängig unterschiedlich relevant (Entfernung).

**Zuschlagsgewichtung.** In 52 % der Verfahren nicht auffindbar — als Bedingung damit unbrauchbar.
Wo erkannt, ändert sie aber die Angebotsstrategie erheblich:

| Konstellation | Hinweis |
|---|---|
| Preisanteil ≥ 70 % | „Überwiegend Preisentscheidung — die Kalkulation entscheidet." |
| Preisanteil ≤ 40 % | „Hoher Qualitätsanteil — Konzeptarbeit lohnt sich." |
| Punktesystem erkannt | größter Einzelposten der Qualitätswertung wird benannt |
| nicht auffindbar | „Zuschlagskriterien in den Unterlagen nicht eindeutig auffindbar." |

**Entfernung.** Luftlinie zwischen Firmensitz und Leistungsort aus `lead_geo`. Bei Lieferleistungen
meist irrelevant, bei Vor-Ort-Dienstleistungen ein realer Kostenfaktor. Wird als Zahl angezeigt,
nicht bewertet — die Einschätzung, ab wann eine Entfernung zu groß ist, trifft der Nutzer.

### 3.8 Beispiele

| Fall | E1 | E2 | E3 | E4 | E5 | Ergebnis |
|---|---|---|---|---|---|---|
| Idealfall | erfüllt | 82 | Amtsinhaber 2 J. | mittel | 12 T (Median 9) | **Bewerben** — alle Kriterien erfüllt, Amtsinhaber schwach gebunden, dort bereits geliefert |
| Fehlendes Zertifikat | ISO 27001 „nein" | 88 | günstig | gering | 20 T | **Nicht bewerben** — ISO 27001 ist Pflicht, nicht vorhanden |
| Unklares Profil | ISO 27001 unbekannt | 88 | günstig | gering | 20 T | **Prüfen** — habt ihr ISO 27001? |
| Festgefahren | erfüllt | 76 | 4 Verlängerungen | hoch | 30 T | **Nicht bewerben** — Amtsinhaber fest gebunden, hoher Aufwand |
| Zeitnot | erfüllt | 90 | günstig | hoch | 3 T (Median 11) | **Nicht bewerben** — Frist reicht für den Aufwand nicht |
| Teilbar | Fachplanung fehlt | 74 | günstig | mittel | 25 T | **Prüfen — mit Partner möglich** (Los 2 abdeckbar) |
| Erstvergabe, dünnes Feld | erfüllt | 78 | Erstvergabe | mittel | 18 T | **Bewerben** — kein Amtsinhaber, im Segment traten im Median 3 Bieter an (n=41) |
| Starkes Feld | erfüllt | 71 | günstig | hoch | 15 T | **Prüfen** — bei dieser Stelle traten im Median 8 Bieter an (n=22) |
| Eigener Vertrag | erfüllt | 85 | **wir sind Amtsinhaber** | mittel | 40 T | **Verteidigen** — Bestandsvertrag 640.000 € läuft aus, Wechselquote im Feld 44 % |
| Knappe Verfehlung | Umsatz 1,9 / 2,0 Mio | 80 | günstig | angemessen | 22 T | **Prüfen** — Mindestumsatz knapp verfehlt (95 %), Eignungsleihe prüfen |
| Aufwand unverhältnismäßig | erfüllt | 76 | günstig | hoch bei 95.000 € | 20 T | **Nicht bewerben** — Aufwand steht nicht im Verhältnis zum Auftragswert |

### 3.9 Profil-Kaltstart — Sonderbehandlung

**Das Problem:** Bei neuem Profil ist E1 zu jeder Anforderung „unbekannt". Über B5 landet damit
**jeder** Lead bei „Noch zu klären" — dreißig Zeilen mit derselben Aussage. Das ist der Regelfall
bei Neukunden, nicht die Ausnahme, und die schlechteste denkbare Erstnutzung.

**Regel:** Unterschreitet das Eignungsprofil die Mindestabdeckung, wird **Kaskade B ausgesetzt** und
die Liste zeigt die Einordnung (Kaskade A) — auch für Pro-Kunden.

| Schwelle | Wert |
|---|---|
| Mindestabdeckung | zu ≥ 60 % der Katalogpunkte des eigenen Segments liegt eine Angabe vor |
| darunter | Kaskade A + Profil-Band (§4.3) |
| darüber | Kaskade B, fehlende Einzelangaben über B5 |

Begründung: Ohne Profil *kann* goVisor nicht empfehlen. Die Einordnung zu zeigen ist ehrlicher als
dreißigmal zur Klärung aufzufordern — und sie ist sofort nützlich.

### 3.10 Alterung der Empfehlung

E5 (Frist) verändert sich täglich, E1 bei Profiländerungen, E4 bei neuen Unterlagen. Eine einmal
berechnete Empfehlung veraltet.

| Auslöser für Neuberechnung | Frequenz |
|---|---|
| Fristablauf rückt näher | täglich für alle Leads mit offener Frist |
| Profil geändert | sofort für betroffene Leads |
| Neue Dokumentversion im Korpus | sofort |
| Änderungsbekanntmachung erkannt | sofort (§2.3) |

**Warnung vor dem Kippen — Pflicht bei beobachteten Leads:** Fällt ein Lead aus der Merkliste oder
dem Cockpit demnächst von „Bewerben" auf „Nicht bewerben" (weil E5 unter die Schwelle rutscht), wird
**vorher** gewarnt:

> Für „Website Development" bleiben noch 6 Tage. Vergleichbare Verfahren brauchen im Median 9 Tage
> Bearbeitung — die Empfehlung kippt in 2 Tagen.

Ohne diese Warnung erlebt der Nutzer eine stille Verschlechterung und verliert die Chance, ohne es
zu merken. Bei nicht beobachteten Leads entfällt die Warnung (sonst Alarm-Flut).

### 3.11 Später zu ergänzen

Sobald genug Ergebnisdaten vorliegen (#11):

| Größe | Wirkung | Voraussetzung |
|---|---|---|
| eigene Gewinnquote im Segment | verschärft oder lockert E2-Schwelle | ≥ 10 eigene Meldungen |
| Wettbewerbsmenge des Verfahrens | E3 wird präziser (echte statt geschätzte Bieterzahl) | Reziprozitäts-Schwelle erreicht |
| bekannte Mitbieter | Zusatzhinweis „X hat hier zweimal gewonnen" | Ergebnisdaten-Pool |

---

## 4. Darstellung

### 4.1 In der Liste

**Eine Spalte, zwei Inhalte — kein Blur, keine zweite Spalte, keine leeren Zellen.**

Die bestehende Spalte „Empfehlung" trägt je nach Stufe:

| Stufe | Inhalt | Beispiel |
|---|---|---|
| Free | Einordnung (Kaskade A) | `Hohe Passung` · *Amtsinhaber angreifbar · keine Unterlagen* |
| Pro | Handlungsempfehlung (Kaskade B) | `Bewerben` · *alle Kriterien erfüllt · Amtsinhaber schwach* |

Begründung gegen Blur: Ein weichgezeichnetes Einzelwort in einer Tabellenzelle wirkt wie ein
Darstellungsfehler, nicht wie ein Wert. Blur trägt nur, wo eine Struktur erkennbar bleibt (Tabellen,
Diagramme) — nicht bei einem Wort.

**Free bleibt damit vollständig brauchbar.** Der Unterschied wird beim Wechsel erlebt, nicht durch
eine kaputte Ansicht demonstriert.

**Farbgebung** (beide Kaskaden):

| Aussage | Darstellung |
|---|---|
| Bewerben / Hohe Passung | grün |
| Verteidigen / Bestandsvertrag | blau |
| Noch zu klären / Passung mittel | neutral |
| Nicht bewerben / Geringe Passung / Frist zu knapp | gedämpft, nicht rot — es ist keine Warnung, sondern eine Einordnung |

**Sortierung:** Standard nach Aussagestärke, dann Frist aufsteigend. Funktioniert in beiden Stufen —
in Free nach Einordnung, in Pro nach Empfehlung.

**Free-Slots:** Wer einen Lead aufschließt, sieht dort die volle Empfehlung. In der Liste bleibt bei
allen übrigen Leads die Einordnung stehen. Kein Mischzustand in der Spalte.

### 4.2 Im Detail

Empfehlung, darunter die **vollständige Begründungskette** — jede Bedingung mit Zustand und Quelle:

| Größe | Zustand | Quelle |
|---|---|---|
| E1 Pflichtanforderungen | 6 von 6 erfüllt | Teil A Bewerbungsbedingungen, S. 7–9 |
| E2 Relevanz | 82 — hoch | CPV ✓ · Region ✓ · Volumen im Band |
| E3 Wettbewerbslage | Amtsinhaber seit 2 Jahren, Bindung schwach | incumbent_tenure |
| E4 Aufwand | mittel — Bürgschaft, 6 Nachweise, 4 Kriterien | #18 |
| E5 Frist | 12 Tage · Median vergleichbarer Verfahren 9 Tage | lead_duration |
| E6 Beziehung | 2 Zuschläge bei dieser Stelle seit 2023 | agg_buyer_supplier |
| E7 Vertragsart | Einzelauftrag | contract_kind |

Jede Zeile ist anklickbar und führt zur Quelle — beim Zitat in die Fundstelle im Dokument, beim
Amtsinhaber ins Firmenprofil (#25).

**Nächster Schritt** als konkrete Handlung: „Unterlagen in der Checkliste abarbeiten — 6 Punkte offen."

#### Free-Ansicht im Detail

Hier — und nur hier — trägt eine Vorschau: Der Block ist sichtbar, die Struktur erkennbar, die aus
Metadaten ableitbaren Zeilen (E2, E3, E5, E8, E9, E10) sind gefüllt. Die Zeilen E1 und E4 sind
gesperrt mit konkretem Hinweis:

> Anforderungsabgleich und Aufwandsbewertung sind Teil von Pro. Damit wird aus der Einordnung eine
> Empfehlung.

Das entspricht der Regel aus dem Preismodell: Wo die Struktur die Botschaft ist, wird sie gezeigt.

### 4.3 Profil-Band bei Kaltstart

Erscheint über der Liste, wenn die Mindestabdeckung (§3.9) unterschritten ist. **Band, kein
Pseudo-Lead in der Liste** — ein künstlicher Listeneintrag bricht Sortierung und Filter.

```
┌────────────────────────────────────────────────────────────────┐
│  5 Angaben fehlen — damit werden 40 eurer Leads bewertbar      │
│                                                                │
│  3 von 8 Angaben haben wir aus euren öffentlichen Zuschlägen   │
│  übernommen. Diese 5 kennen nur ihr:                           │
│                                                                │
│  Mindestumsatz letzte 3 Jahre    [        ] Mio €              │
│  ISO 9001                        [ ja ] [ nein ]               │
│  ISO 27001                       [ ja ] [ nein ]               │
│  Präqualifikation                [ ja ] [ nein ]               │
│  Berufshaftpflicht Deckung       [        ] Mio €              │
│                                                                │
│  [ Speichern ]                          Später ergänzen        │
└────────────────────────────────────────────────────────────────┘
```

**Regeln:**

| Punkt | Verhalten |
|---|---|
| Auswahl der Fragen | die häufigsten unbeantworteten Anforderungstypen **der aktuell angezeigten Leads**, nicht ein generischer Katalog |
| Anzahl | maximal 5 gleichzeitig — beantwortbar in wenigen Minuten |
| Vorbefüllung | ausgewiesen („3 von 8 aus euren Zuschlägen übernommen"), als *abgeleitet* markiert und bestätigbar |
| Wirkung | konkret beziffert („damit werden 40 Leads bewertbar"), nicht abstrakt |
| Beantwortung | direkt im Band, kein Sprung ins Formular |
| Verschwinden | sobald die Mindestabdeckung erreicht ist — danach nur noch Hinweis im Profilbereich |
| Wegklickbar | ja, kehrt bei der nächsten Sitzung zurück, solange die Abdeckung fehlt |

**Nicht:** „Fülle dein Profil aus." Eine Aufgabe ohne Ende und ohne sichtbaren Nutzen wird aufgeschoben.

### 4.4 Widerspruch

Der Nutzer kann jeder Empfehlung widersprechen („wir bewerben uns trotzdem" / „wir lassen es").
Der Widerspruch wird gespeichert und ist Grundlage der Qualitätsmessung (§8). Er wird **nicht**
kommentiert oder verteidigt.

---

## 5. Kein enger Standardfilter ⚠

**Ausdrückliche Entscheidung gegen einen Vorschlag aus der Konzeptphase:** Die Liste zeigt
standardmäßig **nicht** nur die Top-Empfehlungen.

Begründung: Wenn die Standardansicht nur „Bewerben"-Leads zeigt, sieht der Nutzer nie, was
ausgeblendet wurde. Eine falsche Empfehlung wird damit unsichtbar — er verpasst eine echte Chance
und merkt es nie. Das ist ein größeres Risiko als eine lange Liste.

**Stattdessen:**
- Empfehlung als **Sortierung** (Standard: Empfehlung absteigend, dann Frist)
- Filter verfügbar, aber nicht vorbelegt
- Bei aktivem Filter **immer sichtbar**, wie viel ausgeblendet ist: „38 weitere Leads ausgeblendet"

---

## 6. Was dieses Ticket vom Profil braucht (Schnittstelle zu #27)

Die Empfehlung ist nur so gut wie das Eignungsprofil. #27 spezifiziert es; hier stehen die
Anforderungen, die aus der Entscheidungslogik folgen.

| Anforderung | Warum |
|---|---|
| **Angabe je Anforderungstyp**: ja / nein / Wert / unbeantwortet | B1 und B5 unterscheiden „verfehlt" von „unbekannt" — ein ausdrückliches „trifft nicht zu" ist etwas anderes als eine Lücke |
| **Schwellenwerte numerisch** (Umsatz, Referenzanzahl, Referenzwert, Mitarbeiterzahl) | §3.2a rechnet Verhältnisse, nicht Ja/Nein |
| **Referenzen mit Wert und Datum** | Anforderungen mit Zeitfenster („letzte 5 Jahre") prüfbar |
| **Ablaufdatum bei Zertifikaten** | abgelaufen zählt nicht als erfüllt |
| **Abdeckungsgrad je Segment** | §3.9 setzt Kaskade B unter 60 % aus |
| **Branchenzuordnung** | bestimmt den maßgeblichen Anforderungskatalog |
| **Änderungszeitpunkt je Angabe** | §3.10 berechnet betroffene Leads neu |

**Nicht Teil von #26:** Aufbau des Katalogs, Erfassungswege, Aktualitätspflege, Navigation,
Nachweis-Upload, Team-Zuschreibung, Ausschlusskriterien, Zielrichtung. Alles in #27.

## 7. Rechtliche Leitplanken

| Regel | Umsetzung |
|---|---|
| **Einordnung, keine Anweisung** | Formulierung „die Kriterien sprechen für eine Bewerbung", nicht „bewerbt euch unbedingt" |
| **Nie ohne Begründung** | Die Empfehlung erscheint immer mit der Bedingungstabelle (§4.2) — sie behauptet nicht, sie legt offen |
| **Keine Tatsachenbehauptung ohne Beleg** | „Alle Kriterien erfüllt" nur, wenn jede Anforderung als Zitat belegt ist (#23 §6a.2) |
| **Keine Rechtsberatung** | Keine Bewertung vergaberechtlicher Zulässigkeit, keine Fristenberatung über die reine Datumsangabe hinaus |
| **Hinweis** | Einschätzung auf Basis öffentlicher Daten und hochgeladener Unterlagen; die Vergabeunterlagen bleiben maßgeblich; die Entscheidung liegt beim Nutzer |

Vor Produktivsetzung anwaltlich prüfen lassen — insbesondere die Nähe zur Rechtsberatung bei
Eignungs- und Fristaussagen.

---

## 8. Qualitätsmessung

Das wirtschaftliche Risiko ist größer als das juristische: Wer Empfehlungen folgt und nie gewinnt,
kündigt. Deshalb ist die Messung Pflicht, nicht Kür.

| Fall | Bedeutung |
|---|---|
| „Bewerben" → gewonnen | Empfehlung bestätigt |
| „Bewerben" → verloren | neutral (Preis entscheidet oft) — nur in Serie ein Signal |
| „Nicht bewerben" → Nutzer bewirbt sich trotzdem und gewinnt | **Empfehlung war falsch** — höchste Priorität in der Auswertung |
| „Prüfen" → Nutzer verwirft mit Grund | Grund fließt in die Gewichtung (#11 §4.1) |

Grundlage sind die Ergebnisdaten aus #11. Ohne sie ist die Empfehlungsqualität nicht messbar — das
ist ein weiteres Argument für die Bootstrapping-Reihenfolge dort.

**Auswertung monatlich**, Trefferquote je Empfehlungstyp. Bei systematischen Abweichungen werden die
Bedingungen aus §3 angepasst, nicht die Darstellung.

---

## 9. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Kein Gesamtscore; zwei Kaskaden A1–A6 (Einordnung) und B0–B9 (Empfehlung), Reihenfolge bindend |
| 1b | Zehn Eingangsgrößen E1–E10 wie in §3.1; keine anderen Größen fließen ein |
| 1c | Schwellen konfigurierbar, Ausgangswerte wie §3.2 |
| 1d | Anforderungen binär oder schwellenbasiert ausgewertet; „knapp verfehlt" ab 85 % führt zu Prüfen, nicht zu Ablehnung |
| 1e | E4 als Verhältnis Aufwand ÷ Auftragswert; bei unbekanntem Wert Rückfall auf absolute Stufe mit benannter Unsicherheit |
| 1f | Zuschlagsgewichtung und Entfernung als Hinweise ohne Regelwirkung |
| 2 | Zwei Ebenen: Einordnung (Free) und Handlungsempfehlung (Pro / 3× Free) |
| 3 | Sperre als fehlende Grundlage formuliert, nie als Bezahlschranke |
| 4 | Vier Empfehlungen (inkl. Verteidigen), fünf Zusätze |
| 4b | B0 greift vor allen anderen Regeln, wenn das eigene Profil Vorgänger des Verfahrens ist |
| 4c | Bieterdichte nur ab Fallzahl 8, immer mit Fallzahl, immer rückwärtsgewandt formuliert |
| 4d | Bei Mehr-Los-Vergaben Zusatz „einzelnes Los" statt harter Ablehnung wegen Aufwand |
| 4e | „Noch zu klären" erscheint nie ohne konkrete offene Frage und Handlungsoption |
| 4f | Höchstens zwei Zusätze in der Liste, Rangfolge nach §3.4 |
| 4g | Eine Spalte, zwei Inhalte je Stufe — kein Blur in der Liste, keine leeren Zellen |
| 4h | Empfehlung auch im Zustand B (Korpus-Unterlagen) vollständig; Dokumentstand ausgewiesen |
| 4i | Veraltete Korpus-Fassung schwächt die Empfehlung ab (§2.3) |
| 4j | Checkliste unterhalb der Bestätigungsschwelle (#23 §12.2) trägt keine Empfehlung für Dritte |
| 4k | Abweichung zwischen Einordnung und Empfehlung wird einmalig erklärt (§2.5) |
| 4l | Unter 60 % Profilabdeckung wird Kaskade B ausgesetzt; Liste zeigt Einordnung (§3.9) |
| 4m | Profil-Band als Band über der Liste, max. 5 Fragen aus den angezeigten Leads, direkt beantwortbar, mit beziffertem Nutzen (§4.3) |
| 4n | Empfehlung wird täglich neu berechnet; bei beobachteten Leads Warnung vor dem Kippen (§3.10) |
| 5 | Hartes „Nicht bewerben" nur bei belegtem Zitat **und** ausdrücklicher Profilangabe |
| 6 | Empfehlung erscheint nie ohne Begründungskette |
| 7 | Nächster Schritt als konkrete Handlung benannt |
| 8 | Widerspruch möglich, wird gespeichert, nicht kommentiert |
| 9 | **Kein enger Standardfilter**; bei aktivem Filter Anzahl der ausgeblendeten Leads sichtbar |
| 10 | Empfehlungsqualität wird monatlich gegen Ergebnisdaten gemessen |
| 11 | Profil-Schnittstelle nach §6 erfüllt |

---

## 10. Offene Punkte

| # | Punkt | Zu klären |
|---|---|---|
| 2 | Median-Bearbeitungszeit je Segment (E5) | aus `lead_duration` je CPV-Segment ableiten; Ausgangswert bis dahin: 10 Tage |
| 2b | **Aufwand-Wert-Schwellen (§3.2b) sind Startwerte** | aus `lead_export` kalibrieren: Verteilung der Auftragswerte je Aufwandsstufe |
| 2c | 85-%-Grenze für „knapp verfehlt" | an realen Eignungsleihe-Fällen prüfen |
| 3 | Anwaltliche Prüfung der Empfehlungsformulierungen | vor Produktivsetzung |
| 4 | Verhältnis zu #19 | #19 geht hierin auf und entfällt als eigenes Ticket |
| 5 | Los-Ebene | E10 wirkt bisher nur als Aufwandsventil; bei Mehr-Los-Vergaben wären Empfehlungen je Los denkbar — eigener Prüfpunkt |
| 6 | Partner-Zusatz ohne Netzwerkabgleich | „mit Partner" sollte prüfen, ob im Netzwerk überhaupt ein passender Partner existiert |
| 7 | Rahmenvertrag setzt die Verhältnisprüfung aus (§3.2b) | öffnet ein Schlupfloch bei hohem Aufwand und kleinem Nennwert — Regel schärfen |
