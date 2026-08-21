# goVisor — Vollständige Feature-Liste

> ⚠ **STAND 2026-08-21: Die Erfolgsprämie ist gestrichen.** Alles unten zum Thema Success-Fee ist Entscheidungsgeschichte, kein geltendes Modell. Aus dem Produkt ist sie entfernt (Code + Texte), das Schema räumt `supabase/0012_erfolgspraemie_entfernen.sql`.

Struktur → Feature → Erklärung. Basis für die Landingpage. **Reifegrad:** 🟢 live/verifiziert ·
🟡 gebaut (funktioniert, ggf. an Demo-/Teildaten) · ⚪ Stub/ruht (Gerüst da, noch nicht scharf).
Stand: 2026-07-30.

---

## A. Datenfundament — was goVisor überhaupt „sieht"

| Feature | Erklärung | Reife |
|---|---|---|
| **DACH-Abdeckung** | Deutschland lückenlos 2004–2026 (270 Monate, 1,83 Mio Bekanntmachungen, 0 Dubletten), plus Österreich und Schweiz. | 🟢 |
| **Mehrere Quellen, nicht nur TED** | Oberschwellig aus TED **+ unterschwellig** aus nationalen Portalen (DÖE/oeffentlichevergabe.de, OffeneVergaben.at, simap.ch). Genau das, was reine TED-Aggregatoren nicht sehen. | 🟢 |
| **Los-Ebene** | Das Los ist die Bietentscheidung — goVisor führt sie separat, mit zwei Dritteln des eigentlichen Freitexts. | 🟢 |
| **Volles CPV-Vokabular** | 9.454 CPV-Codes mit deutschen Klartext-Labels, Branchen-Zuordnung. | 🟢 |
| **Ehrlichkeits-Prinzip** | Jeder Wert trägt seine Herkunft: gemessen / geschätzt / unsicher / unbekannt — nie geraten, sondern gekennzeichnet. | 🟢 |
| **Verlustfreie Pipeline** | Medaillon-Architektur (Bronze→Silber→Gold); nichts wird nach Relevanz weggeworfen, Zweifelsfälle landen in einer Review-Queue. | 🟢 |

## B. Lead-Entdeckung & Suche

| Feature | Erklärung | Reife |
|---|---|---|
| **Auslauf-Radar** | Zeigt Verträge, die auslaufen — bevor die Nachfolge ausgeschrieben ist. Der Frühwarn-Kern. | 🟢 |
| **Offene Ausschreibungen** | Aktuell laufende Verfahren (mit zukünftiger Angebotsfrist) als bietbare Leads. | 🟢 |
| **Volltextsuche** | Über Titel + Beschreibung + Los — volle Teilstring-Semantik (findet „Großwärmepumpe"). | 🟢 |
| **Such-Tokens** | Ort/PLZ, Auftraggeber, Stichwort als kombinierbare Filter-Chips. | 🟢 |
| **Umkreissuche** | Stadt- oder PLZ-Eingabe + Radius (5–100 km), echte Haversine-Distanz; Stadtname-Autocomplete über 16k-Städte-Index. | 🟢 |
| **Regionssuche** | NUTS-Regionen mit Namens-Autocomplete + Drill-down; Achse **Leistungsort vs. Käufersitz** umschaltbar. | 🟢 |
| **Bundesweit-Logik** | Ortsungebundene Leistungen fallen nicht aus der Umkreissuche, sondern werden als „bundesweit" einsortiert. | 🟢 |
| **Branchen-/Grundraum-Umschalter** | 6 Grundräume (Bau, IT, Medizin, Beratung, Sicherheit, Energie); Zähler je Branche **bezogen auf den aktiven Orts-Filter**. | 🟢 |

## C. Filter & Listen-Steuerung

| Feature | Erklärung | Reife |
|---|---|---|
| **15 Filter-Sektionen** | Land (DACH), Phase, Frist/Vertragsende-Horizont, Fachgebiet (CPV), Region, Vergabestelle, Wettbewerb, **Relevanz**, **Chance**, **Aufwand**, Leistungsart, Vertragsart, Rechtsrahmen, Auftragswert, Weitere (nur mit Detail/Unterlagen). | 🟢 |
| **Multi-Kriterien-Kombination** | Alle Filter greifen per UND — z. B. „geringer Aufwand + hohe Chance + Region München". | 🟢 |
| **Sortierbare Spalten** | Kombiniertes Ranking, Frist, Volumen, Relevanz, Wechsel-Chance, Aufwand, Konkurrenz. | 🟢 |
| **Anpassbare Tabelle** | Spalten per Drag-&-Drop umsortieren, ein-/ausblenden, Breite ändern; Herkunfts-Spalten (Quelle, Phase). | 🟢 |
| **CSV-Export** | Die aktuell gefilterte Liste als CSV herausziehen. | 🟡 |

## D. Lead-Bewertung — die Intelligenz je Lead

| Feature | Erklärung | Reife |
|---|---|---|
| **Empfehlung (Ampel)** | Kopf-Verdikt je Lead: Antreten / Offen / Überspringen. | 🟢 |
| **Bid/No-Bid-Einordnung** | „Solltest du bieten?" aus Chance × Aufwand × Eignung, mit K.o.-Vorschaltung (Klarer Fall / Abwägen / Mitnahme / Meiden). | 🟢 |
| **Relevanz** | Profil-Passung aus CPV + Region + Volumen (braucht Profil). | 🟢 |
| **Wechsel-Chance / Verdrängbarkeit** | Wie angreifbar ist der Amtsinhaber — relatives Ranking nach Bieterzahl × Branche. | 🟢 |
| **Aufwands-Indikator** | Intrinsisch aus Bürgschaft, Bindefrist, Eignungsnachweisen, Zuschlagskriterien — auch ohne Profil. | 🟢 |
| **Konkurrenz/Bieterzahl** | Zuletzt eingegangene Angebote (single-bidder-Nähe als Chance-Signal). | 🟢 |
| **Nachfolge-Kette** | „N Verträge in Folge seit YYYY" + Amtsinhaber + seit-wann — deckt bei offenen Leads Incumbent/Wechsel auf. | 🟢 |

## E. Lead-Detail — die Tabs

| Tab | Inhalt | Reife |
|---|---|---|
| **Übersicht** | Eckdaten mit Herkunfts-Flags: Volumen, Frist, Laufzeit, Wettbewerbslage, Land, Leistungsort, Vertragsart, Rechtsrahmen, Verfahren. | 🟢 |
| **Teilnahme** | Angebotsfrist + Resttage (dringlichkeitsgefärbt), Rückfragefrist, Submissionstermin, Bindefrist, Bürgschaft, **Zuschnitt/Lose** (nur bei echter Mehr-Los-Vergabe). | 🟢 |
| **Unterlagen** *(neu)* | Vergabe-Analyse / Upload / Volltext — siehe Abschnitt F. Upload nur bei offenen Ausschreibungen. | 🟢 |
| **Bewertung** | 8 Abschnitte: Bewertung, Zuschlagskriterien, **Direktvergleich Du↔Incumbent**, Anforderungs-Check, Lücke, Deine Verträge beim Käufer, Wettbewerbs-Historie, Nächster Schritt. | 🟡 |
| **Vergabestelle** | Käufer-Dossier: „Ist der Käufer aktiv?" (Pro-Feature). | 🟡 |
| **Markt** | Nachfrage / Feld-Schwäche / Struktur des CPV-Segments (Pro-Feature). | 🟡 |
| **Team** | Geteilte Notizen + automatischer Verlauf (Merken/Status/Analyse protokolliert). | 🟢 |

## F. Vergabeunterlagen-Analyse — der Dokument-Layer *(neu, Alleinstellung)*

| Feature | Erklärung | Reife |
|---|---|---|
| **Volltext-Extraktion** | Vergabeunterlagen (ZIP/PDF/DOCX/XLSX, auch verschachtelt) → durchsuchbarer Volltext im Lead. | 🟢 |
| **Regelbasierte Signale** | Bürgschaft, Bindefrist, Eignungsnachweise, geforderte Zertifikate, Nebenangebote, Zuschlagsgewichte — automatisch erkannt. | 🟢 |
| **LLM-Vergabe-Analyse** | Aus 80 Seiten PDF in Sekunden: **Ampel** (bietbar/abwägen/Hürde), abhakbare **Bieter-Checkliste** (K.o.-Kriterien, Eignungsnachweise, Aufwandstreiber), Zuschlagsgewichte, Fristen. | 🟢 |
| **„Wir füllen vor"** | Liste der Angaben, die sich aus dem Firmenprofil vorausfüllen ließen (Firmenstammdaten, Referenzen, Eigenerklärungen). | 🟢 (Liste) / ⚪ (echtes Ausfüllen offen) |
| **Upload-Feld** | Nutzer zieht die Unterlagen rein (3-Schritte: Portal-Link → hochladen → Analyse), ~7 s bis Ergebnis. Umgeht das Portal-Gating sauber. | 🟢 |
| **Multi-Key-LLM-Fallback** | Mehrere API-Keys bündelbar; bei leerem Guthaben automatische Rotation. | 🟢 |

## G. Vergabestellen-Sicht — eigenes Produkt „Vergabeblick"

Nicht nur ein Bieter-Tab, sondern eine **eigene Rolle** (Route `/authority`, Umschalter
„↔ Vergabestelle", in Produktion rollen-gegatet). Vollständige Liste: **`feature-inventory-vergabestelle.md`**.

| Feature | Erklärung | Reife |
|---|---|---|
| **Käufer-Dossier (im Bieter-Detail)** | „Ist der Käufer aktiv?" — die Vergabestelle aus Bietersicht. | 🟡 |
| **Vergabeblick-Dashboard** | Wie steht meine Stelle da: Ø Bieterzahl (Ein-Bieter-Warnung), KMU/Preis/Wechsel, Top-Anbieter. | 🟢 |
| **Ausschreibungscheck** | Entwurf (Feld/Lose/Bürgschaft/Umsatz/Wert) → marktgestützte Hinweise + **Bieterzahl-Prognose**, *bevor* ausgeschrieben wird. Das verkaufbare Kernstück der Vergabestellen-Sicht. | 🟢 |
| **Markterkundung / Controlling / Pflichten** | Anbieterlandschaft, Peer-Vergleich (Comps), KMU-/Preis-Benchmark. | 🟢 |
| **Fragmentierungs-Ehrlichkeit** | Zeigt den zusammengeführten Teil einer Stelle transparent („Teilbild"-Badge). | 🟢 |

## H. Strategie / Potenzial — der Markt-Explorer

| Unteransicht | Frage, die sie beantwortet | Reife |
|---|---|---|
| **Pipeline** | Was kommt in 12/24/36 Monaten? | 🟡 |
| **Felder (White-Space)** | Wo ist Platz, wo ist es eng? Marktchancen-Score je CPV-Segment (Nachfrage × Schwäche × Wert), Make/Buy/Partner. | 🟡 |
| **Vergabestellen** | Wo lohnt Beziehungsaufbau? | 🟡 |
| **Wettbewerb** | Wer holt was, wer hält was? (Incumbent-Retention, Head-to-Head) | 🟡 |
| **Position / Fähigkeiten / Bindung / Profil** | Wo stehen wir, was blockiert uns, was ist uns verschlossen, wer sind wir? | 🟡 |
| **Verzweiflungs-Chronik** | Chronisch erfolglose Ausschreibungen („seit X Jahren Y-mal gesucht") — stärkster Kauf-/Chancen-Hinweis. | 🟢 (Daten) |
| **CPV-Nähe** | Offene Märkte nah am eigenen Skill (Firmen-Co-Occurrence). | 🟢 (Daten) |

## I. Netzwerk — Bietergemeinschaften

| Feature | Erklärung | Reife |
|---|---|---|
| **Partnersuche** | Mehr-Los-Vergaben, bei denen ein Partner weitere Lose abdecken kann; beidseitig freiwillige Freigabe. | 🟡 |
| **Konsortial-Erkennung** | Bietergemeinschaften werden als solche erkannt und geflaggt. | 🟢 (Daten) |

## J. Arbeits-Workflow (Team/CRM-artig)

| Feature | Erklärung | Reife |
|---|---|---|
| **Merkliste** | Leads merken (Stern), eigene Ansicht. | 🟢 |
| **Status/Workflow** | Interessant / In Prüfung / Offene Fragen / Verworfen je Lead. | 🟢 |
| **Team-Notizen** | Geteilte Kommentare je Lead, fürs Team sichtbar. | 🟢 |
| **Verlauf/Aktivitätslog** | Merken, Status, Notizen, Öffnen werden automatisch protokolliert. | 🟢 |
| **Als gewonnen markieren** | Legt aus dem Lead direkt einen Vertrag an (Grundlage für Auslauf-Tracking + Erfolgsprämie). | 🟡 |

## K. Ausgaben & Benachrichtigung

| Feature | Erklärung | Reife |
|---|---|---|
| **Briefing/Dossier** | 1-Seiten-Briefing je Lead als Word oder Markdown, mit goVisor-Deep-Link (führt Empfänger zurück). | 🟢 |
| **Alerts** | Frist-/Auslauf-/Award-Benachrichtigungen (Logik + UI gebaut, E-Mail-Versand als Stub). | ⚪ |
| **Kalender-Feed** | Fristen als abonnierbarer ICS-Feed (Token-URL). | 🟡 |

## L. Onboarding & Profil

| Feature | Erklärung | Reife |
|---|---|---|
| **Profil** | CPV-Schwerpunkte, Regionen, Volumen-Band, Nachweise/Zertifikate — schaltet die profilbasierte Relevanz frei. | 🟡 |
| **Firmengruppe/Identität** | „Gruppe = Identität" — Schwester-Firmen zusammengeführt (Winner-Matching, Onboarding). | 🟢 (Daten) |

## M. Account, Billing, Konto

| Feature | Erklärung | Reife |
|---|---|---|
| **Registrierung/Login** | Supabase-Auth; Registrierung schaltet Leads frei. | 🟡 |
| **Settings** | Profil, Firmengruppe, Zahlung, Rechnungen, Benachrichtigungen, Account, Daten-Export, Account-Löschung. | 🟡 |
| **Billing / Abo** | Abo-Zahlung über Stripe (Stub, kein Provider-Key). Die Erfolgsprämie ist am 2026-08-21 gestrichen. | ⚪ |
| **Free/Pro-Gating** | Analyse-Tabs (Vergabestelle, Markt) hinter Paywall; Bewertungs-Limit im Free-Tier. | 🟡 |
| **Analytics** | Event-Layer für Nutzungsauswertung. | 🟡 |

## N. Regionale & rechtliche Spezifika

| Feature | Erklärung | Reife |
|---|---|---|
| **DACH-Länderfilter** | DE/AT/CH mit Landeskennzeichnung. | 🟢 |
| **Rechtsrahmen-Filter** | VgV / VOB / UVgO / SektVO (höchste Feld-Abdeckung im Inventar). | 🟢 |
| **Preismodell** | 7-Band-Flat-Fee-Staffel (abrechenbar auf echtem Wert, Rest via Kunden-Bestätigung). | 🟡 |

## O. Datenqualität & Vertrauen (Querschnitt — Marketing-Substanz)

| Feature | Erklärung | Reife |
|---|---|---|
| **Herkunfts-Punkte (Provenance)** | Jeder Wert farbcodiert: gemessen / geschätzt / unsicher / unbekannt. | 🟢 |
| **Entity-Resolution** | Vergabestellen konsolidiert über Leitweg-ID, Handelsregister, AGS-Behördenverzeichnis, kommunale Gruppierung. | 🟢 (Daten) |
| **Nachfolge-Modell** | 100k verifizierte Vertrags-Nachfolgen (inhaltsbasiert + LLM-adjudiziert) statt naiver Paarung. | 🟢 (Daten) |
| **Review-Queue** | Harte Datenfehler als Worklist statt stillem Wegwerfen. | 🟢 (Daten) |

---

## Landingpage-Destillat (die stärksten Verkaufsargumente)
1. **Unterschwellig + oberschwellig** — nicht nur TED, sondern die nationalen Portale, die die Konkurrenz nicht sieht.
2. **Auslauf-Radar** — Verträge sehen, *bevor* sie ausgeschrieben werden.
3. **Vergabeunterlagen-Analyse** — aus 80 Seiten PDF in Sekunden Ampel + abhakbare Bieter-Checkliste (Alleinstellung).
4. **Ehrliche Daten** — jeder Wert mit Herkunft; nie geraten.
5. **DACH-weit** — DE/AT/CH in einem Werkzeug.
6. **Bid/No-Bid-Entscheidung** — nicht nur „hier ist ein Lead", sondern „solltest du bieten und wie".
