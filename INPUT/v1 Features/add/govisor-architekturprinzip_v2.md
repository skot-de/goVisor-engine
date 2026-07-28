# goVisor — Architekturprinzip: Ein Kern, zwei Profile

**Ebene:** Intern. Bindende Klammer für alle Bau-Tickets.
**Zweck:** Sicherstellen, dass der Datenkern rollen-agnostisch bleibt, damit die zweite Marktseite (Vergabestelle) später ein Frontend-Projekt ist und kein Datenbank-Umbau.
**Stand:** 2026-07-27

---

## 1. Das Prinzip in einem Satz

> **goVisor ist ein Datenkern mit rollen-agnostischer Logik, auf den zwei Profiltypen zwei getrennte Sichten haben — Anbieter und Vergabestelle sehen denselben Bestand aus entgegengesetzten Richtungen.**

Nicht zwei Plattformen. Nicht eine Plattform mit zwei Modi im selben Menü. Ein Fundament, zwei Eingänge.

---

## 2. Die drei Schichten und ihr Teilungsgrad

Die zentrale Unterscheidung, die das ganze Prinzip trägt: Was ist geteilt, was ist getrennt?

| Schicht | Teilung | Begründung |
|---|---|---|
| **Datenschicht** | vollständig geteilt | Derselbe TED/national-Bestand, dieselben Entities, dieselbe Wettbewerbslandschaft, dieselben Ergebnisdaten. Zwei Datenbanken zu bauen würde den Kernvorteil zerstören — der Wert entsteht ja daraus, dass goVisor beide Seiten kennt. |
| **Logikschicht** | ~80 % geteilt | „Wie angreifbar ist dieser Amtsinhaber", „wie viele Anbieter in diesem CPV/Region", „was ist marktüblich" — identische Berechnungen. Der Anbieter fragt sie zum Angreifen, die Vergabestelle zum Planen. |
| **Präsentationsschicht** | vollständig getrennt | Andere Startseite, anderes Menü, andere Sprache, andere Defaults. Ein Bid Manager und ein Vergabesachbearbeiter wollen nicht dieselbe Oberfläche. |

Die Kurzform: **Daten und Logik geteilt, Oberfläche getrennt.**

---

## 3. Die zwei Profiltypen

Die Rolle wird **einmal bei der Registrierung** gewählt und bestimmt die gesamte Sicht.

```
Registrierung
   │
   ├─ "Ich suche und gewinne Aufträge"   → Anbieter-Profil
   │                                        → Lead Explorer, Strategie, Netzwerk, Treffergüte
   │
   └─ "Ich schreibe Aufträge aus"        → Vergabestellen-Profil
                                            → Ausschreibungscheck, Marktübersicht
```

Nach der Wahl sieht kein Profil die Menüs des anderen. Getrennte Navigation, getrennte Onboarding-Flows, getrennte Sprache. Der Anbieter weiß nicht (außer als Randnotiz), dass es eine Vergabestellen-Sicht gibt, und umgekehrt.

**Realistische Gewichtung:** goVisor ist primär eine Anbieter-Plattform. Das Vergabestellen-Profil ist eine eigene, klar getrennte Tür daneben — nicht der halbe Startbildschirm, sondern ein bewusst schmalerer zweiter Eingang, der erst in Phase 3–4 ausgebaut wird.

Das ist kein Widerspruch zu der Aussage im Kerndokument, die Vergabestellen-Seite sei „der stärkste Graben": Beides gilt, nur auf verschiedenen Zeitachsen. **Im Frontend heute** ist sie ein schmaler Eingang (der manuelle Ausschreibungscheck, wenig Oberfläche). **Strategisch langfristig** ist sie der stärkste Graben (das zweiseitige Netzwerk, das keine einseitige Plattform einholt). Klein im Aufwand jetzt, groß in der Wirkung später — deshalb schmal gebaut, aber im Datenkern von Anfang an ermöglicht.

---

## 4. Die rollen-agnostische Logik — die eigentliche Bau-Regel

Das ist der Teil, der die Bau-Tickets bindet. Die Logikschicht darf **nicht anbieter-fest verdrahtet** werden.

**Falsch (anbieter-fest):**
> „Berechne die Lead-Relevanz für den eingeloggten Anbieter."

**Richtig (rollen-agnostisch):**
> „Berechne die Relevanz zwischen Entität X und Ausschreibung Y."

Im zweiten Fall ist es dieselbe Funktion, egal wer fragt:
- Der **Anbieter** ruft sie für sich selbst gegen offene Ausschreibungen auf → „passt dieser Lead zu mir?"
- Die **Vergabestelle** ruft sie für ihre potenziellen Bieter gegen ihren Entwurf auf → „welche Anbieter passen zu meiner geplanten Ausschreibung?"

Eine Berechnung, zwei Aufrufer. Wenn die Tickets das heute so bauen, ist die zweite Sicht später ein Frontend-Projekt. Wenn nicht, ist sie ein Datenbank-Umbau.

### Konkrete Konsequenzen für die Tickets

| Baustein | Anbieter-fest (vermeiden) | Rollen-agnostisch (bauen) |
|---|---|---|
| Relevanz | `relevance(lead, current_user)` | `relevance(entity, tender)` |
| Wettbewerbsmenge | „meine Konkurrenten" | „Anbieter in CPV+Region" |
| Marktüblichkeit | (nur Anbieter-Sicht) | „übliche Losstruktur/Volumen/Kriterien für Vergabetyp Z" |
| Entity-Bezug | `user.company_id` fest | Parameter, den beide Rollen füllen |

Die Berechnungen sind ohnehin fast alle schon entity-bezogen (Ticket #14 Entity-Härtung liefert die Basis). Es geht nur darum, sie nicht an `current_user = Anbieter` zu koppeln, sondern die Entität als Parameter zu führen.

---

## 5. Der eine Berührungspunkt

Die zwei Profile sind auf der Oberfläche getrennt — mit **einer** bewusst gestalteten Ausnahme: dem PRE-Berührungspunkt aus dem Zyklus-Konzept.

- Die Vergabestelle sieht als **Marktbild**: „Für diesen geplanten Auftrag kommen 12 passende Anbieter in eurer Region in Frage." — aggregiert, anonym, keine Kontaktliste.
- Der Anbieter sieht als **Frühwarnung**: „In deinem Feld bahnt sich etwas an." — aus öffentlichen Vorlauf-Signalen, keine Einladung.

Beide sehen **Potenziale**, goVisor vermittelt **keinen Kontakt**. Das ist kein geteiltes Menü, sondern eine an genau einer Stelle geschlagene Brücke — der zweiseitige Netzwerkgraph. Kommt spät (Phase 3–4), aber der Datenkern muss ihn ermöglichen, ohne dass die Profile sich sonst vermischen.

**Regel:** Der Berührungspunkt ist immer aggregiert und anonym. Nie schlägt goVisor einen direkten, individualisierten Kontakt zwischen einer benannten Vergabestelle und einem benannten Anbieter vor. Das hält ihn außerhalb der Neutralitäts- und Wettbewerbsprobleme.

---

## 6. Datenmodell-Konsequenz

| Feld/Konzept | Anforderung |
|---|---|
| `profile_type` | enum `bidder` / `contracting_authority`, bei Registrierung gesetzt |
| Relevanz-/Analyse-Funktionen | nehmen `entity_id` als Parameter, nicht implizit den eingeloggten Anbieter |
| Sicht-Steuerung | `profile_type` bestimmt Navigation, Defaults, Sprache — nicht den Datenzugriff auf Berechnungsebene |
| Berührungspunkt-Aggregate | eigener, anonymisierter Aggregat-Typ, ab Mindestzahl |

---

## 7. Was das für die aktuelle Bauphase heißt

**Heute ist das kein Bau-Auftrag für die Vergabestellen-Sicht** — die ist Phase 3–4. Es ist eine **Disziplin** für die Tickets, die jetzt entstehen:

1. Analyse-/Relevanzfunktionen entity-parametrisiert bauen, nicht user-fest.
2. `profile_type` von Anfang an im Nutzermodell vorsehen, auch wenn nur `bidder` genutzt wird.
3. Keine Annahme „der Nutzer ist immer ein Anbieter" in der Logikschicht verankern.

Kosten heute: minimal (eine Parameter-Disziplin). Ersparnis später: der Unterschied zwischen einem Frontend-Projekt und einem Datenbank-Umbau.

### 7.1 Umsetzungsstand

| Punkt | Stand |
|---|---|
| `profile_type` im Schema | **erledigt** — Migration `0004_profile_type.sql`, Spalte mit `default 'bidder'` und Check-Constraint `in ('bidder','contracting_authority')`. Nutzt aktuell nur `bidder`, Haken gesetzt ohne Sicht-Änderung. |
| Rollen-agnostische Logik | **teilweise** — `matchLead(lead, profile, wert)` nimmt schon ein Profil-Objekt statt des eingeloggten Users. Aber das Profil ist noch bieter-förmig (`cpvFields` = „meine Stärken"), nicht der vollsymmetrische Entity-Deskriptor. Für Phase 1 ausreichend; die volle Symmetrie kommt mit der Vergabestellen-Sicht. |
| Rahmenvertrag-Flag | **erledigt** — `contract_kind='framework'` aus dem Gold-Export im Web-Export verdrahtet (`istRahmen`, 7,5 % gesamt / 14 % IT). Zeigt den Volumen-Hinweis „Nennwert ist Ober-/Schätzgrenze, real oft ein Vielfaches" ohne erfundenen Multiplikator — Hausstil-konform. |

Die erste „billig heute, teuer später"-Sache ist damit gezogen, bevor Nutzer im System sind. Die verbleibende Arbeit an der vollen Rollen-Symmetrie ist bewusst nach Phase 1 verschoben und kein Blocker.

---

## 8. Verhältnis zu den anderen Dokumenten

| Dokument | Rolle |
|---|---|
| Kerndokument (`govisor-kern.md`) | *Warum* — die Idee, zwei Marktseiten |
| Zyklus-Konzept (`govisor-gesamtkonzept-zyklus.md`) | *Entlang welcher Achse* — die drei Phasen |
| **Dieses Dokument** | *Wie technisch geklammert* — ein Kern, zwei Profile, rollen-agnostisch |

Die ersten beiden erklären die Strategie. Dieses stellt sicher, dass die Bau-Tickets sie nicht versehentlich verbauen.
