# Feature #24: Zuschlagsphase — Gewinner als Einkäufer

**Produkt:** goVisor
**Version:** 1.0
**Status:** Bau-Spezifikation
**Erstellt:** 2026-07-30
**Abhängigkeiten:** #1 (Lead Explorer), #9 (Alerts), #14 (Entity-Härtung), #17 (Cockpit), #25 (Firmenprofil), Netzwerk

---

## 1. Umfang

Ein erteilter Zuschlag macht den Gewinner zum Einkäufer: Er braucht Nachunternehmer, Fachplanung,
Material, Lizenzen. Das Zeitfenster dafür liegt in den Wochen nach dem Zuschlag.

goVisor kennt den Auslöser punktgenau — Gewinner, Volumen, CPV, Datum stehen in TED/DÖE.

**Kein eigener Navigationsbereich.** Der Zuschlag ist eine **Phase** im bestehenden Lead-Bestand,
neben „Ausschreibung offen" und „Vertrag läuft aus". Gleiche Liste, gleiche Detailstruktur, andere
Handlung: anrufen statt bieten.

---

## 2. Datengrundlage

| Element | Quelle | Abdeckung |
|---|---|---|
| Gewinner, Datum, CPV, Vergabestelle | Zuschlagsbekanntmachung | ~96 % der Vergaben mit publiziertem Gewinner |
| Auftragswert | `value_band_effektiv` | ~65 % echter Wert |
| Laufzeit | `lead_duration` | vorhanden |
| **Unterauftragsvergabe geregelt** | `SubcontractingTerm.TermCode` | **32,6 %** |
| Firmenkontext des Gewinners | `contractor_stats`, `agg_supplier_profile` | vorhanden |
| Netzwerk-Freigabe | Netzwerk-Feature | vorhanden |

---

## 3. Darstellung in der Akquise

### 3.1 Phasenfilter

Die Phasenleiste erhält einen dritten Zustand:

```
● Ausschreibung offen  48   ● Zuschlag erteilt  6   ● Vertrag läuft aus  312
```

Zuschläge sind **standardmäßig eingeschaltet**, aber abschaltbar. Eigene Farbgebung (blau), damit sie
sich in der Liste von offenen Ausschreibungen unterscheiden.

### 3.2 Listenzeile

Gleiche Spalten wie bei Ausschreibungen, andere Belegung:

| Spalte | Bei Ausschreibung | Bei Zuschlag |
|---|---|---|
| Phase | „Ausschreibung offen" | „Zuschlag erteilt" (blau) |
| Status | „noch 12 Tage" | „vor 2 Tagen" |
| Empfehlung | „Hohe Passung" | „Ansprechen" / „Prüfen" |
| Empfehlung-Zeile 2 | „Amtsinhaber angreifbar" | „Unteraufträge geregelt · im Netzwerk" |
| Titel | Ausschreibungstitel | Auftragstitel |
| Untertitel | Vergabestelle | **Gewinner · Vergabestelle** |
| Volumen | geschätzt/gemessen | gemessen/geschätzt |

**Sortierung innerhalb der Phase:** nach Zuschlagsdatum absteigend. Das Zeitfenster bestimmt die
Reihenfolge, nicht das Volumen.

**Empfehlungslogik:**

| Empfehlung | Bedingung |
|---|---|
| Ansprechen | Unterauftragsvergabe geregelt **und** Feldüberschneidung gering (ergänzend) |
| Prüfen | keine Angabe zu Unteraufträgen **oder** Feldüberschneidung mittel |
| (kein Eintrag) | Feldüberschneidung hoch → direkter Wettbewerb, keine Empfehlung |

### 3.3 Standardfilter

| Filter | Vorbelegung | Begründung |
|---|---|---|
| Feld (CPV) | aus dem Profil | wie bei Ausschreibungen |
| Region | aus dem Profil | |
| **Mindestvolumen** | **500.000 €** | Unter dieser Größe wird selten weitervergeben; ohne Schwelle ist die Liste Rauschen |
| Zeitraum | letzte 30 Tage | danach ist das Fenster meist zu |
| nur mit Unterauftrags-Hinweis | aus | optionale Verschärfung |

---

## 4. Alert

Der Alert ist der eigentliche Auslöser — ein zeitkritisches Feature, das gesucht werden muss, wirkt nicht.

| Element | Regel |
|---|---|
| Trigger | neuer Zuschlag im Profilfeld + Region, über Mindestvolumen |
| Bündelung | täglich, nicht je Einzelzuschlag |
| Inhalt | Gewinner, Auftrag, Volumen, Unterauftrags-Signal |
| Gate | Pro (konsistent mit #9) |
| Bandanzeige | zusätzlich als Band über der Liste, solange ungelesen |

---

## 5. Zuschlag-Detail

Gleiche Detailstruktur wie ein Lead. Tabs: **Übersicht · Gewinner · Vergabestelle · Markt.**

### 5.1 Übersicht

Zwei Karten nebeneinander:

**Der Zuschlag** — Gewinner, Vergabestelle, Zuschlagsdatum, Auftragswert, Laufzeit, Unterauftrags-Angabe.

**Der Gewinner** — Zuschläge 36 Monate, Ø Auftragswert, davon mit Unterauftrags-Regelung, Region,
Leistungsfelder als Balken.

### 5.2 Passungshinweis

Abgeleiteter Textblock, **immer als Ableitung gekennzeichnet**:

> **Warum das zu euch passen könnte:** Goldbeck West gewinnt überwiegend Hochbau und führt Elektro
> selten selbst aus — bei 19 von 27 Aufträgen war Unterauftragsvergabe geregelt. Euer Schwerpunkt
> ergänzt, statt zu konkurrieren.
>
> *Abgeleitet aus der Zuschlagshistorie · kein Hinweis auf konkreten Bedarf*

### 5.3 Pflicht-Erläuterung

Bei jedem Zuschlag-Detail, nicht optional:

> „Unteraufträge geregelt" heißt: In den Vergabeunterlagen ist Unterauftragsvergabe vorgesehen.
> Ob und was tatsächlich vergeben wird, steht nirgends — das Feld liegt bei etwa einem Drittel der
> Verfahren vor.

### 5.4 Aktionen

| Aktion | Bedingung |
|---|---|
| Merken | immer → Cockpit (#17), eigener Eintragstyp |
| Firmenprofil | immer → #25 |
| Über Netzwerk kontaktieren | **nur bei beidseitiger Netzwerk-Freigabe** |

Ohne Freigabe **kein** Kontaktknopf und kein Ersatzangebot — goVisor täuscht keine Vermittlung vor,
die es nicht gibt.

---

## 6. Spiegelseite: eigener Zuschlag

Hat das eigene Profil gewonnen (Entity-Match, `entity_confidence` = confirmed), erscheint der Zuschlag
als eigener Block:

> **Ihr habt gewonnen** — Erneuerung Elektroverteilung Klinikum, 2,4 Mio €, Laufzeit bis 09/2027.
> Für Bereiche, die ihr nicht selbst abdeckt, gibt es im Netzwerk vier Anbieter in eurer Region.

Darunter Anbieter aus dem Netzwerk in **ergänzenden** Feldern (geringe CPV-Überschneidung), nur mit
Freigabe.

**Pflichthinweis:** „Euer Zuschlag ist ohnehin öffentlich — ob ihr Bedarf habt, sieht niemand."

Ohne diese Seite ist das Netzwerk einseitig; Gewinner hätten keinen Grund, ihre Freigabe zu setzen.

---

## 7. Strategie-Anbindung

Die Wettbewerbssektion (#10) erhält zwei zusätzliche Spalten:

| Spalte | Inhalt |
|---|---|
| mit Unterauftrag | „19 von 27" bzw. „keine Angabe" |
| Einordnung | „ergänzt euch" / „direkter Wettbewerb" — aus CPV-Überschneidung |

Abschlusshinweis der Sektion verweist auf die Akquise:

> Frische Zuschläge dieser Unternehmen erscheinen in der Akquise unter „Zuschlag erteilt".

Damit führt der analytische Weg zur Handlung, ohne dass ein dritter Ort gelernt werden muss.

---

## 8. Was das System nicht behaupten darf

| Verboten | Erlaubt |
|---|---|
| „X sucht Nachunternehmer" | „Unterauftragsvergabe in den Unterlagen geregelt" |
| „keine Unteraufträge" (bei fehlendem Feld) | „keine Angabe zu Unteraufträgen" |
| „X hat Bedarf an Elektroleistungen" | „X führt Elektro selten selbst aus (8 % der Aufträge)" |
| Kontaktdaten ohne Freigabe | öffentliche Angaben aus der Bekanntmachung |

---

## 9. Branchenabhängigkeit

Die Unterauftragskette ist im Bau der Normalfall, in der IT die Ausnahme. Umsetzung:

- Die Phase ist überall verfügbar.
- Die **Empfehlung** („Ansprechen") wird nur vergeben, wo das Unterauftrags-Feld belegt ist oder die
  Historie des Gewinners es stützt.
- Kein branchenübergreifendes Versprechen in Onboarding oder Marketing.

---

## 10. Datenmodell

Keine neue Tabelle. Erweiterungen:

| Feld | Ort | Inhalt |
|---|---|---|
| `phase` | Lead-Export | Wert `award` ergänzt `open` / `expiring` |
| `award_date` | Lead-Export | Zuschlagsdatum |
| `winner_entity_id` | Lead-Export | FK auf `entity_identity` |
| `subcontracting_flag` | Lead-Export | `geregelt` / `keine_angabe` |
| `overlap_score` | berechnet | CPV-Überschneidung Profil ↔ Gewinner, steuert die Empfehlung |
| Cockpit-Eintragstyp | #17 | dritter Typ neben Ausschreibung und eigenem Vertrag |

---

## 11. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Phase „Zuschlag erteilt" in der Phasenleiste, standardmäßig an, abschaltbar |
| 2 | Zuschläge erscheinen in derselben Liste wie Ausschreibungen, blau unterschieden |
| 3 | Sortierung innerhalb der Phase nach Zuschlagsdatum absteigend |
| 4 | Empfehlungslogik nach §3.2; keine Empfehlung bei hoher Feldüberschneidung |
| 5 | Mindestvolumen 500.000 € als Vorbelegung |
| 6 | Täglich gebündelter Alert (Pro) + Band über der Liste |
| 7 | Detail mit Zuschlag- und Gewinnerkarte |
| 8 | Passungshinweis immer als Ableitung gekennzeichnet |
| 9 | Pflicht-Erläuterung zum Unterauftrags-Feld in jedem Detail |
| 10 | „keine Angabe" statt „keine Unteraufträge" bei fehlendem Feld |
| 11 | Kontaktknopf nur bei beidseitiger Netzwerk-Freigabe |
| 12 | Spiegelseite bei eigenem Zuschlag inkl. Pflichthinweis |
| 13 | Merken erzeugt Cockpit-Eintrag vom Typ Zuschlag |
| 14 | Strategie-Wettbewerbstabelle um zwei Spalten erweitert |

---

## 12. Offene Punkte

| # | Punkt | Zu klären |
|---|---|---|
| 1 | Schwelle für `overlap_score` (ergänzend / Wettbewerb) | an realen Profilen kalibrieren |
| 2 | Mindestvolumen je Branche | im Bau vermutlich höher als in Beratung |
| 3 | Alert-Frequenz | täglich vs. wöchentlich nach Nutzungsdaten |
