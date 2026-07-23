# Feature #2: Personal Fit — v2 (engine-verdrahtet)

**Produkt:** goVisor
**Version:** V1
**Status:** Draft (Neufassung, korrigiert gegen die reale Entity-Resolution)
**Erstellt:** 2026-07-18

> **Warum diese Fassung?** Die erste Fassung hatte das #1-Feedback gut eingearbeitet (CPV-
> Hierarchie, `value_real_2020`/`value_source`, Volumen-unbekannt=50, Verteidigung). Ihr
> Herzstück — das Gruppen-Profil mit Win-Kuratierung pro Entität — stand aber auf einer
> **idealisierten** Sicht der Unternehmensgruppen. Gemessen sind die Gruppen fragmentiert,
> teils dupliziert und konfidenz-gemischt. Diese Fassung macht diese Realität zur Vorgabe und
> löst den offenen Onboarding-Einstieg. Prinzipien wie in #1: **kein Datenverlust, markieren
> statt wegwerfen, messen statt annehmen.**

---

## Reality-Check (gemessen, DE-Gold, Stand 2026-07-18)

Verbindliche Vorgaben, keine Randnotiz.

| Signal | Messung | Konsequenz |
|--------|---------|------------|
| Gruppengröße | **76,4 % aller Gruppen = 1 Entität**; 2 E. 13,5 %; 6 E. nur **0,6 %** | Normalfall = **keine Gruppe**. Der Gruppen-Flow ist der Ausnahmefall, nicht der Default. |
| Gruppen-Sauberkeit (Bsp. CANCOM) | „CANCOM Public GmbH" erscheint **4×** als getrennte entity_ids; Konfidenz 0.40–1.00 gemischt; Zeilen wie „…KST 606400", „NL Leipzig" | Entitäten **vor Anzeige deduplizieren**, Konfidenz je Zeile zeigen. Die „6 sauberen Töchter" existieren nicht. |
| Hierarchie | `entity_group` ist **flach** (entity→group); `dim_company_group` = nur `group_id`+`label` | **Kein** Holding/root/relation_type ableitbar. Konzernstruktur ist nicht in den Daten. |
| Branche | `dim_cpv.branche` liegt auf CPV-**Division** (2-stellig) | Bestehende Taxonomie nutzen; kein paralleles 5-stelliges Mapping. |
| Volumen | 55,8 % `value_source='unbekannt'` (aus #1) | Deal-Größen-Vorschlag aus Wins ist nach oben verzerrt → Caveat. |
| Zertifikate | **ableitbar** aus den Eignungsabschnitten (`…SelectionCriteria.Description`, `…LEFTI.TECHNICAL_PROFESSIONAL_INFO`): ISO 27001 in **4.254** Notices, Präqualifikation 214k, Zertifi* 111k | Anforderung (cn) → Gewinner (can, `ref_publication_number` **58,4 %**) → Gewinner erfüllt sie. Konfidenzbehaftet, Freitext-Extraktion nötig. |

---

## Kontext

User sieht tausende Leads — nur ein Bruchteil passt. Personal Fit ist das **Profil**, aus dem
sich der Relevanz-Score 🎯 (Ticket #1) speist, plus die **Filter** im Explorer.

Das Profil: Stammdaten · Unternehmensgruppe (soweit vorhanden) · Kompetenzen (CPV/Branchen) ·
Regionen · Deal-Größen · Referenzen (Wins) · Zertifizierungen · Partner.

Bei **bekannten Firmen** wird vorbefüllt (aus TED-Wins). Bei **unbekannten Firmen** gibt es eine
Kurz-Version (Onboarding) und eine Lang-Version (später).

---

## User Story

> **Als** Anbieter
> **will ich** nur Leads sehen, die zu meinen Fähigkeiten, Regionen und Deal-Größen passen —
> mit ehrlicher Kennzeichnung, wie sicher das aus TED abgeleitete Profil ist,
> **um** keine Zeit mit irrelevanten Ausschreibungen zu verschwenden.

---

## Onboarding-Einstieg (der zuvor offene Punkt)

**Prinzip:** Der Matcher ist die **bestehende** Entity-Resolution, gegen eine User-Eingabe
gefahren — keine neue Auflösungslogik. Geschichtet, präzisestes Signal zuerst, immer bestätigt.

| Stufe | Signal | Mechanik (bestehend) | Präzision |
|-------|--------|----------------------|-----------|
| 1 | **E-Mail-Domain** der Login-Adresse | `domain_group_label(domain)` → Gruppenlabel; Freemail wird ausgeschlossen | hoch, automatisch, null Tipparbeit |
| 2 | **Getippter Firmenname** | `normalize_company` → `blocking_key` → Kandidaten aus `entities`, gerankt nach Namensähnlichkeit × Win-Prominenz | mittel, Auffang |
| 3 | **USt-IdNr** (optional) | exakter Match gegen `entities.national_id` | sehr hoch; heilt Fragmentierung (gleiche Firma, streuende Namen) |

**Ablauf:**
1. Beim Login/Onboarding wird Stufe 1 automatisch versucht. Treffer → Gruppe/Entity vorgeschlagen.
2. Kein Domain-Treffer (Freemail o. Ä.) → Namensfeld (Stufe 2). Optionales USt-Feld (Stufe 3)
   verbessert/bestätigt.
3. Kandidaten werden **dedupliziert** (gleiche normalisierte Namen zu einer Zeile, Wins summiert)
   und **mit Konfidenz** gezeigt. Der User bestätigt einen → `company_group_id`/`company_entity_id`
   + `company_entity_conf` gesetzt.
4. Konfidenz `< 0.75` ⇒ Status „unbestätigt"; Verteidigungs-Leads (Ticket #1) gelten dann als
   „mutmaßlich eigener Vertrag".
5. Kein Treffer / „Andere Firma" → Pfad **unbekannte Firma** (Kurz-Version).

> Damit ist auch das „Wir haben CANCOM gefunden"-Mockup nicht mehr magisch: es ist der
> Domain-/Namens-Treffer aus Stufe 1/2, mit Konfidenz und Disambiguierung bei mehreren Kandidaten.

---

## Zwei Ebenen: Profil vs. Filter

| Ebene | Was | Wo | Persistenz |
|-------|-----|-----|------------|
| **Profil** | Grundeinstellung (CPV, Region, Volumen, Gruppe) | Onboarding + Einstellungen | dauerhaft |
| **Filter** | temporäre Einschränkung (Quelle, Vertragsart, Timing, Volumen-Band) | Explorer-Header | Session |

Der Relevanz-Score 🎯 kommt aus dem **Profil**-Match, nie aus Filtern.

---

## Unternehmensgruppen (korrigiert gegen die Realität)

### Was die Daten hergeben — und was nicht

- Gruppen entstehen aus E-Mail-SLD/Namensstamm (`domain_group_label` + Seed). Sie sagen
  **„diese Entitäten teilen ein Label"** — **nicht** „X ist die Holding von Y".
- `entity_group` ist flach. Es gibt **kein** `relation_type`, kein root. → im Ticket **gestrichen**
  (oder later extern via Handelsregister; nicht v1).
- **76,4 % der Firmen haben gar keine Gruppe** (1 Entität). Der Gruppen-Picker ist der Ausnahmefall.

### Pflicht vor Anzeige: Dedup + Konfidenz

Die rohe Gruppe (Bsp. CANCOM) enthält dieselbe Firma mehrfach und Buying-Unit-Rauschen. Vor der
Anzeige:
1. **Dedup** über die normalisierte Form (`normalize_company`): „CANCOM Public GmbH" (4 Datensätze)
   → **eine** Zeile, Wins summiert, mit Hinweis „4 Datensätze zusammengeführt".
2. **Konfidenz je Zeile** sichtbar (0.40 vs 1.00): niedrig-konfidente Mitglieder werden als
   „unsicher zugeordnet" markiert, nicht als Fakt.
3. Sortierung nach Wins; Rauschzeilen (0 Wins, reine Kostenstellen) einklappbar.

### Regeln (unverändert sinnvoll)

| Aktion | Erlaubt | Begründung |
|--------|---------|------------|
| Entität für Profil aktivieren/deaktivieren | ✓ | User entscheidet, was „er" ist |
| Entität zur Gruppe hinzufügen/entfernen | ✗ | System-definiert aus TED; Korrektur nur über Feedback |
| Fehler melden | ✓ | Feedback-Loop für Datenqualität (inkl. „gehört nicht zu uns" bei Fehlgruppierung) |

### Auswirkungen der Auswahl

| Bereich | Verhalten |
|---------|-----------|
| Profil / Relevanz | CPVs, Regionen, Wins aggregiert über **aktivierte** Entitäten (dedupliziert) |
| Verteidigung | Lead ist „meiner", wenn `incumbent_entity` ∈ aktivierte Entitäten (mit `incumbent_conf`) |
| Referenzen | zeigt, welche Entität gewonnen hat (inkl. Auflösungs-Konfidenz) |

---

## User-Profil: Vollständig (Quellen korrigiert)

> **Vorschlags-Prinzip: recall-first, der Nutzer ist der Filter.** Der Profil-Vorschlag ist
> editierbar — also nehmen wir **alles auf, was wir finden**, jeweils **mit sichtbarer Konfidenz**
> und nach Konfidenz sortiert. Ein übersehenes Signal (das der Nutzer manuell nachtragen müsste)
> ist teurer als ein schwaches, das er mit einem Klick entfernt. „Nimm alles rein" heißt **nicht**
> „stelle alles als sicher dar" — schwache Treffer werden als schwach markiert, nicht versteckt
> (markieren statt wegwerfen). Das gilt für Zertifikate, Kompetenzen, Regionen und Partner
> gleichermaßen.

### Bei bekannter Firma

| Bereich | Quelle | Status |
|---------|--------|--------|
| Stammdaten (Name, Adresse, USt-ID) | `entities` (+ national_id, wo vorhanden) | ✓ vorbefüllt |
| Unternehmensgruppe | `entity_group` / `dim_company_group` (dedupliziert) | ✓ vorbefüllt, **konfidenzbehaftet** |
| Kompetenzen (CPV/Branche) | aus Wins aggregiert (`leads.cpv_main`/`cpv_class`/`branche`) | ✓ vorgeschlagen |
| Regionen (NUTS) | aus Wins aggregiert | ✓ vorgeschlagen |
| Typische Deals | aus Win-Volumen — **nur `value_source≠unbekannt`**, Coverage-Hinweis | ◐ vorgeschlagen + Caveat |
| Referenzen (Wins) | `party_entity` (role=winner) → Notice | ✓ automatisch, mit Konfidenz |
| Partner (Konsortien) | Notices mit mehreren Winner-Entitäten | ✓ automatisch |
| Zertifizierungen | **abgeleitet**: Eignungsanforderung (cn-LEFTI/SelectionCriteria) → Gewinner via `ref_publication_number` (58,4 %); **konfidenzbehaftet** + manuell ergänzbar | ◐ vorgeschlagen (bestätigen), + manuell |

### Bei unbekannter Firma

| Version | Felder | Wann |
|---------|--------|------|
| Kurz | Firmenname, Branche, Region, Deal-Größe | Onboarding (Pflicht) |
| Lang | Zertifizierungen (manuell), manuelle Referenzen, „erneut in TED suchen" | später (optional) |

---

## Neubau vs. Bestand

| Baustein | Status | Quelle |
|----------|--------|--------|
| Gruppen (`entity_group`, `dim_company_group`), Entities+Konfidenz, Wins (`party_entity`) | ✅ existiert | Gold |
| CPV→Branche (`dim_cpv`), Deflator, Leads mit cpv_class/branche/value_source | ✅ existiert | Gold |
| **Onboarding-Matcher** (Domain/Name/USt → Kandidaten) | ⬜ Neubau (nutzt bestehende Primitive) | — |
| **Gruppen-Dedup + Konfidenz-Aufbereitung** für die Anzeige | ⬜ Neubau | — |
| **user_profiles / user_entity_selection / user_references / Filter** | ⬜ Neubau | — |
| **Branche-Auswahl-Layer** (User-facing, auf `dim_cpv.branche` aufsetzend) | ⬜ Neubau | — |
| **Zertifikats-Ableitung** (LEFTI/SelectionCriteria-Extraktion + cn→can-Zuschreibung) | ⬜ Neubau | `attributes` (Signal vorhanden) + `ref_publication_number` |
| **Auth, Feedback-Tabelle, S3-Attachments** | ⬜ Neubau | — |

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Profil definierbar: CPVs, Regionen (NUTS), Volumen-Range |
| 2 | CPV-Auswahl unterstützt Hierarchie (Klasse = alle Sub-CPVs) |
| 3 | Onboarding-Match über Domain → Name → USt (Abschnitt oben), Kandidaten mit Konfidenz, bestätigt |
| 4 | Bei bekannter Firma: Profil aus Wins vorgeschlagen (Deal-Größe **mit** Volumen-Coverage-Hinweis) |
| 5 | Gruppe wird **dedupliziert** und **mit Konfidenz je Entität** angezeigt; aktivier-/deaktivierbar |
| 6 | Normalfall „keine Gruppe / eine Entität" wird sauber behandelt (kein leerer Picker) |
| 7 | Gruppe nicht editierbar (nur aktivieren/deaktivieren); Fehler meldbar |
| 8 | Bei unbekannter Firma: Kurz-Version (Branche statt CPV-Codes), Lang-Version später |
| 9 | Zertifizierungen aus Eignungskriterien **abgeleitet** (mit Konfidenz, Nutzer bestätigt) + manuell ergänzbar |
| 10 | Filter im Explorer (Quelle, Vertragsart, Timing, Volumen-Band): temporär, sichtbar, einzeln entfernbar, „Reset" auf Profil-Defaults |
| 11 | Relevanz-Score aus Profil-Match; Profiländerung → async Neuberechnung |
| 12 | „Bund" als Regions-Sonderwert definiert (föderaler Käufer, siehe Logik), nicht als NUTS |

---

## Datenmodell

### Bestehend (Gold — nicht neu anlegen, darauf zeigen)

| Tabelle | Relevante Felder |
|---------|------------------|
| `leads` | `cpv_main`, `cpv_class`, `branche`, `sector`, `buyer_nuts`, `value_real_2020`, `value_source`, `value_band`, `contract_kind`, `source`, `incumbent_entity`, `incumbent_conf` |
| `entities` | `entity_id`, `canonical_name`, `national_id`, `method`, `confidence` |
| `entity_group` | `entity_id`, `group_id` (**flach**) |
| `dim_company_group` | `group_id`, `label` |
| `party_entity` | `notice_id`, `role`, `seq`, `entity_id` (Wins = role='winner') |
| `dim_cpv` | `division`, `label`, `sector`, `branche` |

### Neu: `company_group_view` (Anreicherung, kein Parallel-Store)

Materialisierte Sicht auf `entity_group` + `entities` + `party_entity`, **dedupliziert**:

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `group_id` | string | FK → `dim_company_group` |
| `entity_id` | string | Repräsentant nach Dedup |
| `merged_entity_ids` | string[] | zusammengeführte Roh-Entitäten (Transparenz) |
| `display_name` | string | normalisierter Anzeigename |
| `resolution_conf` | decimal | min/mittlere Konfidenz der zusammengeführten Datensätze |
| `total_wins` | int | Wins über die zusammengeführten Entitäten |
| `total_volume_known` | decimal | Summe nur über `value_source≠unbekannt` |
| `top_cpvs` | string[] | Top-CPVs |

> **Kein** `relation_type`/`root_entity_id` — nicht datengedeckt.

### Neu: `user_profiles`

Stammdaten (`user_id`, `company_name`, `company_entity_id` nullable, `company_group_id` nullable,
**`company_entity_conf`**, `address`, `vat_id`, `known_from_ted`, `profile_completeness`) ·
Suchkriterien (`cpv_codes`, `cpv_classes`, `branches`, `nuts_regions`, `is_federal` *(„Bund")*,
`volume_min`, `volume_max`, `volume_bands`) · Track Record (`total_wins`, `total_volume_known`,
`first_win_year`, jeweils nullable) · Timestamps.

### Neu: `user_entity_selection`

`user_profile_id`, `entity_id` (muss in `company_group_view` der Gruppe liegen), `active`,
`updated_at`. Uniqueness `(user_profile_id, entity_id)`.

### Neu: `user_references`, `user_partners`

Wie v1 — aber `entity_id`/`confidence` mitführen (Wins/Partner tragen Auflösungs-Konfidenz).

### Neu: `user_certifications`

`certification_type`, `source` (`'ted_implied'` | `'manual'`), `confidence` (bei implied: Extraktion ×
cn→can × Gewinner-Konfidenz), `evidence_notice_id` (die Ausschreibung, aus der die Anforderung
stammt), `is_mandatory` (Pflicht- vs. Wunsch-Kriterium), `valid_until` (nullable — TED nennt kein
Ablaufdatum → manuell), `confirmed` (User hat bestätigt).

### Neu: `group_feedback`

`feedback_type` (`missing_entity`, `wrong_entity`, `wrong_name`, `other`), `description`,
`attachment_url` (S3, nullable), `status`, `resolution_note`, Timestamps, `resolved_by`.

### Branche-Auswahl (kein Parallel-Mapping)

Die User-facing Branchenliste setzt auf **`dim_cpv.branche`** auf (Division-Ebene). Wo eine feinere
Auswahl gewünscht ist (z. B. „SAP" innerhalb IT), wird ein **optionaler Sub-Layer** definiert, der
explizit CPV-Klassen bündelt — 1:1, **keine** Mehrfachzuordnung eines CPV auf zwei Branchen. Ein
Branche-Key referenziert CPV-Klassen; jede Klasse gehört zu **genau einem** Key.

---

## API / Logik

### Endpunkte

| Methode | Endpoint | Beschreibung |
|---------|----------|--------------|
| POST | /api/onboarding/match | Domain/Name/USt → Kandidaten (Entity/Gruppe) mit Konfidenz |
| GET/PUT | /api/profile | Profil laden/aktualisieren |
| GET | /api/profile/suggest | Vorschlag aus Wins (mit Volumen-Coverage) |
| GET | /api/profile/group | Gruppe (dedupliziert, konfidenzbehaftet) |
| PUT | /api/profile/group/entities | Entitäten aktivieren/deaktivieren (validiert) |
| POST | /api/profile/group/feedback | Fehler melden |
| GET | /api/taxonomy/branches · /regions · /certifications | Taxonomien |

### Onboarding-Match (nutzt bestehende Resolution)

```python
def onboarding_match(email_domain=None, typed_name=None, vat_id=None):
    candidates = []
    # 1) Domain — dieselbe Logik, die die Gruppen baute
    if email_domain:
        label = domain_group_label(email_domain)      # leer bei Freemail
        if label:
            candidates += groups_by_label(label)       # + Win-Stats
    # 3) USt — exakter, hoch-konfidenter Anker; heilt Fragmentierung
    if vat_id:
        candidates += entities_by_national_id(vat_id)
    # 2) Name — Auffang
    if typed_name:
        key = blocking_key(typed_name)
        candidates += rank_entities(key, normalize_company(typed_name))
    # dedup + Konfidenz + Prominenz
    return dedupe_and_rank(candidates)                  # nie automatisch binden
```

### Relevanz-Score (identisch zu Ticket #1 — hier nur konsumiert)

```python
def calculate_relevance(lead, profile):
    return round(0.4*cpv_match(...) + 0.3*region_match(...) + 0.3*volume_match(...))

def region_match(lead_nuts, profile):
    if profile.is_federal and lead_is_federal_buyer(lead):   # „Bund": föderaler Käufer,
        return 100                                           # erkannt über looks_public/Name,
    if lead_nuts in profile.nuts_regions:                    # NICHT über NUTS
        return 100
    if nuts_parent(lead_nuts) in profile.nuts_regions:
        return 50
    return 0
```

`volume_match` / `cpv_match` wie in Ticket #1 (unbekanntes Volumen → 50; CPV über Hierarchie).

### Profil-Vorschlag (mit Coverage-Ehrlichkeit)

```python
def suggest_profile(selected_entity_ids):
    wins = get_wins(selected_entity_ids)                 # dedupliziert
    valued = [w for w in wins if w.value_source != 'unbekannt']
    return {
      "branches": map_cpvs_to_branches(wins),            # via dim_cpv.branche
      "nuts_regions": top_regions(wins),
      "deal_size": percentiles(valued) if valued else None,
      "deal_size_coverage": len(valued)/len(wins),       # UI zeigt „nur X% mit Volumen"
      "partners": consortium_partners(selected_entity_ids),
      "certifications_implied": infer_certifications(selected_entity_ids),
    }

def infer_certifications(entity_ids):
    """Zertifikate aus den Eignungsanforderungen gewonnener Ausschreibungen ableiten.
    Anforderung (cn-LEFTI/SelectionCriteria) → Gewinner (can via ref_publication_number).
    Recall-first: ALLES aufnehmen, was wir finden — Pflicht UND Wunsch, auch schwache
    Extraktion. Die Nuancen (mandatory?, 'oder gleichwertig', Link vorhanden?) senken die
    Konfidenz, filtern aber NICHT raus. Der Nutzer prunt."""
    certs = []
    for can in wins_as_can(entity_ids):
        cn = link_cn(can.ref_publication_number)          # 58,4 % verknüpfbar
        if not cn:
            continue                                      # ohne Anforderungstext kein Signal
        for req in extract_cert_reqs(cn):                 # Keyword/Muster auf LEFTI-Pfaden
            certs.append({
                "type": req.cert,                         # ISO_27001, BSI_C5, …
                "is_mandatory": req.mandatory,            # Flag, KEIN Filter (Pflicht→höhere Konf.)
                "evidence_notice_id": cn.notice_id,
                "confidence": req.extract_conf * cn.link_conf * can.winner_conf,
            })
    return dedupe_max_conf(certs)                          # je Cert höchste Konfidenz, konf-sortiert
```

---

## Edge Cases (aktualisiert)

| # | Case | Verhalten |
|---|------|-----------|
| 1 | Firma nicht in TED | Kurz-Profil, kein Vorschlag |
| 2 | Firma < 3 Wins | Vorschlag + „wenige Daten" |
| 3 | Keine Gruppe (Normalfall, 76 %) | Einzel-Entity, **kein** Gruppen-Picker |
| 4 | Gruppe mit Duplikaten | dedupliziert anzeigen (Merge-Hinweis) |
| 5 | Niedrig-konfidente Entität in Gruppe | „unsicher zugeordnet"-Markierung |
| 6 | Alle Entitäten abgewählt | Fehler „mindestens eine auswählen" |
| 7 | Keine CPV/Branche | Fehler „mindestens eine Branche" |
| 8 | Keine Region | Default = alle DE-Regionen |
| 9 | Deal-Größe-Vorschlag, aber Volumen meist unbekannt | Range zeigen **+** „nur X % der Wins mit Volumen" |
| 10 | Neue Entität in TED taucht auf | bei Login „neue Entität gefunden — hinzufügen?" (mit Konfidenz) |
| 11 | Zwei User derselben Gruppe | je eigenes Profil + eigene Auswahl |
| 12 | Filter → 0 Leads | „keine Leads mit diesen Filtern [Reset]" |
| 13 | Doppelte Fehlermeldung | „bereits gemeldet, Status: in Bearbeitung" |

---

## Out of Scope

Lead-Liste (#1) · Score-Details (#4) · Lead-Detail (#3) · Einstellungen-UI komplett & Alert-Config
(#10) · Admin-Dashboard für Feedback (v2) · automatische Feedback-Validierung (v2) ·
`relation_type`/Konzernhierarchie (extern, v2). Zertifikats-Ableitung ist v1 **recall-first**
(alles Gefundene als konfidenzbehafteter Vorschlag); v2 = **Präzision** (bessere Extraktion, „oder
gleichwertig"/Negation, die ~42 % ohne cn→can-Link erschließen).

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| Gold `leads`/`entities`/`entity_group`/`dim_company_group`/`party_entity`/`dim_cpv` | ✅ existiert |
| `domain_group_label` / `normalize_company` / `blocking_key` (Onboarding-Match) | ✅ existiert |
| Gruppen-Dedup-View | ⬜ Neubau |
| Branche-Auswahl-Layer auf `dim_cpv.branche` | ⬜ Neubau |
| Zertifikats-Extraktion (`attributes` LEFTI/SelectionCriteria) + cn→can-Link | ⬜ Neubau (Signal ✅ vorhanden) |
| Auth-System | ⬜ vorher nötig |
| S3 für Feedback-Attachments | ⬜ Setup |

---

## Testfälle (aktualisiert)

| # | Test | Erwartung |
|---|------|-----------|
| 1 | Onboarding via Firmen-Domain | Gruppe automatisch vorgeschlagen (Konfidenz sichtbar) |
| 2 | Onboarding via USt-IdNr | fragmentierte Entitäten zu einer Firma zusammengeführt |
| 3 | Onboarding via Name, mehrere Treffer | Disambiguierungs-Liste, User wählt |
| 4 | Bekannte Firma mit Duplikat-Gruppe | dedupliziert, Wins summiert, Merge-Hinweis |
| 5 | Niedrig-konfidente Entität | „unsicher"-Markierung |
| 6 | Firma ohne Gruppe (Normalfall) | Einzel-Entity, kein Picker |
| 7 | Entität aktivieren/deaktivieren | Wins/Verteidigung passen sich an |
| 8 | Fremde Entität aktivieren (API) | 403 „gehört nicht zu deiner Gruppe" |
| 9 | Deal-Größe bei meist unbekanntem Volumen | Range + Coverage-Hinweis |
| 10 | Zertifikat abgeleitet (Pflicht-ISO-27001-Ausschreibung gewonnen) | als „impliziert" mit Konfidenz + Beleg-Notice vorgeschlagen, User bestätigt; manuell ergänzbar |
| 11 | „Bund" im Profil, föderaler Lead | Region-Match 100 |
| 12 | CPV-Klasse wählen | alle Sub-CPVs inkludiert |
| 13 | Filter setzen/entfernen | sofort; Reset auf Profil-Defaults |
| 14 | Profil ändern | Relevanz async neu |
| 15 | Fehler melden (mit/ohne Beleg) | gespeichert, Status pending |
| 16 | Doppelte Fehlermeldung | „bereits gemeldet" |

---

## Offene Fragen

| # | Frage | Entscheidung |
|---|-------|--------------|
| 1 | CPV-Hierarchie-Tiefe? | 2 Ebenen (Klasse + Code) |
| 2 | Branche-Taxonomie? | ✅ `dim_cpv.branche` (Division) + optionaler 1:1-Sub-Layer, **keine** Mehrfachzuordnung |
| 3 | Regionen-Granularität? | NUTS-1 + „Bund" als föderaler Sonderwert (über Käufer-Typ, nicht NUTS) |
| 4 | Zertifikate aus TED? | ✅ **ja, ableitbar** (cn-LEFTI → Gewinner, 58,4 %); v1 **recall-first**: alles Gefundene als konfidenzbehafteter, editierbarer Vorschlag, manuell ergänzbar |
| 5 | `relation_type`/Holding? | ✅ raus aus v1 (nicht ableitbar; ggf. extern in v2) |
| 6 | Onboarding-Einstieg? | ✅ Domain → Name → USt, dedupliziert, konfidenzbehaftet, bestätigt |
| 7 | Gruppen-Duplikate? | ✅ vor Anzeige über `normalize_company` mergen |
| 8 | Deal-Größe bei unbekanntem Volumen? | Range nur aus bekannten Werten + Coverage-Hinweis |
| 9 | Filter persistent? | v2 — erstmal Session-only |

---

## Anhang: Branche

v1-Basis = **`dim_cpv.branche`** (existiert, Division-Ebene). Ein optionaler feinerer Sub-Layer
bündelt CPV-**Klassen** (4-stellig) zu User-Labels — jede Klasse gehört zu genau einem Label
(keine Kollision wie „72212 → cloud_managed UND sap_erp"). Vollständiges Sub-Mapping in separatem
Dokument, sobald der Bedarf über die Division-Ebene hinaus bestätigt ist.
