# goVisor — Preismodell (Mechanik)

**Status:** In Arbeit — Mechanik steht, Beträge offen
**Letzte Messung:** 2026-07-20 (75.014 DE-Leads, 28.004 mit echtem Wert)

> Dieses Dokument beschreibt die **Mechanik** des Preismodells. Die konkreten
> Beträge/Prozente sind bewusst offen und als „aktueller Vorschlag" markiert —
> sie sind reine Konfiguration (`govisor/pricing.py`) und jederzeit kalibrierbar.

---

## 1. Grundprinzip: Basis-Fee + Success-Fee

Zwei Komponenten:

| Komponente | Was | Höhe |
|---|---|---|
| **Basis-Fee** | Monatliches Abo, deckt Zugang + Intelligence | ~49 €/Mo *(marktvalidiert, s.u.)* |
| **Success-Fee** | Erfolgsprämie, fällt **nur bei gewonnenem Auftrag** an | Pauschale je Wert-Band *(Vorschlag, s.u.)* |

Die Basis-Fee trägt das Geschäft; die Success-Fee ist der **Bonus** bei Erfolg.
Das entlastet die Prämie — sie muss nicht hoch sein, um zu tragen, und kann
konservativ bleiben (wichtig, weil sie ein Novum ist, s. §6).

---

## 2. Warum Flat-per-Band statt Prozent

**Kernproblem:** Nur **37 %** der Auftragswerte sind in TED echt veröffentlicht;
58 % müssen wir schätzen/imputieren. Ein Prozentsatz auf einen **geschätzten**
Wert ist die schwache Flanke — im Verkaufsgespräch und rechtlich.

**Entscheidung:** feste **Pauschale je Wert-Band**. Wir multiplizieren nie einen
unsicheren Wert. Der Kunde sieht „dein Auftrag liegt in Größenordnung X →
Pauschale Y". Robust, transparent, verteidigbar.

Zwei Belege stützen das (s. §6 Research):
- **Lehman-Prinzip:** Erfolgs-%-Sätze *müssen* mit der Auftragsgröße sinken —
  ein Flat-% wird bei sechs-/siebenstelligen TED-Werten absurd.
- **Einziger echter Vergabe-Präzedenzfall (US, FAR-konform): Pauschalen**
  (z. B. 10.000 USD je Zuschlag), nicht Prozente.

---

## 3. Die Gebühren-Basis: `value_band_effektiv`

Jeder Lead bekommt **immer** einen Wert (nie „unbekannt"), plus eine
Herkunfts-Markierung `band_source`:

| `band_source` | Bedeutung | Anteil |
|---|---|---|
| `echt` | in TED veröffentlicht | 37 % |
| `geschaetzt` | aus dem Auftrag ableitbar | 5 % |
| `imputiert` | CPV-Klassen-Median (≥10 Samples) | 52 % |
| `default` | Fallback (kein Wert, keine CPV-Basis) | 6 % |

Build: `gold.build_value_band_effektiv` → `data/gold/DE/value_band_effektiv.parquet`.
`band_source` ist der **Fairness-Regler**: bei `imputiert`/`default` rechnen wir
konservativer ab (×0,8, s. §5).

---

## 4. Die Staffel (gebaut — Beträge als V1-Default)

> **Status:** in Code umgesetzt (`gold._band_sql` + `pricing.SCHEDULE`, 90 Tests grün,
> FK sauber). Die Beträge sind der V1-Default und bleiben Business-kalibrierbar.

Stufengrenzen **datengetrieben** an den echten Perzentilen der Auftragswerte
(p20≈100k, p40≈234k, p60≈470k, p80≈1,21M, p95≈6,52M):

| Stufe | Grenze (Perzentil) | Pauschale *(Vorschlag)* | eff. % Median-Deal |
|---|---|---|---|
| `<100k` Lose | < p20 | 600 € | ~1,3 % |
| `100-250k` | p20–p40 | 1.200 € | ~0,65 % |
| `250-500k` | p40–p62 | 2.400 € | ~0,65 % |
| `500k-1,3M` | p62–p82 | 4.800 € | ~0,63 % |
| `1,3-5M` | p82–p94 | 9.600 € | ~0,44 % |
| `5-25M` echte Großdeals | p94–p99 | 15.000 € | 0,30 → 0,06 % |
| `>25M` Rahmen/Ceiling | > p99 | 25.000 € (Fix) | homöopathisch |

**Design-Regeln dahinter:**
- Stufen 1–5 **verdoppeln** sich sauber (600→1.200→…→9.600) → konstante 2×-Klippen.
- **Oberhalb 25M nur Fix**, weil der Wert dort ein Rahmen-Höchstwert ist
  (größter echter Wert in DE: 793 Mio. €) — er trägt keine Umsatz-Information mehr.
  Prinzip: *staffeln solange der Wert Information trägt, pauschalisieren sobald er
  zum Ceiling wird.*
- Umsatz kommt aus der **fetten Mitte** (100k–1,3M = 74 % aller Aufträge, echte
  Gewinner), nicht von den Walen.

**Effektivsatz-Korridor:** ~0,3–0,7 % im Kern. Das ist bewusst **~eine
Größenordnung unter** jedem Benchmark aus Nachbarbranchen (§6) — konservativ,
passend für ein Novum.

---

## 5. Unsicherheits-Rabatt

```
if band_source in ('imputiert', 'default'):
    pauschale *= 0.8
```

Fairness bei geschätzten Werten: wo wir den Wert nur geraten haben, rechnen wir
20 % günstiger ab. Reiner Regler, frei einstellbar.

Implementierung: `govisor/pricing.py` (`SCHEDULE` + `fee(band, source, value)`),
Tests in `tests/test_pricing.py`. Runner `python -m govisor.pricing` rechnet die
Verteilung an den echten Leads durch.

---

## 6. Marktvalidierung (Deep-Research 2026-07-20)

103 Agenten, 21 Quellen, 22 verifizierte Claims.

- **🟢 49 €/Mo ist punktgenau.** Deutsches Ausschreibungsblatt kostet exakt 49 €;
  Marktkorridor 19–300 € (Vergabepilot 60–125, Vergabe24 19–90, DTAD ~100).
  *Primärquellen.*
- **🔴 Die Success-Fee ist ein Novum.** Ausnahmslos alle deutschen
  Vergabe-Plattformen sind reines Abo, **null** Erfolgsgebühr. TenderAlerts (EU/TED)
  wirbt aktiv mit „no commissions, success fees". → Kein Präzedenzfall =
  Differenzierungs-Chance **und** Marktedukations-Risiko.
- **Kein direkter %-Benchmark für Vergabe.** Nachbarbranchen: B2B-Vertrieb
  5–15 % vom *Erstjahres*-ACV, Lead-Gen 10–20 %, M&A-Finder 3–7 % — alles kleinere
  Deals, meist interne Provision, nicht übertragbar.
- **🟢 Flat-Präzedenzfall:** US-Vergabeberatung nutzt 10.000 USD/Zuschlag (≈ 9.200 €
  ≈ unsere `1,3-5M`-Stufe). Bestätigt Flat-per-Band **und** die absoluten Beträge.
- **Rechts-Signal (unverifiziert, vor Launch prüfen):** BGH hält reine
  Erfolgsprovision für Auftragsvermittlung grundsätzlich für zulässig.

---

## 7. Auslöse-Mechanik & Attribution

Die Success-Fee braucht das Signal „unser Nutzer hat gewonnen":

- **96 % der Vergaben** haben einen publizierten, aufgelösten Gewinner →
  automatisch erkennbar (Gewinner-Matching auf die bestätigte User-Entity).
- **4 % Blind Spot** (Gewinner nicht publiziert) → über **Self-Report/Bestätigung**
  des Nutzers schließbar.
- **Attributionsproblem** (wahrscheinlich der Grund, warum der Markt auf
  Erfolgsprämien verzichtet): Kausalität „Lead über goVisor → Zuschlag" ist schwer
  zu beweisen. Deshalb ist die Nutzer-Bestätigung nicht nur Abrechnungs-Detail,
  sondern **Kern der Machbarkeit**. Mechanik zu klären vor Launch.

---

## 8. Offene Business-Entscheidungen

- Finale Pauschalen-Beträge (aktuell §4-Vorschlag)
- Rabatt-Faktor (aktuell ×0,8)
- Bezugsgröße der Prämie: geschätzter TED-Wert vs. tatsächlicher Zuschlagswert
- Attributions-/Abrechnungs-Mechanik + rechtliche Absicherung (BGH-Signal prüfen)
- Warum verzichtet der Markt auf Erfolgsprämien? (Novum-Risiko final bewerten)
