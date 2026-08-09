# Feature #27: Eignungsprofil

**Produkt:** goVisor
**Version:** 2.0
**Status:** Bau-Spezifikation
**Erstellt:** 2026-07-30
**Abhängigkeiten:** #2 (Personal-Fit), #14 (Entity-Härtung), #15 (Anforderungen), #23 (Bausteinbibliothek), #26 (Handlungsempfehlung)
**Abgegrenzt:** Auswertungen auf dem Profil (Bilanz, Chancen) → **#28**

---

## 1. Warum eigener Hauptbereich

Das Profil ist **keine Kontoverwaltung**, sondern die Voraussetzung dafür, dass das Produkt
funktioniert. Ohne es gibt es keinen Anforderungsabgleich, keine Handlungsempfehlung, keine passenden
Textbausteine und keine belastbare Relevanz.

**Konsequenz:** eigener Eintrag in der Hauptnavigation, benannt **„Unser Unternehmen"** — nicht
„Profil" (klingt nach Konto).

| Gehört hinein | Bleibt in den Einstellungen |
|---|---|
| Stammdaten, Eignungsangaben, Referenzen, Zertifikate | Zugangsdaten, Passwort |
| Ausschlusskriterien, Zielrichtung, Ansprechpartner | Benachrichtigungen |
| Bausteinbibliothek (#23) | Abrechnung, Stufe |
| Entity-Zuordnung | |

---

## 2. Ein Objekt, nicht drei

Dieselbe Substanz wird an drei Stellen gebraucht: Anforderungsabgleich (#15/#26), Textbausteine (#23),
Relevanz (#2). **Mehrfach gepflegt heißt mehrfach veraltet.**

| Element | Verwendet für |
|---|---|
| Referenz (Projekt, Auftraggeber, Wert, Zeitraum, CPV) | Anforderungsprüfung · Textbaustein „Referenzen" · Relevanz |
| Zertifikat (Typ, Nummer, Gültigkeit) | K.-o.-Prüfung · Textbaustein „Zertifikate & QM" |
| Umsatz, Mitarbeiterzahl | Schwellenprüfung · KMU-Status · Textbaustein „Unternehmensdarstellung" |
| CPV-Schwerpunkte, Regionen | Relevanz · Anforderungskatalog · Zielrichtung |

**Regel:** Ein Datenpunkt wird **einmal** erfasst und überall verwendet. Eine Referenz im Profil
speist den Referenz-Textbaustein automatisch — keine zweite Eingabe.

---

## 3. Stammdaten

| Feld | Erfassung | Wofür |
|---|---|---|
| Firmenname, Anschrift | vorbefüllt aus `entity_identity` | Identität, Textbausteine |
| **Rechtsform** | Auswahl | Formulare, Eigenerklärungen |
| Umsatz (letzte 3 Geschäftsjahre) | Eingabe | Schwellenprüfung, KMU-Status |
| Mitarbeiterzahl | Eingabe | Schwellenprüfung, KMU-Status |
| **KMU-Status** | **berechnet**, nicht abgefragt | Verfahren mit Mittelstandsbezug |
| Gründungsjahr | Eingabe | „Jahre am Markt" als Anforderung |
| Sprache | Auswahl, Standard Deutsch | Textbausteine, europäische Skalierung |

**KMU-Status wird aus Umsatz und Mitarbeiterzahl abgeleitet** (EU-Definition), nie separat abgefragt —
zwei Wahrheiten würden auseinanderlaufen. Das Ergebnis ist sichtbar und erklärt („KMU: ja — unter
250 Beschäftigten und 50 Mio € Umsatz").

**Mehrsprachigkeit:** In V1 nur Deutsch. Das Datenmodell hält Sprachfelder aber offen, damit die
europäische Ausweitung später keinen Umbau erfordert.

---

## 4. Ansprechpartner

Wer im Unternehmen Vergaben bearbeitet. Nicht Kosmetik, sondern Adressat der Alerts — bei einem
Bid-Team entscheidet das über Nützlichkeit oder Rauschen.

| Feld | Zweck |
|---|---|
| Rolle im Vergabeprozess (Bid-Manager, Vertrieb, Geschäftsführung) | Alert-Verteilung (#9) |
| Zuständige Segmente/Regionen | Alerts nur für den eigenen Bereich |

**Nur nutzerbezogen, keine Personenverwaltung.** Jeder Teamnutzer pflegt seine eigene Rolle. Keine
Erfassung Dritter — konsistent mit dem Grundsatz, personenbezogene Daten außen vor zu lassen (#11).

---

## 5. Der Anforderungskatalog

### 5.1 Vollständigkeitsbegriff

Vollständig heißt: Zu **jedem branchenüblichen Anforderungstyp** liegt eine Angabe vor — ja, nein oder
ein Wert. Ein ausdrückliches „trifft nicht zu" ist genauso verwertbar wie ein Nachweis; bei
K.-o.-Kriterien sogar wertvoller, weil es ein Abraten ermöglicht (#26 §3.3, B1).

Kein globaler Prozentsatz über alle denkbaren Anforderungen. Je Segment schätzungsweise 20–30 Punkte.

### 5.2 Herkunft — mit Kaltstart ⚠

**Nicht aus TED-Metadaten ableitbar.** Die Struktur-Studie zeigt: Zuschlagskriterien zu 24 % als
eigenes Dokument, 52 % nicht per Keyword auffindbar; benannte Zertifikate zu 0,1–0,4 % in den
Metadaten. Der Katalog entsteht **nur aus analysierten Vergabeunterlagen** — die es zu Beginn nicht gibt.

| Stufe | Inhalt |
|---|---|
| **Startkatalog** (manuell, je Branche) | Ausschlussgründe §§ 123/124 GWB · Russland-Sanktionen Art. 5k · Tariftreue · Mindestumsatz · Referenzanzahl und -wert · Berufshaftpflicht mit Deckungssumme · **Präqualifikation** · branchenübliche Zertifikate (ISO 9001, 27001, 14001, SCC) · Mitarbeiterzahl · Jahre am Markt · **Verbandsmitgliedschaften** |
| **Wachstum aus dem Korpus** | Jede analysierte Ausschreibung meldet ihre Anforderungstypen. Typen ab 10 % Auftreten in einem Segment wandern in dessen Katalog |

Erste Fassung des Startkatalogs aus den vorliegenden Unterlagen-Sets ableiten.

### 5.3 Anforderungstypen

| Typ | Erfassung | Beispiele |
|---|---|---|
| **Binär** | ja / nein / unbeantwortet | Zertifikat, Präqualifikation, Eigenerklärung |
| **Schwellenwert** | Zahl + Einheit | Mindestumsatz, Mitarbeiterzahl, Deckungssumme |
| **Sammlung** | Liste mit Attributen | Referenzen |
| **Kennung** | Text | Präqualifikationsnummer, Zertifikatsnummer, Registernummer |

Die Unterscheidung ist bindend, weil #26 §3.2a Verhältnisse rechnet — das geht nur numerisch.

---

## 6. Branchenzuordnung, Zielrichtung, Ausschlüsse

### 6.1 Branchenzuordnung

Vorschlag aus der eigenen Zuschlagshistorie (CPV-Schwerpunkt), **änderbar**.

### 6.2 Zielrichtung

Das Profil beschreibt sonst nur den Ist-Zustand. Wer expandiert, braucht andere Leads als wer verteidigt.

| Zielrichtung | Wirkung auf Relevanz (#2) und Empfehlung (#26) |
|---|---|
| **Bestand halten** | Gewichtung auf bekannte Vergabestellen und bisherige CPV-Felder; Auslauf-Radar priorisiert |
| **Ausgewogen** (Standard) | keine Verschiebung |
| **Expandieren** | zusätzliche CPV-Felder und Regionen werden aufgenommen, auch ohne Zuschläge dort — deren Anforderungskatalog gilt zusätzlich |

### 6.3 Ausschlusskriterien

Was bewusst **nicht** in Frage kommt. Wenige Fragen, große Wirkung auf die Listenqualität.

| Ausschluss | Wirkung |
|---|---|
| Mindest-/Höchstauftragswert | Leads außerhalb fallen aus der Relevanz |
| Ausgeschlossene Regionen | trotz CPV-Treffer keine Empfehlung |
| Ausgeschlossene Leistungsarten | einzelne CPV-Zweige abwählbar |
| Keine Bietergemeinschaften | unterdrückt den Partner-Zusatz (#26 §3.4) |

Gehört ins Onboarding.

---

## 7. Erfassung

### 7.1 Drei Wege, kein leeres Formular

| Weg | Inhalt |
|---|---|
| **Vorbefüllung** | Referenzen aus eigenen Zuschlägen (Projekt, Auftraggeber, Wert, Zeitraum, CPV) · Regionen · CPV-Schwerpunkte · Umsatz näherungsweise aus Auftragsvolumen |
| **Profil-Band** (#26 §4.3) | bis zu 5 Fragen aus den aktuell angezeigten Leads, direkt beantwortbar |
| **Anforderungs-Check** | unbeantwortete Anforderung wird dort erfragt — eine Frage, zehn Sekunden |

Vorbefüllte Angaben sind als **abgeleitet** markiert und zählen bis zur Bestätigung als
„unbeantwortet" für die 60-%-Schwelle (#26 §3.9) — sonst empfiehlt goVisor auf ungeprüften Annahmen.

### 7.2 Erstkontakt — zwei Einstiegswege, ein Ziel

| Herkunft | Ausgangslage |
|---|---|
| **über Token-Seite** | Entity bereits zugeordnet, Verträge und Referenzen vorbefüllt |
| **normale Registrierung** | Entity muss zugeordnet werden |

Beide laufen nach der Zuordnung im **gleichen Zustand** zusammen: vorbefülltes Profil, Profil-Band mit
den ersten fünf Fragen. Kein zweites Einstiegserlebnis.

Bei normaler Registrierung ist die Entity-Zuordnung der erste Schritt — sie ist Voraussetzung für
jede Vorbefüllung.

### 7.3 Entity-Korrektur

Ist die Firma falsch zugeordnet (falsche Gesellschaft, verwechselter Name, fehlende Tochter), zeigt
die Vorbefüllung fremde Verträge. Das muss korrigierbar sein.

| Element | Verhalten |
|---|---|
| Anzeige | Zuordnungsgüte sichtbar (`entity_confidence`), wie in #25 |
| Korrektur | Auswahl aus Kandidaten, Zusammenführen mehrerer Gesellschaften, Abwählen falscher Treffer |
| Wirkung | Vorbefüllung wird neu berechnet; bestätigte Angaben bleiben erhalten |
| Rückfluss | Korrektur härtet den Entity-Graph (#14) — wirkt für alle |

### 7.4 Wirkung sichtbar machen

> 4 Angaben fehlen · dadurch sind 7 aktuelle Leads nicht abschließend bewertbar
> · 2 Zertifikate laufen in den nächsten 90 Tagen ab

Ohne diesen Bezug fühlt sich Pflege wie Verwaltung an statt wie ein Hebel.

---

## 8. Belegte gegen angegebene Werte

Alle Angaben sind Selbstauskunft. Wer „ISO 27001: ja" anklickt, obwohl das Zertifikat abgelaufen ist,
führt die Empfehlung in die Irre.

| Zustand | Bedeutung | Wirkung |
|---|---|---|
| **angegeben** | Standard | volle Verwendung |
| **belegt** | Nachweis hinterlegt | als belegt gekennzeichnet; Ablaufdatum übernehmbar |
| **abgeleitet** | aus öffentlichen Daten vorbefüllt | zählt erst nach Bestätigung |

**Nachweis-Upload ist optional**, nicht Pflicht — eine Pflicht würde die Erfassung abwürgen. Anreiz:
Zertifikatsnummer und Gültigkeit werden ausgelesen, die Ablauferinnerung entsteht automatisch, der
Textbaustein kann die Nummer zitieren.

**Speicherung** wie #23 §12.3: verschlüsselt, profilgebunden, nie in geteilten Ebenen.

---

## 9. Aktualität

| Element | Regel |
|---|---|
| Zertifikate | Ablaufdatum pflichtig bei „ja"; Erinnerung 90 Tage vorher |
| Abgelaufenes Zertifikat | zählt **nicht** als erfüllt; betroffene Empfehlungen werden neu berechnet (#26 §3.10) |
| Referenzen | Datum pflichtig; Zeitfenster-Anforderungen prüfen es automatisch |
| Umsatz, Mitarbeiterzahl | jährliche Erinnerung, mit Erfassungsdatum |
| Alle Angaben | Änderungszeitpunkt gespeichert |

### 9.1 „Stimmt so" — Bestätigung ohne Neueingabe

Viele Angaben ändern sich jahrelang nicht. Wenn die jährliche Erinnerung eine vollständige Neueingabe
verlangt, wird sie ignoriert — und goVisor empfiehlt auf altem Stand.

**Regel:** Jede Erinnerung bietet eine Sammelbestätigung an: „Diese 6 Angaben sind unverändert" —
ein Klick, alle Erfassungsdaten werden aktualisiert. Einzelne Angaben lassen sich vorher korrigieren.

Ausgenommen: Zertifikate mit abgelaufenem Datum. Die brauchen ein neues Gültigkeitsdatum, keine
Bestätigung.

### 9.2 Historie

Jede Angabe wird mit Gültigkeitszeitraum geführt. Nötig, weil Anforderungen mit Zeitfenster
(„Umsatz der letzten drei Geschäftsjahre") wissen müssen, was wann galt — und weil Widersprüche zu
Empfehlungen (#26 §4.4) sonst nicht nachvollziehbar sind.

---

## 10. Team

Das Profil gehört dem **Unternehmen**, nicht der Person. Eine Änderung kann Empfehlungen für alle kippen.

| Anforderung | Umsetzung |
|---|---|
| Zuschreibung | „zuletzt geändert von M. Kessler am 12.07.2026" je Angabe |
| Warnung beim Überschreiben | Hinweis, wenn die vorherige Angabe von jemand anderem stammt |
| Änderungsprotokoll | einsehbar |
| Keine Rechteverwaltung in V1 | jeder darf ändern — Transparenz statt Sperren |

---

## 11. Export und Löschung

### 11.1 Export

JSON und PDF. Zwei Gründe: **Vertrauen** — wer Daten mitnehmen kann, gibt sie leichter her. Und
**Nutzen** — das PDF ist eine Eignungsübersicht, die bei Bewerbungen gebraucht wird.

Umfasst Angaben, Referenzen, Zertifikate mit Gültigkeit, Ausschlusskriterien. **Nicht** die
Textbausteine (eigener Export in #23) und **nicht** hochgeladene Nachweisdokumente.

### 11.2 Löschung

| Element | Verhalten bei Kontolöschung |
|---|---|
| Profilangaben, Referenzen, Zertifikate | vollständig gelöscht |
| Hochgeladene Nachweise | vollständig gelöscht |
| Textbausteine (#23) | vollständig gelöscht |
| Gemeldete Ergebnisdaten (#11) | siehe #11 §11.4 — auf Widerruf gelöscht, Aggregate ohne sie neu berechnet |
| Beiträge zum Entity-Graph und Dokumentkorpus | bleiben — sie sind sachbezogen und nicht personenbezogen |

Das Löschverhalten wird **vor** der Erfassung kommuniziert, nicht in den AGB versteckt. Vor
Produktivsetzung anwaltlich prüfen (Löschkonzept, Aufbewahrungspflichten bei Rechnungsdaten).

---

## 12. Was nicht ins Profil gehört

| Nicht | Grund |
|---|---|
| **Logo** | goVisor generiert keine Dokumente, in denen es auftauchen würde. Erst relevant, wenn Angebotsvorlagen exportiert werden |
| **Kapazität / Auslastung** | goVisor maßt sich keine Ressourcenentscheidung an (#26). Als reine Anzeige gehört sie ins Cockpit, nicht ins Eignungsprofil |
| **Bonitätsdaten** | Zukauf, kein Nutzen für die Empfehlung |
| **Mitarbeiterprofile, Lebensläufe** | personenbezogen — konsistent mit #11 und #23 §10.3 |
| **Umsatzentwicklung als Selbstauskunft über viele Jahre** | Pflegeaufwand ohne Nutzen; die letzten 3 Geschäftsjahre genügen. Die Entwicklung des *öffentlichen* Auftragsvolumens berechnet goVisor selbst (#28) |

---

## 13. Gate

| Element | Free | + | ++ |
|---|:---:|:---:|:---:|
| Profil anlegen und pflegen | ○ | ○ | ○ |
| Vorbefüllung, Entity-Korrektur | ○ | ○ | ○ |
| Ausschlusskriterien, Zielrichtung | ○ | ○ | ○ |
| Nachweis-Upload | ○ | ○ | ○ |
| Ablauferinnerungen | — | ○ | ○ |
| Änderungsprotokoll | — | ○ | ○ |
| Export | — | ○ | ○ |

**Das Profil selbst ist frei.** Es ist Voraussetzung für alles andere und liefert goVisor Daten — eine
Bezahlschranke davor wäre gegen das eigene Interesse.

---

## 14. Datenmodell

| Tabelle | Inhalt |
|---|---|
| `profile_company` | Stammdaten, Rechtsform, Kennzahlen, Sprache, Branchenzuordnung, Zielrichtung, `entity_id` |
| `profile_attributes` | je Anforderungstyp: Wert, Typ, Zustand (angegeben/belegt/abgeleitet), Gültigkeit, geändert von/am |
| `profile_references` | Projekt, Auftraggeber, Wert, Zeitraum, CPV, Quelle |
| `profile_certificates` | Typ, Nummer, Aussteller, gültig bis, Nachweis-Referenz |
| `profile_exclusions` | Wertgrenzen, Regionen, CPV, Bietergemeinschaft |
| `profile_roles` | je Nutzer: Rolle im Vergabeprozess, zuständige Segmente/Regionen |
| `profile_attribute_history` | Änderungshistorie mit Gültigkeitszeitraum |
| `catalog_requirement_types` | Anforderungskatalog je Segment |

Alle profilgebunden mit RLS. Nachweisdokumente verschlüsselt wie #23 §12.3. Sprachfelder vorgesehen,
in V1 nur Deutsch belegt.

---

## 15. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Eigener Eintrag in der Hauptnavigation, benannt „Unser Unternehmen" |
| 2 | Bausteinbibliothek (#23) ist Teil dieses Bereichs |
| 3 | Ein Datenpunkt wird einmal erfasst und überall verwendet |
| 4 | KMU-Status berechnet, nicht abgefragt |
| 5 | Sprachfelder im Datenmodell vorgesehen |
| 6 | Ansprechpartner-Rolle je Nutzer, keine Erfassung Dritter |
| 7 | Katalog branchenbezogen; Startkatalog manuell, Wachstum ab 10 % Auftreten |
| 8 | Vier Anforderungstypen: binär, Schwellenwert, Sammlung, Kennung |
| 9 | Branchenzuordnung vorgeschlagen und änderbar |
| 10 | Zielrichtung wirkt auf Relevanz und Empfehlung |
| 11 | Ausschlusskriterien wirken auf die Listenqualität |
| 12 | Erfassung über drei Wege, kein leeres Formular |
| 13 | Beide Registrierungswege laufen im gleichen Zustand zusammen |
| 14 | Entity-Korrektur möglich, Rückfluss in den Entity-Graph |
| 15 | Abgeleitete Angaben zählen erst nach Bestätigung |
| 16 | Drei Zustände sichtbar unterschieden |
| 17 | Nachweis-Upload optional; Ablaufdatum übernehmbar |
| 18 | Abgelaufene Zertifikate zählen nicht als erfüllt |
| 19 | „Stimmt so"-Sammelbestätigung bei Erinnerungen |
| 20 | Historie mit Gültigkeitszeitraum je Angabe |
| 21 | Zuschreibung und Änderungsprotokoll bei Teamnutzung |
| 22 | Wirkung sichtbar („N Leads nicht bewertbar") |
| 23 | Export als JSON und PDF |
| 24 | Löschverhalten definiert und vorab kommuniziert |
| 25 | Profilpflege in allen Stufen kostenlos |
| 26 | Schnittstelle zu #26 §6 vollständig bedient |

---

## 16. Offene Punkte

| # | Punkt | Zu klären |
|---|---|---|
| 1 | Startkatalog je Branche | erste Fassung aus den vorliegenden Unterlagen-Sets |
| 2 | 10-%-Schwelle für Korpus-Wachstum | an realen Verteilungen prüfen |
| 3 | Zertifikatserkennung aus Nachweisdokumenten | Aufwand gegen Nutzen; manuelle Eingabe ist Rückfall |
| 4 | Rechteverwaltung im Team | in V1 weggelassen; prüfen bei größeren Bid-Teams |
| 5 | **Eignungsleihe / Nachunternehmer** | Kann eine Anforderung über Dritte erfüllt werden? Berührt #26 B1 und den Partner-Zusatz unmittelbar |
| 6 | Löschkonzept | anwaltlich prüfen, inkl. Aufbewahrungspflichten |
