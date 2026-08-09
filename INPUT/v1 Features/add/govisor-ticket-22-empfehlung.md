# Feature #17: Empfehlung — Handlungs-Urteil über den Scores

**Produkt:** goVisor
**Version:** V1
**Status:** Draft
**Erstellt:** 2026-07-28

> **Warum dieses Ticket?** Die Positionierung von goVisor ist „der einzige Dienst, der **abrät**" — und das
> Geschäftsmodell trägt genau diese Haltung: Wir verdienen bei Zuschlag, nicht bei Klick. Nur fehlt das
> Urteil bislang im Produkt. Relevanz, Chance und Aufwand stehen nebeneinander, aber die Software zieht
> daraus keine sichtbare Konsequenz. Die Empfehlung **ist** diese Konsequenz — **kein neues Modell, sondern
> eine dünne Ableitung** über bestehende Scores. Sie unterliegt demselben Prinzip wie alles andere:
> **lieber „kann ich nicht sagen" als ein falsches Urteil.** Eine Empfehlung, die „überspringen" rät, wo sie
> in Wahrheit nur nichts weiß, wäre falsche Präzision — diesmal auf der Urteils-Ebene.

---

## Reality-Check — welche Eingänge trägt das Urteil?

Die Empfehlung ist nur so ehrlich wie ihre Eingänge. Jeder wird nach Belastbarkeit eingeteilt.

| Ampel | Eingang | Stand |
|-------|---------|-------|
| 🟢 **tragfähig heute** | **Relevanz** (CPV 40 / Region 30 / Volumen 30, aus #1/#3) | existiert, deterministisch |
| 🟢 **tragfähig heute** | **Chance** = `leads.displaceability` (kalibriert, AUC 0.806, `score_driver`/`score_support`, #3) | existiert; **`NULL` bei 31,4 % Einmal-Werk** |
| 🟡 **partiell** | **Aufwand-Proxy** aus strukturierten Eckdaten (Bürgschaft, Bindefrist, Los-Zahl, strukturierte Nachweise) | nur soweit Felder belegt; Coverage mitführen |
| 🔴 **erst später** | **Aufwand aus Freitext** (Zertifikate/Referenzen aus Vergabeunterlagen, F02-Extraktion) | V2 — bis dahin **kein** Aufwand-basiertes „überspringen" |

> **Konsequenz:** Das MVP-Urteil steht auf **Relevanz + Chance** (beide 🟢). Aufwand fließt nur als **weicher
> Dämpfer** ein, soweit der Proxy 🟡 belegt ist — und erzeugt **nie allein** ein „überspringen", solange der
> Freitext-Aufwand (🔴) fehlt. Die Landing-Begründung „Aufwand zu hoch" ist erst mit F02 gedeckt; vorher
> nicht verwenden.

---

## User Story

> **Als** Anbieter **will ich** zu jeder Ausschreibung ein klares Urteil — antreten, überspringen oder
> offen — **mit dem Grund, der es kippt**, **um** in Sekunden zu entscheiden, wo ich meine Zeit investiere,
> ohne jeden Score selbst zu deuten.

---

## Die drei Zustände

| Zustand | Bedeutung | Bedingung (MVP, 🟢-Eingänge) |
|---------|-----------|------------------------------|
| 🟢 **antreten** | lohnt sich, hier Zeit zu investieren | Relevanz ≥ R_hi **und** Chance ≥ C_hi |
| ⚪ **überspringen** | begründet abraten | Relevanz < R_lo **oder** Chance ≤ C_lo (belegtes Negativ-Signal, z. B. Incumbent-Lock) |
| 🟡 **offen** | Daten reichen für kein Urteil | Chance = `NULL` (Einmal-Werk) · laufende Ausschreibung ohne Gebote · Grenzfall zwischen den Schwellen |

**„offen" ist ein vollwertiges Ergebnis, kein Fehler** — das Pendant zu „n/a" bei den Scores (#3). Es wird
gleichwertig gerendert, nicht als Fehlzustand versteckt und **nie eingefärbt, als würde es abraten**.

---

## Begründung (der kippende Faktor)

Jede Empfehlung trägt **genau einen** sichtbaren Grund — den Faktor, der das Urteil trägt. Kein Breakdown,
keine Prosa.

- **antreten** → stärkster positiver Treiber (z. B. „hohe Chance, offener Wettbewerb" aus `score_driver`)
- **überspringen** → das kippende Negativ (z. B. „Amtsinhaber sitzt fest" = niedrige `displaceability` mit
  `score_support`; „passt nur halb" = niedrige Relevanz)
- **offen** → **warum** offen (z. B. „keine Gebote bisher", „Erstvergabe, keine Vorgängerdaten")

Grund-Texte kommen aus einem **festen Katalog**, gemappt auf den auslösenden Faktor — nicht generativ.

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Jeder Lead trägt eine Empfehlung: `antreten` / `ueberspringen` / `offen` |
| 2 | Urteil abgeleitet aus **Relevanz + Chance**; Aufwand nur als 🟡-Dämpfer, **nie allein** ausschlaggebend (solange 🔴 F02 fehlt) |
| 3 | `displaceability = NULL` → **immer `offen`**, nie „überspringen" (kein Ersatzwert, wie #3) |
| 4 | Laufende Ausschreibung ohne Gebotsgrundlage → `offen` mit Grund „keine Gebote bisher" |
| 5 | Jede Empfehlung trägt **genau einen** Grund aus dem Katalog, gemappt auf den kippenden Faktor |
| 6 | `offen` wird gleichwertig gerendert (nicht als Fehler, nicht leer, nicht rot) |
| 7 | Empfehlung erscheint in **Lead-Liste** (Spalte) **und** Lead-Detail (#3) |
| 8 | Schwellen (R_hi/R_lo/C_hi/C_lo) zentral konfigurierbar, nicht hartkodiert |
| 9 | Rein beratend — kein Auto-Handeln, **keine** Kopplung an die Erfolgsprämie (die hängt am Analyse-Klick, #6) |
| 10 | Kein neues Score-Modell; ausschließlich Ableitung über `leads.relevanz` + `leads.displaceability` (+ Aufwand-Proxy) |

---

## UI/UX

- **Lead-Liste:** eigene Spalte „Empfehlung" rechts. `antreten` grün gefüllt, `überspringen` gedämpft/grau,
  `offen` neutral mit Punkt. Zustand + Grund-Kurztext untereinander.
- **Lead-Detail (#3):** Empfehlung als **Kopf-Verdikt** über den drei Scores, mit dem Grund darunter.
- **Provenance:** Der Grund benennt den kippenden Faktor. Fließt der 🟡-Aufwand-Proxy ein, Coverage-Hinweis.
- **Kein Override-Zwang:** Nutzer kann trotz „überspringen" öffnen und bewerten — die Empfehlung sperrt nichts.

---

## Datenmodell

Kein neues ML. Abgeleitetes Feld, täglich mit den Scores materialisiert (oder on-read berechnet):

```
lead_recommendation
  lead_id       VARCHAR    -- like leads.lead_id (VARCHAR, not uuid)
  verdict       ENUM       -- 'antreten' | 'ueberspringen' | 'offen'
  reason_code   VARCHAR    -- catalog key
  driver        VARCHAR    -- triggering factor (from score_driver / relevanz)
  aufwand_cov   NUMERIC    -- coverage of aufwand proxy, nullable
  computed_at   TIMESTAMP
```

Ableitung als **reine Funktion** über bestehende Felder — reproduzierbar, testbar, ohne Trainingslauf.

---

## Out of Scope

Aufwand aus Freitext / Zertifikats-Extraktion (F02) → **V2**. Warum-nicht-Erklärung als Prosa/LLM → V2.
Persönliche Gewichtung der Schwellen je Nutzer → später. Empfehlung als Prämien-Trigger → **nein** (bleibt
am Analyse-Klick, #6).

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| `leads.relevanz` (#1) | ✅ existiert |
| `leads.displaceability` + `score_driver`/`score_support` (#3) | ✅ existiert (NULL-Fälle beachten) |
| Aufwand-Proxy aus strukturierten Eckdaten | ⬜ klein, jetzt baubar (🟡) |
| Grund-Katalog (`reason_code` → Text) | ⬜ neu, klein |
| F02-Anforderungs-Extraktion (für 🔴-Aufwand) | ⬜ V2 |

---

## Testfälle

| # | Fall | Erwartung |
|---|------|-----------|
| 1 | Relevanz hoch + Chance hoch | `antreten`, Grund = positiver Treiber |
| 2 | Chance = NULL (Einmal-Werk) | **`offen`**, nie überspringen |
| 3 | Relevanz hoch + Chance sehr niedrig (Incumbent-Lock) | `überspringen`, Grund „Amtsinhaber sitzt fest" |
| 4 | Relevanz mittel, alles im Graubereich | `offen` (Grenzfall) |
| 5 | Laufende Ausschreibung, keine Gebote | `offen`, Grund „keine Gebote bisher" |
| 6 | „Aufwand zu hoch" als einziger Grund, F02 inaktiv | **darf nicht** als `überspringen` erscheinen |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | Schwellen R_hi / R_lo | an Verteilung kalibrieren; Start 70 / 40 |
| 2 | Schwellen C_hi / C_lo | auf `displaceability`; Start 0,6 / 0,2 |
| 3 | Grenzfall → `offen` oder weiches `antreten`? | **`offen`** (ehrlicher) |
| 4 | Aufwand-Proxy: welche Eckdaten-Felder zählen? | Bürgschaft, Bindefrist, Los-Zahl, strukturierte Nachweise |
| 5 | Empfehlung on-read oder materialisiert? | materialisiert mit den Scores (täglich) |
