# v3-Ticket: Vergabeunterlagen-/Vorbereitungstool (Template-Bibliothek + Extraktion)

**Status:** geparkt (v3+, hinter dem §298-StGB-Gate). Nicht in v1. Erst bauen, wenn das
Lead-/Intelligence-Produkt (v1) am Markt ist.

## Kernidee
Bieter lädt die Vergabeunterlagen eines Leads hoch → wir extrahieren Anforderungen/Struktur
→ füllen die passenden amtlichen Formblätter vor → Anforderungs-Check. Schwerpunkt-Verschiebung
von „Lead finden" zu „Lead gewinnen".

## Bewertung (2026-07, ehrlich)
- **Wert liegt NICHT im Hosten der Formulare** — EVB-IT/VHB sind für jeden frei, kein Burggraben.
  Der Wert ist die **Extraktion/Zuordnung** (tender-spezifische Anforderungen → richtige Blätter
  vorbefüllen). Seed-Bibliothek öffentlicher PDFs ist der wertloseste Teil.
- **Flywheel = Phase 2 (User-Upload).** User lädt Unterlagen → wir lernen Struktur und (später)
  echte Bieter-Preise. Genau hier greift das **§298-StGB-Gate**: bis rechtlich geklärt nur die
  sichere Variante (Extraktion für den einzelnen User, KEINE cross-customer Preis-Intelligenz).
- **Phase 3 (Plattform-Partnerschaft)** ist Henne-Ei — braucht bereits Bieter-Traktion. Nordstern,
  kein früher Move.
- **Crawlen von Vergabeplattformen: NICHT tun.** Registrierung nötig, AGB verbieten i. d. R.
  automatisierten Zugriff, Dokumente hinter Login sind nicht unsere zum Weiterverteilen.

## Rechtlicher Haken (wichtig)
EVB-IT/VHB-Formblätter sind **nicht** §5 Abs. 1 UrhG (keine Gesetze/Erlasse/Entscheidungen),
allenfalls §5 **Abs. 2** — dann mit **§62 (Änderungsverbot)** + **§63 (Quellenangabe)**.
→ Verteilen und Ausfüllen (Bestimmungszweck) ok; amtlichen Klausel-Text **umschreiben** nicht.

## Freie Quellen (verifiziert 2026-07, für später)
- EVB-IT: seit 2024 einheitliche **modulare Rahmenvereinbarung** (nicht mehr „6 Vertragstypen") —
  cio.bund.de → EVB-IT & BVB. Zusätzlich Tool „EVB-IT digital" (OpenCoDE).
- VHB Formblatt 124 (Eigenerklärung Eignung) + 124_LD (Liefer/Dienst), 125 (Verpflichtungserklärung)
  — BBR (bbr.bund.de) / fib-bund.de. Ganze VHB-Lesefassung 2017/2023 auf fib-bund.de.
- **Kostenpflichtig (nicht frei):** GEFMA-Richtlinien, STLB-Bau. Nicht einsammeln.

## Nächster Schritt, wenn v3 startet
1. ~10 amtliche Formulare nach `data/reference/templates/` ziehen (EVB-IT-Module, VHB 124/124_LD/125, UfAB).
2. Extraktions-Prototyp gegen 20–30 echte IT-Ausschreibungen (Anforderungen/Preisblatt/Bewertungsmatrix).
3. Template-Struktur definieren; Upload-Flow (Phase 2) mit Extraktion-only.
