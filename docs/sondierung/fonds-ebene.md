# Sondierung: die dritte Ebene — Fonds-Vergaben

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.** Nachgearbeitet, nachdem die zwölf Länderkapitel nur **zwei** von drei
Ebenen abgedeckt hatten.

---

## 1. Warum es diese Ebene gibt

`CLAUDE.md` verlangt bei jedem Land drei Ebenen:

1. **oberschwellig** — TED, überall gleich
2. **unterschwellig** — nationale Pflichtveröffentlichung
3. **Fonds-Ebene** — Vergaben von **Empfängern öffentlicher Fördermittel, die selbst keine
   öffentlichen Auftraggeber sind**

Die dritte ist die unsichtbarste: Ein Hotelbetrieb, der EU-Fördermittel bekommt, muss den
Auftrag ausschreiben — er steht aber in keinem Vergaberegister, weil er kein öffentlicher
Auftraggeber ist. **Die Wettbewerbspflicht gilt EU-weit, die Sichtbarkeit ist rein national.**

⚠ Und sie wird regelmäßig übersehen, weil sie in DACH fast leer ist. Genau das ist mir in
allen zwölf Kapiteln passiert.

**Für DACH bereits geprüft (2026-08-18):** kein eigenes Verzeichnis.

## 2. ✅ Tschechien — gefunden, öffentlich, maschinenlesbar

`zakazky.agentura-api.org`, betrieben von der Agentur für Unternehmen und Innovationen.
Fördermittelempfänger der Programme **OPPIK, OPTAK und NPO** müssen ihre Ausschreibungen
dort veröffentlichen.

| | |
|---|---:|
| Vergaben im Register | **8.663** |
| robots.txt | keine (404) |
| Export durch den Betreiber angeboten | **Excel, PDF** |

**Öffentlich abrufbar, ohne Anmeldung:**
```
POST /nacist_verejny        (DataTables-Parameter)
    → 200, JSON: recordsTotal 8.663
```

Je Zeile: Auftraggeber, **IČ** (tschechische Firmenkennung), Titel, Art, Beschreibung,
Angebotsfrist, Veröffentlichungsdatum, **geschätzter Wert**, Status.

Beispiel aus dem ersten Datensatz: *Hoteliéři Krkonoše servisní s.r.o.*, „Vytvoření
platformy iPec", Frist 5.10.2026, **43.986.500 CZK**, aktiv.

⚠ **Das ist ein privates Unternehmen mit einer 44-Millionen-Ausschreibung** — und es steht
in keinem der Portale, die ich in zwölf Kapiteln vermessen habe. Zum Vergleich: Tschechien
hatte im Juni **1.621** TED-Ausschreibungen. Dieses eine Register führt 8.663 Einträge
(kumuliert, nicht monatlich — aber die Größenordnung sagt genug).

⚠ **Offen:** ob dort auch die Vergabeunterlagen hängen. Die Detailspalte („Zobrazit") ist
kein gewöhnlicher Link; das ist nicht geprüft.

## 3. 🟡 Polen — Portal bekannt, Schnittstelle verschlossen

`bazakonkurencyjnosci.funduszeeuropejskie.gov.pl` (Baza Konkurencyjności), in `CLAUDE.md`
namentlich genannt.

- **keine robots-Sperre** (die robots.txt liefert die Anwendungshülle)
- die API-Basis ist `/api/` (belegt: `/api/cookies`, `/api/statements`, `/api/general-content`
  antworten mit 200)
- **`/api/announcements` antwortet anonym mit HTTP 401**

Ob die öffentliche Weboberfläche ohne Anmeldung Ausschreibungen zeigt, ist offen — der erste
Seitenaufruf endete an einem Cookie-Banner.

## 4. ⚪ Die übrigen zehn Länder

**Nicht recherchiert.** Für FR, ES, IT, BE, NL, SE, LT, LV, EE ist nicht einmal geklärt, ob
ein zentrales Fonds-Register existiert.

Zwei Hinweise zur Priorisierung, wenn das jemand aufnimmt:

- **Je mehr Kohäsionsmittel ein Land bekommt, desto größer diese Ebene.** Unter den
  sondierten Ländern sind das PL, CZ und die drei baltischen Staaten — dieselben, die auch
  sonst die besten Verhältnisse zeigen.
- **Der tschechische Fall zeigt die Bauart:** nicht ein nationales Register, sondern eines
  **je Förderprogramm-Träger**. `agentura-api.org` deckt OPPIK/OPTAK/NPO ab; andere
  Operationelle Programme können eigene Portale haben. Wer „das eine Portal je Land" sucht,
  findet womöglich nur eines von mehreren.

## 5. Was diese Ebene wert wäre

Sie ist die einzige der drei, in der die **Auftraggeber private Unternehmen** sind. Für ein
Produkt, das Bietern Aufträge zeigt, heißt das:

- andere Auftraggeber (kein Amt, sondern ein Hotel, ein Hersteller, ein Verein)
- oft **kleinere Volumina**, aber mit klarer Frist und beziffertem Wert
- **kein Wettbewerber sammelt sie**, weil sie nicht in TED stehen und die Portale je Land
  und teils je Programm verschieden sind

Der tschechische Fund ist der Beleg, dass es geht: ein öffentlicher Endpunkt, keine
robots-Sperre, ein vom Betreiber selbst angebotener Export.
