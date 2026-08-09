# Feature #23: Vergabeunterlagen-Analyse & Bausteinbibliothek

**Produkt:** goVisor
**Version:** 1.0 (Struktur-Studie vollständig, Q1b nachgemessen)
**Status:** Bau-Spezifikation
**Erstellt:** 2026-07-30
**Abhängigkeiten:** #11 (Treffergüte/Ergebnisdaten), #12 (Losebene), #13 (Unterlagen-Link), #15 (Anforderungen), #17 (Cockpit), #18 (Aufwand)

---

## 1. Umfang

Der Nutzer lädt Vergabeunterlagen zu einem Lead hoch. Das System erzeugt daraus eine Checkliste und
Textbausteine aus seinem Profil.

**Nicht im Umfang:** Ausfüllen von Dokumenten. Das System liefert Bausteine und Checklisten; das
eingereichte Angebot verantwortet der Nutzer.

---

## 2. Konstanten aus der Struktur-Studie

Grundlage für Dimensionierung und Grenzwerte (237 Vorgänge, ~4.700 Dateien):

| Kennzahl | Wert |
|---|---|
| Dateien je Vorgang | Median 20 · p75 33 · Max 196 |
| PDF-Seiten je Vorgang | Median 90 · p75 176 · Max 2.883 |
| Tokens je Vorgang | Median 61k · p75 128k · Max 1,55 Mio |
| Reine Bild-PDFs (OCR nötig) | 3 % |
| Aus Dateiname klassifizierbar | 69 % |
| Zuschlagskriterien: eigenes Dok / eingebettet / nicht gefunden | 24 % / 24 % / 52 % |
| Los-benannte Dateien | 8 % |
| GAEB im Bau | 84 % |
| Ausfüllbare PDFs | 24–85 % je Branche |
| Excel-Preisblätter | 14–85 % je Branche |
| Mehrere Datumsstände im Paket | 14 % |
| **Boilerplate-Anteil je Dokumenttyp (Q1b)** | **0–27 %**, Jaccard ~0,00 |

**Q1b-Befund (bindend für die Architektur):** Es existiert **kein bundesweiter Standardformular-Layer**.
Selbst Bewerbungsbedingungen, Eigenerklärungen und Zuschlagskriterien teilen nur 20–27 % wörtliche
Passagen; Leistungsbeschreibung, Vertrag und Aufforderung praktisch nichts. Die Standardisierung ist
**prozedural, nicht textlich** — jede Vergabestelle, jedes Portal und jede VHB-Version erzeugt eigene
Wortlaute.

**Konsequenz:** Kein Template-Caching, keine Entdopplung über Vorlagen. Verarbeitung erfolgt **pro
Dokument**. Der Kostenhebel ist gezielte Dokumentauswahl (§6.1) plus strukturierte Parser (§6.2).

**Nutzbar bleibt die Struktur:** Welche Dokumenttypen zu erwarten sind (Q1a: 4-Typen-Kern in 70–91 %)
und wie sie erkannt werden (Q3: 69 % per Dateiname). Struktur steuert die Auswahl, Inhalt wird einzeln
verarbeitet.

---

## 3. Architektur — zwei Ebenen

| Ebene | Inhalt | Sichtbarkeit | Schreibrecht |
|---|---|---|---|
| **A — Checkliste je Lead/Los** | verfahrensspezifische Anforderungen, Fristen, Kriterien | alle Nutzer desselben Leads | nur Systemprozess |
| **B — Bausteine je Profil** | Firmentexte des Nutzers | ausschließlich eigenes Profil | Nutzer |

Ein verfahrensübergreifender Katalog entfällt (Q1b, §2). Die Wiederverwendung wirkt **innerhalb eines
Leads**: Lädt ein zweiter Nutzer dasselbe Paket hoch, wird die vorhandene Checkliste genutzt.

**Pflicht:** Der Systemprozess, der Ebene A erzeugt, erhält **keine Datenbankberechtigung auf
Ebene-B-Tabellen**. Getrennte Service-Identitäten. Die Trennung wird über Rechte erzwungen, nicht über
Code-Konventionen.

**Anforderungs-Taxonomie:** Anforderungen werden **semantisch** klassifiziert (z. B. `referenz_mindestwert`,
`zertifikat`, `mindestumsatz`), nicht über Textabgleich. Die Taxonomie ist verfahrensübergreifend
gültig und speist #15 sowie die Themenzuordnung der Bausteine (§9.3). Sie ist ein Klassifikationsziel,
kein Textcache.

---

## 4. Upload

### 4.1 Eingabefeld

Drag-&-Drop über volle Kartenbreite, ZIP als Primärfall.

```
┌─────────────────────────────────────────────────────────┐
│        Vergabeunterlagen hier ablegen                    │
│        am besten das komplette ZIP vom Portal            │
│                                                          │
│        Auch einzelne PDF-, Word- oder Excel-Dateien.     │
│        Je vollständiger, desto besser die Analyse.       │
│                                                          │
│                  [ Dateien auswählen ]                   │
└─────────────────────────────────────────────────────────┘
   ① Beim Vergabeportal herunterladen ↗
```

Akzeptierte Formate: ZIP (auch verschachtelt), PDF, DOCX, XLSX, GAEB (D81/D83/X83).

### 4.2 Grenzwerte

| Grenze | Wert |
|---|---|
| Paketgröße | 500 MB |
| Dateien je Paket | 250 |
| Kompressionsverhältnis | max. 100:1 (ZIP-Bomben-Schutz) |
| Verschachtelungstiefe ZIP | 3 |
| Uploads je Profil und Stunde | 20 |

### 4.3 Erkennungsansicht

Nach dem Entpacken, vor der Analyse:

```
Erkannt: 20 Dateien

✓ Aufforderung zur Angebotsabgabe
✓ Leistungsbeschreibung (89 Seiten)
✓ Zuschlagskriterien
✓ 4 Standardformulare
✓ Preisblatt (Excel, 47 Positionen)
· 3 weitere Dokumente

⚠ Keine Eignungsnachweise gefunden — falls vorhanden, bitte nachladen.
```

Fehlende erwartete Dokumenttypen werden benannt (Erwartungswerte aus §2, Spalte „Anteil der Vorgänge
je Dokumenttyp" der Studie).

### 4.4 Quotenhinweis

Vor Start der Analyse, immer:

> Analyse starten — verbraucht eine deiner 3 Analysen diesen Monat (2 verbleibend).

### 4.5 Verarbeitungsanzeige

Phasen sichtbar: `Unterlagen gelesen · Anforderungen abgeglichen · Textbausteine aus deinem Profil erstellt`

**Pflicht:** Die Anzeigedauer ist unabhängig davon, ob eine geteilte Checkliste bereits existiert
(§12.4). Keine Meldung über vorhandene Analysen.

---

## 5. Prüfungen vor der Analyse

Reihenfolge einhalten. Jede Prüfung mit definiertem Abbruch- oder Warnverhalten.

| # | Prüfung | Verfahren | Verhalten |
|---|---|---|---|
| 1 | **Malware** | Scan aller entpackten Dateien | Abbruch, Paket verwerfen |
| 2 | **Pfadprüfung** | Zip-Slip: keine Pfade außerhalb des Zielverzeichnisses | Abbruch |
| 3 | **Eigenes Angebot** | Erkennungsmerkmale: Preisangaben in Angebotsform, Firmenbriefkopf des Uploaders, Formulierungen aus Bietersicht | Abbruch mit Hinweis: „Das sieht nach einem eigenen Angebot aus. Für die Bibliothek nutze bitte den Import unter Profil." |
| 4 | **Zuordnung zum Lead** | Abgleich Titel, Vergabestelle, Aktenzeichen, CPV gegen Lead-Metadaten | Bei Abweichung Rückfrage, kein stiller Durchlauf |
| 5 | **Doppelung** | Paket-Hash gegen `doc_packages` | Vorhandene Checkliste nutzen, keine Quote verbrauchen |
| 6 | **Plausibilität** | §12.2 | Bei Widerspruch: Analyse nur lokal, nicht in Ebene A |

---

## 6. Verarbeitung

### 6.1 Verarbeitungsreihenfolge

Kein Template-Caching (Q1b). Der Hebel ist Auswahl und Parser.

| Schritt | Verfahren | LLM |
|---|---|---|
| 1 | **Paket-Hash-Abgleich** — identisches Paket zu diesem Lead bereits analysiert? | nein |
| 2 | **Klassifikation** — Dokumenttyp aus Dateiname (69 % Trefferquote), Rest über Inhaltsprobe | nur für den Rest |
| 3 | **Parser-Schiene** — GAEB, PDF-Formfelder, XLSX (§6.2) | nein |
| 4 | **Priorisierte Extraktion** — nur die für die Checkliste erforderlichen Dokumenttypen | ja |

**Priorisierung in Schritt 4** (Reihenfolge bindend):

| Priorität | Dokumenttyp | Liefert |
|---|---|---|
| 1 | Eignung, Bewerbungsbedingungen | K.-o.-Kriterien |
| 2 | Zuschlagskriterien | Gewichtung |
| 3 | Leistungsbeschreibung | Anforderungen, Umfang |
| 4 | Vertrag | Fallstricke, Bedingungen |
| 5 | Aufforderung | Fristen, Formalien |

Übrige Dokumenttypen (technische Anlagen, Datenschutzblätter, Bilder) gehen nicht in die Extraktion,
sondern erscheinen unter „Weitere Dokumente" (§7.5).

Erwartungswerte aus Q1a steuern die Vollständigkeitsprüfung: Fehlt ein Typ, der in 70–91 % der
Vorgänge auftritt, wird das in der Erkennungsansicht benannt (§4.3).

**Deckelung:** Übersteigt die Summe der priorisierten Dokumente 200.000 Tokens, wird nach Priorität
abgeschnitten. Der Nutzer sieht, welche Dokumente nicht analysiert wurden, und kann sie einzeln
nachfordern.

### 6.2 Parser-Schiene

| Format | Extrahiert |
|---|---|
| GAEB D81/D83/X83 | Positionen, Mengen, Einheiten, Kurz-/Langtexte |
| PDF mit Formfeldern | Feldnamen, Feldtypen, Pflichtkennzeichen |
| XLSX | Tabellenstruktur, Positionszahl, Gruppen — **keine Werte eintragen** |

Wo ein Parser greift, entfällt die LLM-Extraktion für dieses Dokument.

### 6.3 Kostenkontrolle

- Modellwahl je Schritt konfigurierbar. Für Schritt 4 (Extraktion aus juristischen Texten) ist die
  Modellgüte vor Produktivsetzung zu prüfen — siehe §16.2.
- **Maßgeblich ist das Tokenvolumen, nicht die Dateizahl.** Die priorisierten Typen enthalten gerade die
  umfangreichen Dokumente (Leistungsbeschreibung, Vertrag); Eigenerklärungen und Formblätter sind kurz.
  Der Ausschluss nicht priorisierter Typen senkt das Volumen daher moderat.
- **Der größte Einzelhebel ist die Parser-Schiene**, nicht die Dokumentauswahl: Im Bau (84 % GAEB, größtes
  Segment) ersetzt der GAEB-Parser das umfangreichste Dokument des Pakets vollständig.
- **Zu messen vor Produktivsetzung** (§16.6): tatsächliches Tokenvolumen der priorisierten Typen je
  Vorgang, aus den Rohdaten der Struktur-Studie. Bis dahin gilt der Medianwert des Gesamtpakets
  (61.000 Tokens) als obere Abschätzung.
- Token-Verbrauch je Analyse protokollieren (`doc_packages.token_cost`), Auswertung für die Justierung
  der Free-Grenze.

---

## 6a. Extraktionsqualität

Kein Fine-Tuning. Q1b belegt individuelle Wortlaute je Vergabestelle — es gibt kein wiederkehrendes
Textmuster, das antrainiert werden könnte. Die Qualität entsteht über Schema, Belegpflicht,
typspezifische Aufgaben und Messung.

### 6a.1 Strukturierte Ausgabe

Jede Extraktion liefert Objekte gegen ein festes Schema, keine Prosa. Antworten, die nicht gegen das
Schema validieren, werden verworfen und einmal wiederholt.

Mindestfelder je extrahierter Anforderung:

| Feld | Inhalt |
|---|---|
| `req_type` | Wert aus der Anforderungs-Taxonomie (§3) |
| `value` / `unit` | falls quantifiziert (z. B. 500000 / EUR) |
| `quote` | wörtliches Zitat aus dem Dokument |
| `source_file` / `source_page` | Fundstelle |
| `marking` | Zitat / Extrahiert / Abgeleitet (§7.2) |

### 6a.2 Belegpflicht und Zitatverifikation — Pflicht

Jede Aussage der Stufen *Zitat* und *Extrahiert* muss ein wörtliches Zitat mit Fundstelle tragen.

**Automatische Prüfung nach jeder Extraktion:** Das gelieferte Zitat wird im Quelldokument gesucht
(normalisiert auf Whitespace und Zeilenumbrüche).

| Ergebnis | Verhalten |
|---|---|
| Zitat gefunden | Eintrag wird übernommen |
| Zitat nicht gefunden | Eintrag wird **verworfen**, nicht angezeigt |
| Quote fehlt bei Stufe Zitat/Extrahiert | Eintrag wird verworfen |

Die Verwerfungsquote wird je Analyse protokolliert (`doc_packages.rejected_items`) und ist die
laufende Qualitätskennzahl.

### 6a.3 Typspezifische Extraktionsaufgaben

Keine Universalabfrage. Je Dokumenttyp aus der Priorisierung (§6.1) eine eigene Aufgabe mit eigenem
Schema und zwei bis drei Beispielen aus realen Unterlagen:

| Dokumenttyp | Extraktionsziel |
|---|---|
| Eignung, Bewerbungsbedingungen | K.-o.-Kriterien: Mindestumsatz, Referenzanzahl und -wert, Zertifikate, Ausschlussgründe |
| Zuschlagskriterien | Kriterien, Gewichte, Punktesysteme, Preis-/Qualitätsanteil |
| Leistungsbeschreibung | Leistungsumfang, Mengen, Fristen, technische Mindestanforderungen |
| Vertrag | Vertragsstrafen, Haftung, Laufzeit, Verlängerungsoptionen, Kündigungsrechte |
| Aufforderung | Fristen, Formalien, geforderte Anlagen |

Dokumenteninhalt wird strikt als Daten behandelt (§12.5).

### 6a.4 Bewertungsdatensatz

Grundlage jeder Modell- oder Prompt-Änderung. Ohne ihn ist keine Aussage über Verbesserung möglich.

**Teil 1 — automatisch prüfbar (kein Handaufwand):**
Für Angebotsfrist, Auftragswert, Vergabestelle und CPV liegt die Wahrheit in TED/DÖE vor. Diese Felder
werden über alle vorhandenen Vorgänge der Struktur-Studie automatisch gegengeprüft. Ergebnis: Trefferquote
je Feld. Derselbe Abgleich dient als Sabotageschutz (§12.2) — ein Mechanismus, zwei Zwecke.

**Teil 2 — manuell erhoben:**
Aus dem Bestand der Struktur-Studie werden **30 Vorgänge** ausgewählt (branchenverteilt: Bau, Beratung,
Medizin, IT). Je Vorgang wird einmalig festgehalten:
- alle K.-o.-Kriterien
- Zuschlagskriterien mit Gewichtung
- alle Fristen
- die geforderten einzureichenden Dokumente

**Messgrößen:** Vollständigkeit (gefundene / vorhandene Anforderungen), Korrektheit (richtig extrahierte
Werte), Halluzinationsrate (Einträge ohne verifizierbares Zitat).

**Anwendung:** Jede Änderung an Modell, Prompt oder Schema läuft gegen den Datensatz, bevor sie
produktiv geht. Verschlechterungen in Vollständigkeit oder Korrektheit blockieren die Änderung.

### 6a.5 Rückfluss aus dem Betrieb

Zwei Quellen liefern reale Fehlerfälle:

| Quelle | Verwendung |
|---|---|
| Nutzer-Einordnung unklassifizierter Dokumente (§7.5) | verbessert die Klassifikation (§6.1, Schritt 2) |
| Fehlermeldung zu Checklisteneinträgen (§12.2, Maßnahme 3) | Fälle werden gesammelt und in den Bewertungsdatensatz übernommen |

Gemeldete Fehler werden mit Dokumentstand und Paket-Hash gespeichert, damit sie reproduzierbar bleiben.

### 6a.6 Kein Fine-Tuning in V1

Fine-Tuning ist ausgeschlossen: kein wiederkehrendes Textmuster (Q1b), Bindung an ein Modell, und der
Qualitätsgewinn liegt nachweislich in Schema und Belegpflicht.

**Spätere Ausnahme (nicht V1):** Klassifikation der 31 % nicht per Dateiname erkennbaren Dokumente.
Enge Aufgabe, hohes Volumen. Vor einem Fine-Tuning sind Embeddings mit einfachem Klassifikator zu
prüfen — voraussichtlich günstiger und ausreichend.

---

## 7. Checkliste

### 7.1 Eintrag

```
┌─────────────────────────────────────────────────────────┐
│ Referenzen                                     ⓘ Zitat  │
├─────────────────────────────────────────────────────────┤
│ Aus den Unterlagen                                      │
│ „Mindestens drei vergleichbare Referenzen aus den       │
│  letzten fünf Jahren mit einem Volumen von je           │
│  mindestens 500.000 EUR."                               │
│  → Teil A Bewerbungsbedingungen, S. 7                   │
├─────────────────────────────────────────────────────────┤
│ Dein Textbaustein                        aus deinem     │
│ ┌─────────────────────────────────────┐  Profil         │
│ │ [editierbar]                        │                 │
│ └─────────────────────────────────────┘                 │
│                        [ Kopieren & speichern ]         │
└─────────────────────────────────────────────────────────┘
```

Pflichtbestandteile je Eintrag: Thema · Originalzitat mit Fundstelle (Datei + Seite) · editierbares
Textfeld · Kombi-Button (kopiert in Zwischenablage **und** speichert in Bibliothek).

### 7.2 Kennzeichnung

Eigene Klasse, getrennt von der Provenance-Grammatik (gemessen/geschätzt/unbekannt), die für TED-Daten gilt.

| Stufe | Anwendung |
|---|---|
| **Zitat** | wörtlich aus dem Dokument, mit Fundstelle |
| **Extrahiert** | vom LLM strukturiert, Zitat steht daneben |
| **Abgeleitet** | Einschätzung, nicht wörtlich im Dokument |
| **Vorschlag** | generierter Textbaustein |

Zusätzliche Markierung bei Bausteinen: `aus deinem Profil` oder `generisch`. Generische Bausteine
erhalten sichtbare Platzhalter (`[Projektname]`, `[Jahr]`) und einen Warnhinweis vor dem Kopieren.

### 7.3 Kopfbereich

Dauerhaft über der Checkliste:

```
Stand der Unterlagen: 15.07.2026 · 20 Dateien
Bitte regelmäßig prüfen, ob neue Unterlagen vorliegen. → Zum Vergabeportal ↗

LLM-gestützte Analyse — kann Fehler enthalten. Jede Angabe ist mit Fundstelle
im Originaldokument belegt; maßgeblich bleiben die Vergabeunterlagen.
```

### 7.4 Zuschlagskriterien nicht auffindbar

Bei Nicht-Fund (52 % der Fälle) eigener Eintrag, nie stilles Weglassen:

> **Zuschlagskriterien** — in den Unterlagen nicht eindeutig auffindbar. Bitte selbst prüfen.

### 7.5 Nicht klassifizierte Dokumente

Eigener neutraler Eintrag, keine Fehlermeldung:

```
Weitere Dokumente                                    3 Dateien
· Anlage B1 Bilder.pdf
· Informationsblatt_GAEB-Dateien.pdf
· Anlage B6 Katalog typischer Schlechtleistungen.pdf

[ Einordnen ]
```

Die Nutzer-Zuordnung verbessert die Dokumenttyp-Erkennung (§6.1, Schritt 2) und wirkt für alle Folgeanalysen.

### 7.6 Versionswarnung

Zwei Mechanismen:

1. **Passiv:** Dokumentenstand im Kopf (§7.3).
2. **Aktiv:** Bei erkannter Änderungsbekanntmachung (eForms `ProcurementDocumentsChangeIndicator`) für
   den Lead:

> ⚠ Die Vergabestelle hat die Unterlagen am 27.07. geändert. Deine Analyse beruht auf dem Stand
> vom 15.07. → Neue Unterlagen laden

---

## 8. Lose

**Regelfall:** Eine Checkliste je Lead. Los-benannte Dateien existieren nur in 8 % der Pakete; ohne
Los-Bezug im Dokument ist keine Zuordnung möglich, auch wenn die Losanzahl aus TED bekannt ist.

**Ausnahme:** Enthalten Dokumente einen erkennbaren Los-Bezug (Dateiname oder Inhalt), erhält die
Checkliste zusätzliche Los-Abschnitte mit ausschließlich den abweichenden Einträgen:

```
Für alle Lose
· Eignungsnachweise, Eigenerklärungen, Vertragsbedingungen …

Los 1 — Objektschutz
· abweichende Leistungsbeschreibung, eigenes Preisblatt

Los 2 — Pfortendienst
· …
```

**Pflichtausgabe bei Mehr-Los-Vergabe ohne erkennbare Trennung:**

> Die Anforderungen gelten, soweit erkennbar, für alle Lose.

---

## 9. Bausteinbibliothek

### 9.1 Ort und Eigentum

Bausteine gehören dem **Profil (Firma)**, nicht dem einzelnen Nutzer. Zwei Zugriffsorte:

- **Im Lead:** Bearbeitung im Checklistenkontext.
- **Unter Profil → Bausteine:** vollständige Bibliothek, nach Thema sortiert, auch **ohne vorherige
  Analyse befüllbar**.

Jeder Baustein zeigt `zuletzt bearbeitet von [Nutzer] am [Datum]`. Beim Überschreiben einer Fassung
eines anderen Nutzers erscheint ein Hinweis.

### 9.2 Mengenbegrenzung

Keine. Weder Free noch Pro.

Ordnungshilfen statt Limit: Kennzeichnung „länger nicht genutzt", „mehrfach in gewonnenen Angeboten
verwendet", **Archivieren statt Löschen**.

### 9.3 Zuordnung zu neuen Anforderungen

Rangfolge der Signale:

| Rang | Signal | Quelle |
|---|---|---|
| 1 | Verwendungshistorie | `profile_block_usage` — CPV, Region, Volumen, Vergabestelle des Leads |
| 2 | Thema | feste Taxonomie (§9.4) |
| 3 | Keywords | automatisch aus Inhalt abgeleitet, vom Nutzer korrigierbar |

Keywords werden **abgeleitet, nicht abgefragt**.

### 9.4 Themen-Taxonomie

Fest, nicht nutzererweiterbar:

`unternehmensdarstellung` · `referenzen` · `zertifikate_qm` · `datenschutz_avv` · `nachhaltigkeit` ·
`personal_qualifikation` · `technische_ausstattung` · `projektorganisation` · `sonstiges`

---

## 10. Import aus alten Angeboten

### 10.1 Ablauf

Unter Profil → Bausteine → Import. Der Nutzer lädt eigene frühere Angebote hoch. Das System extrahiert
wiederverwendbare Passagen und legt sie als Bausteine an.

### 10.2 Speicherung

| Element | Behandlung |
|---|---|
| Originaldokument | **wird nicht gespeichert** — Verarbeitung ausschließlich im Arbeitsspeicher, danach verworfen |
| Extrahierter Baustein | gespeichert, verschlüsselt (§12.3) |
| Quellenangabe | Metainformation: Dateiname, Datum, Herkunftsausschreibung, Abschnitt |

Hinweis an den Nutzer vor dem Import: Ohne gespeichertes Original kann später nicht nachgeschlagen
werden; zum Nachschärfen wird das eigene Dokument benötigt.

### 10.3 Personenbezogene Daten — Pflicht

Alte Angebote enthalten regelmäßig Personendaten (Projektleiter, Ansprechpartner beim Auftraggeber,
Personallisten, personengebundene Qualifikationen). Diese dürfen die Bibliothek nicht ungefiltert
erreichen — konsistent mit #11 §5.2 („Team, nicht Person; keine Namen, keine Lebensläufe").

**Umsetzung:**
1. Erkennung von Personennamen, E-Mail-Adressen, Telefonnummern und personengebundenen Qualifikationen
   im extrahierten Text.
2. Ersetzung durch Platzhalter (`[Projektleitung]`, `[Ansprechpartner]`) **vor** dem Speichern.
3. Der Nutzer sieht die Ersetzungen markiert und kann sie im Baustein überschreiben.
4. Passagen, die überwiegend aus Personendaten bestehen (z. B. Lebensläufe), werden nicht übernommen.

Hinweis beim Import: Personenbezogene Angaben werden automatisch durch Platzhalter ersetzt.

### 10.4 Herkunftskennzeichnung

Jeder importierte Baustein trägt den Ausgang des Verfahrens als **neutralen Fakt**:
`aus einem erfolgreichen Angebot` / `aus einem nicht erfolgreichen Angebot`.

**Keine Bewertung und keine Handlungsempfehlung** — Verluste erfolgen überwiegend über den Preis,
nicht über den Text.

Zählbares Positivsignal: `in N gewonnenen Angeboten verwendet`.

---

## 11. Ergebnisdaten aus Importen

Ein Import belegt: Das Profil war Bieter im Verfahren X. Der Gewinner von X ist aus TED bekannt.
Daraus ergibt sich die Verliererinformation, die keine öffentliche Quelle enthält (Lücke aus #11).

### 11.1 Zweckbindung — Pflicht

Der Upload erfolgt zum Zweck der eigenen Bibliothek. Die Auswertung für Wettbewerbsaggregate ist ein
**anderer Zweck** und erfordert eine **gesonderte, ausdrückliche Zustimmung**. Keine stillschweigende
Mitnutzung.

Formulierung bei der Abfrage:

> Sollen wir aus diesen Teilnahmen deine Wettbewerbsdaten ergänzen? Dann siehst du im Gegenzug, wie
> viele Bieter in deinen Feldern üblicherweise antreten. Wir zeigen niemandem, an welchen Verfahren
> du teilgenommen hast.

### 11.2 Verarbeitung

Bei Zustimmung wird ausschließlich das Tripel `profil × verfahren × teilgenommen` in `user_outcomes`
(#11) geschrieben — **nicht** der Angebotsinhalt, nicht der Preis.

### 11.3 Rückspiel — Leitplanken aus #11

| Regel | Umsetzung |
|---|---|
| Nur aggregiert | keine Anzeige „Firma X war Mitbieter" |
| Mindestzahl | Rückspiel erst ab der in #11 definierten Schwelle |
| Rückwärtsgerichtet | nur abgeschlossene Verfahren |
| Keine Preisinformation | Preise aus Angeboten werden nicht ausgewertet |

### 11.4 Widerruf

Die Zustimmung ist jederzeit widerrufbar. Bei Widerruf werden die aus Importen abgeleiteten
Teilnahmedatensätze des Profils gelöscht; bereits berechnete Aggregate werden bei der nächsten
Neuberechnung ohne sie gebildet.

---

## 12. Sicherheit

### 12.1 Ebenentrennung

Systemprozess für Ebene A ohne Datenbankrechte auf Ebene-B-Tabellen (§3).

### 12.2 Schutz der geteilten Checkliste

**Risiko:** Im selben Lead befinden sich konkurrierende Bieter. Eine manipulierte Checkliste (falsche
Frist, fehlende Pflichtanforderung) kann Wettbewerber schädigen.

**Maßnahme 1 — Plausibilitätsabgleich:** Angebotsfrist, Auftragswert, Vergabestelle und CPV aus dem
Dokument gegen TED/DÖE.

*Bekannte Grenze:* Nur ~65 % der Vergaben tragen einen echten Wert, die Bandtreffer­quote liegt bei
42 %; im Unterschwellenbereich sind Vergleichsfelder teils gar nicht vorhanden. Die **Angebotsfrist**
ist der stabilste Anker. Der Abgleich allein genügt nicht.

**Maßnahme 2 — Bestätigungsschwelle:** Eine Checkliste wird erst für andere Nutzer sichtbar, wenn
*eine* der Bedingungen erfüllt ist:
- ein zweiter, unabhängiger Upload desselben Leads erzeugt eine übereinstimmende Extraktion, **oder**
- der Plausibilitätsabgleich ist auf allen verfügbaren Feldern widerspruchsfrei **und** die
  Angebotsfrist stimmt exakt.

Bis dahin ist die Analyse nur für den hochladenden Nutzer sichtbar.

**Maßnahme 3 — Herkunft und Meldeweg:** Jede Checkliste trägt Paket-Hash und Dokumentstand. Nutzer
können Fehler melden. Versionswechsel (neuerer Dokumentstand) wird automatisch übernommen; inhaltlicher
Widerspruch bei gleichem Stand geht in manuelle Prüfung.

### 12.3 Vertraulichkeit Ebene B

| Mechanismus | Umsetzung |
|---|---|
| Envelope-Verschlüsselung | Datenschlüssel je Profil, geschützt über KMS; in der DB nur Chiffrat |
| Protokollierung | jede Entschlüsselung nachvollziehbar |
| Flüchtige Verarbeitung | importierte Angebote nie auf Platte |
| LLM-Anbieter | Zero-Retention, kein Training, AVV, EU-Verarbeitung |
| Mandantentrennung | RLS auf allen Ebene-B-Tabellen |

**Zu dokumentierende Grenze:** Vollständige Nullwissen-Verschlüsselung ist mit LLM-Extraktion nicht
vereinbar. Die Aussage nach außen lautet: verschlüsselt je Kunde, kein Zugriff ohne protokollierte
Schlüsselnutzung, keine Speicherung der Originale, keine Speicherung beim KI-Anbieter.

### 12.4 Zeitkanal

Die Existenz einer geteilten Checkliste verrät, dass ein Wettbewerber am Lead arbeitet.

**Maßnahme:** Die Antwortzeit bei vorhandener Checkliste wird auf die Mindestdauer einer Neuanalyse
angeglichen (Untergrenze konfigurierbar, Richtwert 8–12 Sekunden). Keine Statusmeldung, die auf
vorhandene Analysen schließen lässt.

### 12.5 Prompt Injection

Dokumenteninhalt wird als Daten behandelt: strukturierte Ausgabe gegen festes Schema, keine Tool- oder
Datenbankrechte im Extraktionsschritt, Validierung gegen erwartete Feldtypen und Wertebereiche.

### 12.6 Nebenläufige Uploads

Laden zwei Nutzer gleichzeitig dasselbe Lead-Paket hoch: Sperre auf `doc_packages` je
`(lead_id, package_hash)`. Der zweite Prozess wartet auf das Ergebnis des ersten, statt eine zweite
Analyse zu starten. Die Quote wird nur einmal verbraucht.

---

## 13. Datenmodell

| Tabelle | Ebene | Felder (Auszug) |
|---|---|---|
| `doc_requirement_types` | — | `req_type`, `label`, `theme` — semantische Taxonomie (§3), kein Textcache |
| `doc_packages` | A | `lead_id`, `package_hash`, `doc_state_date`, `file_count`, `token_cost`, `rejected_items`, `visibility`, `uploaded_by` |
| `doc_files` | A | `package_id`, `filename`, `doctype`, `hash`, `pages`, `parser_used` |
| `doc_checklists` | A | `lead_id`, `lot_id` (nullable), `package_id`, `status` |
| `doc_checklist_items` | A | `checklist_id`, `theme`, `quote`, `source_file`, `source_page`, `marking`, `lot_ref` |
| `profile_text_blocks` | B | `profile_id`, `theme`, `content_encrypted`, `keywords`, `origin`, `outcome`, `last_edited_by` |
| `profile_block_usage` | B | `block_id`, `lead_id`, `used_at` |

`doc_packages.visibility`: `private` (Standard) → `shared` nach Bestätigungsschwelle (§12.2).

**RLS:** Ebene B profilgebunden. Ebene A lesbar für alle authentifizierten Nutzer, schreibbar nur
durch Systemrolle.

**Originaldokumente werden nicht persistiert** — weder Lead-Unterlagen noch importierte Angebote.
Gespeichert werden Hashes, Metadaten und Extraktionsergebnisse.

---

## 14. Free/Pro

| | Free | Pro |
|---|---|---|
| Voll analysierbare Leads | 3 pro Monat | unbegrenzt |
| Bausteinbibliothek | unbegrenzt | unbegrenzt |
| Import alter Angebote | ja | ja |

Eine Beschäftigung mit einem Lead zählt als eine Analyse, unabhängig von Bewertungs- oder
Unterlagenanalyse.

---

## 15. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Drag-&-Drop akzeptiert ZIP, PDF, DOCX, XLSX, GAEB; Grenzwerte §4.2 greifen |
| 2 | Erkennungsansicht listet klassifizierte Dateien und benennt fehlende erwartete Typen |
| 3 | Sechs Prüfungen §5 laufen in Reihenfolge mit definiertem Verhalten |
| 4 | Quotenhinweis erscheint vor jedem Analysestart |
| 5 | Keine Meldung und keine Zeitdifferenz, die auf vorhandene geteilte Analysen schließen lässt |
| 6 | Checklisteneintrag enthält Thema, Zitat mit Datei und Seite, editierbares Feld, Kombi-Button |
| 7 | Vier Kennzeichnungsstufen; Bausteine zusätzlich `aus deinem Profil` / `generisch` |
| 8 | Dokumentenstand und Haftungshinweis dauerhaft sichtbar |
| 9 | Aktive Versionswarnung bei erkannter Änderungsbekanntmachung |
| 10 | Zuschlagskriterien bei Nicht-Fund als eigener Eintrag ausgewiesen |
| 11 | Nicht klassifizierte Dokumente als neutraler Eintrag mit Einordnungsmöglichkeit |
| 12 | Eine Checkliste je Lead; Los-Abschnitte nur bei erkennbarem Los-Bezug; Pflichthinweis sonst |
| 13 | Verarbeitung nach §6.1; Parser für GAEB, PDF-Formfelder, XLSX ersetzen LLM-Extraktion |
| 14 | Priorisierte Extraktion; Deckelung bei >200k Tokens schneidet nach Priorität ab und weist es aus |
| 15 | Bausteine profilgebunden, unbegrenzt, ohne Analyse anlegbar, mit Bearbeitungszuschreibung |
| 16 | Import speichert keine Originaldokumente; Quellenangabe als Metadaten vorhanden |
| 17 | Personenbezogene Daten werden vor dem Speichern durch Platzhalter ersetzt; Ersetzungen sichtbar |
| 18 | Verfahrensausgang neutral gekennzeichnet, ohne Handlungsempfehlung |
| 19 | Ergebnisdaten aus Importen nur nach gesonderter Zustimmung; Widerruf möglich |
| 20 | Checkliste wird erst nach Bestätigungsschwelle für andere sichtbar |
| 21 | Ebene-A-Prozess besitzt keine Rechte auf Ebene-B-Tabellen |
| 22 | Nebenläufige Uploads erzeugen keine Doppelanalyse |
| 23 | Das System füllt keine Dokumente aus |
| 24 | Extraktion liefert ausschließlich schemavalide Objekte; ungültige Antworten werden verworfen |
| 25 | Zitatverifikation gegen das Quelldokument; nicht auffindbare Zitate führen zum Verwerfen des Eintrags |
| 26 | Verwerfungsquote je Analyse protokolliert |
| 27 | Eigene Extraktionsaufgabe je Dokumenttyp der Priorisierung |
| 28 | Bewertungsdatensatz (automatischer Teil + 30 manuell erhobene Vorgänge) vorhanden; Änderungen laufen dagegen |

---

## 16. Offene Punkte

| # | Punkt | Zu klären durch |
|---|---|---|
| 1 | Rechtliche Bestätigung der nutzerübergreifenden Wiederverwendung (Ebene A) | anwaltliche Prüfung vor größerem Ausbau |
| 2 | Modellwahl für die Extraktion | Vergleich am Bewertungsdatensatz (§6a.4). Die Kostenangabe der Studie (~2 ct Median) gilt für das günstige Modell und trägt nicht automatisch für die Extraktion juristischer Texte |
| 3 | Free-Grenze | nach Auswertung realer `token_cost`-Werte justieren |
| 4 | Q4-Vorbehalt: 52 % „Zuschlagskriterien nicht gefunden" sind teils Erkennungsgrenze der Keyword-Suche | mit der LLM-Extraktion gegenprüfen, Anteil neu messen |
| 5 | Dokumentbasierter Ausschreibungscheck (Vergabestellen-Seite) | eigenes Ticket |
| 6 | Tokenvolumen der priorisierten Dokumenttypen je Vorgang | aus `data/docs/study/*.csv` auswerten: Zeichen je Datei nach Doctype summieren, Anteil der priorisierten Typen am Gesamtvolumen bestimmen — je Branche, da GAEB den Bau stark verschiebt |
