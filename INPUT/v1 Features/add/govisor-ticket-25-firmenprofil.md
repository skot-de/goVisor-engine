# Feature #25: Firmenprofil

**Produkt:** goVisor
**Version:** 1.0
**Status:** Bau-Spezifikation
**Erstellt:** 2026-07-30
**Abhängigkeiten:** #3 (Lead-Detail/Direktvergleich), #10 (Strategie), #11 (Ergebnisdaten), #14 (Entity-Härtung), #17 (Cockpit), #24 (Zuschlagsphase)

---

## 1. Umfang

Eine Detailseite je Unternehmen — das Gegenstück zum Lead-Detail, nur für eine Firma statt für eine
Ausschreibung. Sie beantwortet: **Wer ist dieses Unternehmen, wo sitzt es fest, was läuft dort aus,
und wie stehen wir zu ihm.**

**Kein Navigationspunkt.** Erreichbar aus:
- der Wettbewerbstabelle (Strategie, #10)
- dem Amtsinhaber im Lead-Detail (#3)
- dem Gewinner eines Zuschlags (#24)
- der Anbieterliste der Vergabestellen-Sicht (Vergabeblick)
- der Suche

**Abgrenzung zu bestehenden Ansichten:**

| Ansicht | Frage |
|---|---|
| Strategie → Wettbewerb | Wer holt in meinem Feld die Aufträge? (Rangliste) |
| Lead-Detail → Direktvergleich | Wie stehe ich gegen diesen einen bei dieser einen Ausschreibung? |
| **Firmenprofil** | **Wer ist diese Firma, über alles hinweg?** |

---

## 2. Rollen-Agnostik

Das Profil ist **dieselbe Ansicht für jede Entität** — Wettbewerber, potenzieller Partner, Amtsinhaber,
Zuschlagsgewinner. Es unterscheidet sich nur in der Einordnung (§4.2), nicht in der Struktur.

Konsequenz aus dem Architekturprinzip: Die Berechnungen nehmen `entity_id` als Parameter. Dasselbe
Profil trägt später die Vergabestellen-Sicht („welche Anbieter kommen für mich in Frage") ohne Umbau.

---

## 3. Datengrundlage

| Bereich | Quelle |
|---|---|
| Identität, Konzernstruktur | `entity_identity`, `dim_company_group` |
| Zuschläge, Volumen, Ø-Wert | `contractor_stats`, `agg_supplier_profile` |
| Vergabestellen-Bindung | `agg_buyer_supplier`, `incumbent_tenure` |
| Auslaufende Verträge | `lead_duration` |
| Verteidigungs-/Wechselquote | `head_to_head` (100.071 Nachfolgen, Marktretention 28,3 %) |
| Vorzeitige Neuausschreibung | `retender_signal` |
| Kopf-an-Kopf | öffentliche Zuschläge + `user_outcomes` (#11) |
| Unterauftragsvergabe | `SubcontractingTerm` (32,6 %) |
| Netzwerk-Status | Netzwerk-Feature |

---

## 4. Kopfbereich

### 4.1 Identität und Zuordnungsgüte

```
Spie Deutschland & Zentraleuropa GmbH
[Zuordnung gesichert] [Konzern · 4 Gesellschaften zusammengefasst]
[direkter Wettbewerb] [Schwerpunkt Elektro · NRW]
```

**Pflicht:** Die Zuordnungsgüte aus `entity_confidence` wird immer angezeigt.

| Zustand | Anzeige | Folge |
|---|---|---|
| `confirmed` | „Zuordnung gesichert" (grün) | volle Darstellung |
| `probable` | „Zuordnung wahrscheinlich" (neutral) | volle Darstellung + Hinweis |
| `none` / mehrdeutig | „Zuordnung unsicher" (amber) | Warnbanner §8, Korrekturmöglichkeit |

Bei zusammengefassten Konzerngesellschaften wird die Zahl der Gesellschaften genannt und ist
aufklappbar. Ohne diesen Hinweis wären die Zahlen irreführend.

### 4.2 Einordnung zum eigenen Profil

Aus der CPV-Überschneidung berechnet, gleiche Logik wie #24:

| Einordnung | Bedingung |
|---|---|
| direkter Wettbewerb | hohe Überschneidung |
| teilweise Überschneidung | mittlere |
| ergänzt euch | geringe Überschneidung, Gegenrichtung möglich |

### 4.3 Kennzahlenleiste

Fünf Werte, jeder mit Herkunftsangabe:

| Kennzahl | Zusatz |
|---|---|
| Zuschläge 36 Monate | „gemessen" |
| Volumen gesamt | „davon X % mit echtem Wert" |
| Ø Auftragswert | Median daneben (robuster) |
| **Verteidigungsquote** | Marktvergleich („Markt 28 %") — amber wenn deutlich darüber |
| Läuft aus ≤ 18 Monate | Anzahl + Volumen, grün (Chance) |

Fehlt eine Grundlage, steht „—" plus Grund („kein Wert veröffentlicht", „zu wenig Daten") —
niemals 0 oder eine geschätzte Zahl ohne Kennzeichnung.

---

## 5. Sektionen

### 5.1 Wo das Unternehmen festsitzt

Tabelle je Vergabestelle: Name, Leistung, Anzahl Aufträge, seit wann, **Bindungsstärke**.

Bindungsstärke aus `incumbent_tenure` in vier Stufen — sehr fest / fest / mittel / schwach.
Schwache Bindung ist grün markiert: das ist die Angriffsfläche.

### 5.2 Was dort ausläuft — die wichtigste Sektion

Tabelle der auslaufenden Verträge: Vertrag, Vergabestelle, Volumen, Enddatum, Aktion „Merken".

- Sortiert nach Enddatum aufsteigend
- Enddatum innerhalb 18 Monaten grün hervorgehoben
- Zweite Zeile je Eintrag: Bindungskontext („Bindung schwach — 1. Vertrag")
- „Merken" erzeugt einen Cockpit-Eintrag (#17) mit dem Auslauftermin

Das ist der operative Kern: Jeder auslaufende Vertrag eines Wettbewerbers ist eine Chance mit Datum.

### 5.3 Kopf an Kopf

Drei Zahlen: ihr gewonnen · das Unternehmen gewonnen · an Dritte.

**Pflichthinweis zur Datenlage:**

> 10 gemeinsame Verfahren — davon 5 aus öffentlichen Zuschlägen belegt, 5 aus euren eigenen Meldungen.
> Wo ihr nichts gemeldet habt, kennt goVisor eure Teilnahme nicht.

Öffentlich sichtbar sind nur die **Gewinne** des Unternehmens. Die eigene Teilnahme kennt goVisor nur
aus `user_outcomes`. Das macht die Sektion zum sichtbarsten Anreiz, das Cockpit zu pflegen.

**Kartellrechtliche Grenze (aus #11):** Es werden ausschließlich die **eigenen** Begegnungen gezeigt.
Niemals „welche anderen Unternehmen gegen X geboten haben" — auch nicht aggregiert, solange die
Mindestzahl aus #11 nicht erreicht ist.

### 5.4 Wo das Unternehmen stark ist

Zwei Balkengruppen: Leistungsfelder (CPV) und Regionen, jeweils Anteil an den Zuschlägen.
Darunter die Überschneidung mit dem eigenen Profil in einem Satz.

Ab weniger als 8 Aufträgen wird **keine Verteilung** gezeigt, sondern der Hinweis, dass die Basis
zu dünn ist.

### 5.5 Weitere Signale

| Signal | Quelle | Darstellung |
|---|---|---|
| Unterauftragsvergabe geregelt | `SubcontractingTerm` | „7 von 34" bzw. „keine Angabe" |
| vorzeitige Neuausschreibungen | `retender_signal` | Anzahl — Indiz für Probleme im Vertrag |
| Bietergemeinschaften | Zuschlagsdaten | Anzahl — Indiz für Kooperationsbereitschaft |
| Netzwerk | Netzwerk-Feature | beigetreten / nicht beigetreten |

Daneben ein abgeleiteter Einordnungssatz, **immer als Ableitung gekennzeichnet**.

---

## 6. Aktionen

| Aktion | Wirkung |
|---|---|
| Beobachten | Alerts bei neuen Zuschlägen und Vertragsausläufen dieses Unternehmens (Pro) |
| Merken (je Auslaufvertrag) | Cockpit-Eintrag mit Termin |
| Export | Profil als PDF (Pro) |
| Zuordnung korrigieren | bei unsicherer Entity-Zuordnung, siehe §8 |
| Über Netzwerk kontaktieren | nur bei beidseitiger Freigabe |

---

## 7. Gate

| Inhalt | Free | Pro |
|---|---|---|
| Kopfbereich, Kennzahlen, Felder/Regionen | ✓ | ✓ |
| Wo das Unternehmen festsitzt | ✓ | ✓ |
| **Was dort ausläuft** | ✗ | ✓ |
| **Kopf an Kopf** | ✗ | ✓ |
| Weitere Signale | ✗ | ✓ |
| Beobachten, Export | ✗ | ✓ |

Die Auslaufliste ist der wertvollste Teil und gehört hinter das Gate.

---

## 8. Ehrlichkeit bei dünner Datenlage — Pflicht

Bei `entity_confidence` = unsicher erscheint **vor** allen Zahlen ein Warnbanner:

> **Diese Firma ist nicht eindeutig zuzuordnen.** Im Vergaberegister gibt es drei ähnliche Namen an
> unterschiedlichen Orten. Die Zahlen unten beziehen sich auf die wahrscheinlichste Zuordnung und
> können Aufträge anderer Gesellschaften enthalten.
> [Zuordnung korrigieren]

Die Korrektur des Nutzers fließt in die Entity-Härtung (#14) zurück und verbessert den Graphen für alle.

**Schwellen für Sektionen:**

| Sektion | Mindestbasis | sonst |
|---|---|---|
| Feld-/Regionsverteilung | 8 Aufträge | „Aus N Aufträgen lässt sich kein belastbarer Schwerpunkt ableiten" |
| Verteidigungsquote | 3 auswertbare Nachfolgen | „—", „keine Nachfolge auswertbar" |
| Bindungsstärke je Stelle | 2 Aufträge | „zu wenig Daten" |
| Kopf an Kopf | ≥ 1 Begegnung | Leerzustand mit Verweis aufs Cockpit |

---

## 9. Grenzen

| Verboten | Grund |
|---|---|
| Personenbezogene Daten (Geschäftsführung, Ansprechpartner, Mitarbeiter) | konsistent mit #11 §5.2 |
| Angebotspreise | Kartellrecht |
| Daten anderer Nutzer, nicht aggregiert | #11 |
| Bonität, Finanzkennzahlen, Presseauswertung | nicht Teil des Vergabedatenkerns; wäre Zukauf |
| Wertende Aussagen über die Firma („unzuverlässig") | Fakten statt Urteil |

**Pflichthinweis am Seitenende:**

> Alle Angaben stammen aus öffentlichen Vergabebekanntmachungen und euren eigenen Meldungen.
> goVisor zeigt keine Daten anderer Nutzer, keine Preise und keine Personen.

---

## 10. Datenmodell

Keine neue Rohdatentabelle. Benötigt:

| Element | Art |
|---|---|
| `profile_watchlist` | neu, klein: `profile_id`, `entity_id`, `created_at` — für „Beobachten" |
| `overlap_score(profile, entity)` | berechnet, geteilt mit #24 |
| Aggregat-View je Entität | liest `contractor_stats`, `agg_buyer_supplier`, `incumbent_tenure`, `lead_duration`, `head_to_head` |

Alle Berechnungen entity-parametrisiert, nicht an den eingeloggten Nutzer gebunden.

---

## 11. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Erreichbar aus Wettbewerbstabelle, Lead-Detail, Zuschlag-Detail und Suche |
| 2 | Zuordnungsgüte immer sichtbar; Konzernzusammenfassung ausgewiesen |
| 3 | Einordnung zum eigenen Profil aus CPV-Überschneidung |
| 4 | Fünf Kennzahlen mit Herkunft; „—" plus Grund statt Ersatzzahlen |
| 5 | Verteidigungsquote immer mit Marktvergleich |
| 6 | Bindungsstärke je Vergabestelle in vier Stufen, schwache grün |
| 7 | Auslaufliste nach Enddatum sortiert, ≤ 18 Monate hervorgehoben, „Merken" erzeugt Cockpit-Eintrag |
| 8 | Kopf an Kopf mit Pflichthinweis zur Datenherkunft |
| 9 | Kopf an Kopf zeigt ausschließlich eigene Begegnungen |
| 10 | Keine Verteilung unter 8 Aufträgen |
| 11 | Warnbanner + Korrekturmöglichkeit bei unsicherer Zuordnung |
| 12 | Korrektur fließt in die Entity-Härtung zurück |
| 13 | Auslaufliste, Kopf an Kopf und Signale hinter dem Pro-Gate |
| 14 | Keine Personen, keine Preise, keine Wertungen |
| 15 | Pflichthinweis zur Datenherkunft am Seitenende |
| 16 | Alle Berechnungen entity-parametrisiert |

---

## 12. Offene Punkte

| # | Punkt | Zu klären |
|---|---|---|
| 1 | Schwellen (8 Aufträge, 3 Nachfolgen) | an realen Verteilungen prüfen |
| 2 | Darstellung bei Konzernstrukturen — zusammengefasst oder je Gesellschaft umschaltbar? | Nutzertest |
| 3 | „Beobachten"-Alerts: Frequenz und Bündelung | mit #9 abstimmen |
