# Sondierung Griechenland

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Kein Connector, keine Tabelle, kein Kapitel in
> `docs/laender/`.

**Stand 2026-09-03.**

---

## 1. Ein Land, ein System — und trotzdem kein einfacher Fall

Alle grossen Namen gehören zu **ΕΣΗΔΗΣ/Promitheus**, betrieben vom Ministerium für digitale
Verwaltung. Zusammen **89,3 %** des Unterlagen-Felds (112 Domains, 3.724 Nennungen).

Diese Zahl ist aber irreführend, und das ist der wichtigste Befund des Kapitels.

## 2. ⚠ 43 % der Links nennen gar kein Verfahren

Gemessen über vier Monate an **1.861 echten GR-Ausschreibungen**, je Host getrennt nach
„tief" (der Pfad trägt eine Kennung) und „Startseite":

| Host | tief | Startseite | Anteil tief |
|---|---:|---:|---:|
| `nepps-search.eprocurement.gov.gr` | 393 | 12 | **97 %** |
| `portal.eprocurement.gov.gr` | 263 | 145 | 64 % |
| `pwgopendata.eprocurement.gov.gr` | 19 | 1 | **95 %** |
| `neppssearch…` (ohne Bindestrich) | 14 | 0 | 100 % |
| `nepps.eprocurement.gov.gr` | 2 | 163 | **1 %** |
| `promitheus.gov.gr` | 0 | 97 | **0 %** |
| `marketsite.gr` | 0 | 28 | **0 %** |

**725 tief, 538 Startseite — 43 % der griechischen Unterlagen-Links führen auf eine
Startseite.** Einer zeigte sogar auf `/webcenter/portal/**TestPortal**`.

⚠ Wer die Domain-Anteile aus der Tiefensondierung für Abdeckung hält, überschätzt
Griechenland um fast das Doppelte. Die Domain sagt, **wer** verlinkt; sie sagt nicht, **ob
etwas dahinter steht**. Diese Prüfung fehlt in allen bisherigen Länderkapiteln und gehört
nachgezogen.

## 3. ⚠ Ein Länderfilter, der leckte — und was er beinahe angerichtet hätte

Der erste Durchlauf dieser Messung zeigte `viesiejipirkimai.lt` (2.844) und
`etenders.gov.ie` (2.130) in einer angeblich **griechischen** Auswertung. Ursache: ich hatte
auf „enthält irgendwo `GRC`" geprüft statt auf „das **erste** Ländermerkmal ist `GRC`" — und
Griechenland taucht in fremden Bekanntmachungen als Herkunfts- oder Zulassungsland auf.

Die Zahlen darunter waren wertlos. Mit der Regel aus `sondiere_tief.py` (erstes Vorkommen
zählt) blieben **1.861** statt eines aufgeblähten Gemischs.

**Die Lehre:** ein Länderfilter, der „irgendwo" prüft, fällt nicht auf — er liefert einfach
zu viel, und zu viel sieht aus wie ein guter Ertrag.

## 4. 🟡 ΕΣΗΔΗΣ — Dokumente öffentlich sichtbar, Abruf braucht eine Sitzung

`nepps-search.eprocurement.gov.gr` (32,2 %, davon 97 % tief) ist der eine Host, der zählt.
**Keine robots.txt (404).** Die Adresse steht in TED:
`/actSearch/resources/search/469002`.

Ohne Anmeldung sichtbar, vollständig:

```
Titel:        Προμήθεια σάκων απορριμμάτων        (Beschaffung von Abfallsäcken)
Auftraggeber: ΔΗΜΟΣ ΠΕΡΙΣΤΕΡΙΟΥ                    (Gemeinde Peristeri)
CPV:          18930000-7, 19640000-4
Haushalt:     72.034,00 € ohne MwSt
Frist:        29/6/2026
```

Und ein zweiter Reiter **Συννημένα Αρχεία** („angehängte Dateien") listet fünf Dokumente:

```
ΔΙΑΚΗΡΥΞΗ 9Μ3ΘΩΞ2-8Λ9.pdf          ← die Ausschreibungsurkunde
ΠΕΡΙΛΗΨΗ ΔΙΑΚΗΡΥΞΗΣ 9Α10ΩΞ2-Φ3Υ.pdf
ΠΡΟΚΗΡΥΞΗ ΑΔΑΜ.pdf
espd-request_signed.pdf  ·  espd-request.xml    ← die ESPD in beiden Formen
```

**Kein Login, kein CAPTCHA, kein robots-Verbot.** Jede Zeile trägt ein `Λήψη`
(Herunterladen), und der Klick löst tatsächlich eine Dateiübertragung aus — belegt: die
anonyme Sitzung bekam den Datenstrom, er wurde nur von der Sandkasten-Umgebung abgebrochen.

⚠ **Aber es ist kein GET.** Die Seite ist Oracle ADF; `curl` bekommt nur eine
JavaScript-Hülle, und der Download ist ein **POST mit `javax.faces.ViewState`**. Ein
Abrufer braucht eine Sitzung, kein Adressmuster.

### Das ist bereits die dritte Plattform dieser Bauform

| Land | Plattform | Form |
|---|---|---|
| **LV** | `eis.gov.lv` | Modal per POST |
| **PT** | AnoGov / compraspt | JSF mit `jsessionid` |
| **GR** | ΕΣΗΔΗΣ `nepps-search` | Oracle ADF mit `ViewState` |

**Ein sitzungsführender Abrufer löst drei Länder.** Bisher stand jedes dieser drei als
Einzelfall „nachzuholen" in seinem Kapitel — zusammen ergeben sie eine Investition mit
dreifachem Ertrag. Das ist der praktische Schluss dieses Kapitels.

## 5. ⛔ Die zwei gesperrten Hosts — und warum die Herkunft der Sperre nichts ändert

`nepps.eprocurement.gov.gr` und `publicworks.eprocurement.gov.gr` liefern:

```
User-agent: *
Disallow: /
```

⚠ Das ist die **Standarddatei der Oracle E-Business Suite** — die Datei sagt es selbst:
*„Do not edit settings in this file manually. They are managed automatically and will be
overwritten when AutoConfig runs."* Sie stammt aus 2008 und trägt sogar eine Notiz an
Sicherheitsprüfer.

Die Sperre ist also mit hoher Wahrscheinlichkeit **keine Entscheidung des Betreibers**,
sondern eine Beigabe der Software. Dieselbe Behörde, dasselbe System, und die anderen
Namen (`portal`, `nepps-search`) haben gar keine robots.txt.

**Das ändert nichts.** Eine robots.txt ist das, was unter der Adresse ausgeliefert wird;
„die haben das bestimmt nicht so gemeint" ist genau die Umgehungslogik, die in der Slowakei
schon abgelehnt wurde ([`sk.md`](sk.md): sich `ClaudeBot` zu nennen, weil der auf der Liste
steht). **Gesperrt bleibt gesperrt.**

Praktisch kostet es fast nichts: `nepps` ist zu **99 % Startseiten-Links** (163 von 165),
also ohnehin fast wertlos.

## 6. ⛔ Διαύγεια — Metadaten offen, Dokumente ausdrücklich gesperrt

Die Dateinamen oben tragen Kennungen wie `9Μ3ΘΩΞ2-8Λ9`. Das ist eine **ΑΔΑ**, die Nummer
des griechischen Transparenzportals `diavgeia.gov.gr` — und das hat eine offene
Schnittstelle.

**Die robots.txt, vollständig (120 Bytes):**
```
User-agent: *
Disallow: /decision/view
Disallow: /doc/*                     ← der Dateipfad
Disallow: /luminapi/api/decisions/*
Disallow: /f/all/ada/*
```

Und die erlaubte Metadaten-Schnittstelle antwortet:
```
GET /opendata/decisions/9Μ3ΘΩΞ2-8Λ9
    → 200: ada, subject, organizationId, submissionTimestamp, decisionTypeId,
           documentUrl: https://diavgeia.gov.gr/doc/9Μ3ΘΩΞ2-8Λ9
```

⚠ **Die Antwort nennt als `documentUrl` genau den Pfad, den die robots.txt sperrt.** Das
ist die Sorte Fall, in der ein Abrufer arglos zugreift: die offizielle Schnittstelle reicht
die Adresse selbst heraus. Sie wurde **nicht** abgerufen.

`/opendata/` selbst ist nicht gesperrt und filterbar:
```
GET /opendata/search?type=Δ.2.1&size=2   → total 17.602
```

⚠ **Falle, die Geld und Vertrauen kostet:** ein **falscher Parametername wird
stillschweigend ignoriert**. `decisionType=Δ.2.1` (statt `type=`) gibt `total 2.972.077`
zurück — den ganzen Bestand, ohne Fehler, ohne Hinweis. Wer den Namen vertippt, hält 2,97
Millionen Verwaltungsakte für 2,97 Millionen Ausschreibungen.

Dieselbe Krankheit wie die `publication_date`-Bedingung, die 93 % von DÖE lautlos verwarf —
nur in die andere Richtung.

## 7. ⛔ ΚΗΜΔΗΣ — die unterschwellige Ebene ist zu

`cerpp.eprocurement.gov.gr` (Zentrales Elektronisches Register öffentlicher Aufträge)
liefert unter `/robots.txt` **ein Anmeldeformular** — Benutzername, Passwort, POST an
`access.eprocurement.gov.gr/oam/server/auth_cred_submit` (Oracle Access Manager).

Damit gilt die stehende Regel: **kein Konto anlegen, keine Zugangsdaten.** Die
unterschwellige Ebene Griechenlands ist ohne Anmeldung nicht erreichbar.

**Fonds-Ebene: nicht recherchiert.** Griechenland ist ein grosser Kohäsionsempfänger, damit
gehört es nach der Regel aus [`fonds-ebene.md`](fonds-ebene.md) zu den vorrangigen
Kandidaten. Ungeprüft.

## 8. Zwei Fallen für jeden künftigen Abrufer

- ⚠ **`PageNotFound.jspx` kommt mit HTTP 200.** Eine der drei geprüften tiefen Adressen
  (`…/search/399127`) ist nicht vorhanden — der Server antwortet trotzdem mit 200 und
  22 KB HTML. Wer auf den Statuscode hört, zählt sie als Erfolg. Der Titel muss geprüft
  werden, nicht der Code.
- ⚠ **Die Kennungen sind griechische Grossbuchstaben.** `9Μ3ΘΩΞ2-8Λ9` sieht lateinisch aus,
  ist es aber nicht (Μ, Θ, Ω, Ξ, Λ). Das trifft dieselbe Stelle wie `Łódź` → `['d']` in
  Kapitel 14 der Länder-Bibel. **Vor der ersten Messung klären.**

## 9. Ergebnis

| | |
|---|---|
| Ausschreibungen sichtbar | ✅ vollständig, ohne Anmeldung (`nepps-search`) |
| Dokumente sichtbar | ✅ gelistet, mit Namen und ESPD |
| Dokumente abrufbar | 🟡 **ja, aber nur mit Sitzung** (ADF-POST), nicht per GET |
| Unterschwellig (ΚΗΜΔΗΣ) | ⛔ Anmeldung |
| Transparenzportal-Dateien | ⛔ robots sperrt `/doc/*` |
| Nutzbare Basis | ⚠ **43 % der Links nennen kein Verfahren** |

Griechenland ist damit kein „offenes" und kein „gesperrtes" Land, sondern das erste klar
**bedingt offene**: alles ist da und öffentlich, der Abruf kostet einen Abrufer, den zwei
andere Länder ebenfalls brauchen.
