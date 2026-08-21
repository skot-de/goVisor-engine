# goVisor — Produkt-Vision & Scope

> ⚠ **STAND 2026-08-21: Die Erfolgsprämie ist gestrichen.** Alles unten zum Thema Success-Fee ist Entscheidungsgeschichte, kein geltendes Modell. Aus dem Produkt ist sie entfernt (Code + Texte), das Schema räumt `supabase/0012_erfolgspraemie_entfernen.sql`.

**Status:** Strategische Leitlinie (2026-07-20)
**Zweck:** Wo goVisor spielt, wo bewusst nicht, und warum — abgeleitet aus der
gemessenen Datenrealität, nicht aus Wunschdenken.

---

## 1. Die Wertschöpfungskette — und unsere Position

```
Lead finden → Ausschreibung vorbereiten → Einreichen → Auftrag verwalten
   Stufe 1          Stufe 2                 Stufe 3        Stufe 4
```

| Stufe | Position | Bewertung |
|---|---|---|
| **1 · Lead finden** | Datenmoat: TED + Intelligence (Nachfolge, Incumbent, Marktstruktur, Retender, Wechselchance) | ✅ **Kernterritorium** |
| **2 · Vorbereiten** | Nur das **vordere Ende** (Entscheidungs-Support + Prep-Tool), nicht volle Bid-Produktion | 🟡 **defensible Erweiterung** |
| **3 · Einreichen** | Regulierte, rechtsverbindliche Plattformen (eVergabe, DTVP, cosinex…) | 🔴 **fremdes Geschäft** |
| **4 · Verwalten** | Separater CLM-Markt, nutzt unseren Moat nicht | 🔴 **fremder Markt** |

**Leitentscheidung:** goVisor ist ein **Lead- + Ausschreibungsvorbereitungs-Tool** mit
Schwerpunkt Stufe 1. Die Plattformen (Stufe 3) verdrängen wir nicht — wir **arbeiten
ihnen zu** und übergeben sauber. Fokus statt Kette.

---

## 2. Warum nicht weiter — die gemessenen Wände

- **Dokumenten-Wand:** Die Leistungsbeschreibung/Vergabeunterlagen sind **nicht in TED**
  (nur Kurz-Zusammenfassung, Median 162 Zeichen; Link zu den Unterlagen nur bei 24,8 %).
  Sie liegen auf dutzenden Vergabeplattformen hinter Registrierung. Volle Bid-Produktion
  (Stufe 2) ist dadurch blockiert.
- **Wert ist ein Angebots-Ergebnis, keine Spec-Angabe:** Selbst mit allen Unterlagen
  bekämen wir den Auftragswert nicht — er entsteht aus (geheimen) Angeboten, wird nur
  beim Zuschlag zu ~65 % veröffentlicht. Die Wert-Schätzung deckelt bei ~42 % Band-Treffer
  (gemessen, kein Modell knackt es).
- **Plattformen sind unverdrängbar:** reguliert, rechtsverbindlich, etabliert.

---

## 3. Die defensible Erweiterung: Prep-Tool, das den Plattformen zuarbeitet

**Konzept:** Bieter lädt das Preisblatt (Excel/GAEB) bei uns hoch → wir helfen beim
Ausfüllen → Export → Weiterverarbeitung auf der Plattform. Wir ersetzen die Plattform
nicht, wir sind die Schicht davor.

**Was „Ausfüllen" realistisch heißt:**

| Teil | Machbarkeit | Wert |
|---|---|---|
| Wiederkehrender Formalkram (Firmendaten, Eignung, Referenzen, Zertifikate) | ✅ gut | hoch — Zeitfresser |
| Preisblatt strukturell | 🟡 stark bei **GAEB** (Bau, standardisiert), brüchig bei Freiform-Excel | mittel-hoch |
| Tatsächliche Preise | 🔴 gehören dem Bieter | wir assistieren, füllen nicht |

**Einstiegspunkte:** GAEB (Bau = großer, *standardisierter* Block) + der repetitive
Eignungsteil. Freiform-Excel semi-automatisch („wir strukturieren, du bestätigst").

**Unsere einzigartige Zutat:** Preis-**Positionierung** aus den öffentlichen
Zuschlagswerten — „vergleichbare Aufträge gingen bei €X weg, der Incumbent bei €Y".
Das ist erlaubt (veröffentlichte Daten) und verbindet Stufe 1 mit Stufe 2.

**Attributions-Synergie:** Wird das Angebot bei uns vorbereitet und exportiert, ist
**das** das saubere Attributions-Ereignis für die Erfolgsprämie — viel stärker als ein
Lead-Klick. Prep-Tool stärkt das Preismodell.

---

## 4. Der v3-Datenmoat (hinter Rechts-Gate)

Wenn Bieter ihre Preise bei uns eintragen, kennen wir ihre Preise → potenziell echter
Datenmoat (auch Verlierer-Gebote, die niemand sonst hat) → würde die 42 %-Wert-Decke
knacken. **Aber rechtlich radioaktiv:**

| Nutzung | Bewertung |
|---|---|
| **Eigene Preise des Bieters für ihn selbst** (Vorfüllen, Kalkulation, Historie) | ✅ **v3-Start** — single-tenant, kein Wettbewerbsbezug |
| Preise **über Bieter hinweg** aggregieren + Signale zurückspielen | 🔴 **§ 298 StGB** (Submissionsabsprachen, strafbar) / Kartellrecht-Informationsaustausch |

**Entscheidung:** v3 startet mit der **sicheren Variante** (nur eigene historische
Daten). Bieterübergreifende Aggregation ist eine **separate, rechtlich vorab geklärte**
Entscheidung — kein Feature, das „nebenbei mitläuft, weil die Daten da sind".
→ Vor diesem Pfad: Deep-Research + anwaltliche Prüfung.

---

## 5. Monetarisierung (Kurzfassung)

**Basis-Fee (~29–49 €/Mo Abo) + Success-Fee (Erfolgsprämie bei Zuschlag).**
V1-Strategie: niedrige Einstiegshürde (Marktanteil) + Prämie schlägt hohen Preis ohne
Prämie. Success-Fee = **Flat-per-Band** (7 Stufen), abgerechnet nur auf echtem Wert,
Rest über Kunden-Bestätigung + HITL. Details: [`docs/pricing-modell.md`].
Die Erfolgsprämie ist ein **Novum** im DE-Vergabemarkt (kein Wettbewerber macht es) —
Chance und Marktedukations-Risiko zugleich.

---

## 6. Roter Faden

> **Wir versprechen nur Präzision, die die Daten hergeben.** Echter Wert statt Schätzung
> fürs Billing, bestätigte Identität statt Fuzzy-Match, ehrliche Schätz-Flags im UI.
> Fokus auf Stufe 1 + Prep ist kein Manko — es ist ein verteidigbarer, ehrlicher Scope.

Siehe auch: [`pricing-modell.md`], [`mehrwert-roadmap.md`].
