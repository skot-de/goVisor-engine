# Erkannte Doktypen, die nie ausgewertet werden — ABGEARBEITET 2026-09-18

## Ergebnis vorweg

**Die Liste `AUSWERTUNG` wird NICHT erweitert.** Und es gibt einen zweiten Befund, der
zehnmal billiger ist und mehr bringt: **566 Vorgaenge aus dem Altbestand tragen 913
Dokumente, deren Typ laengst auf der Liste steht.**

## Schritt 1: die Kosten, aus dem Kostenbuch gerechnet

`token_cost` in den Analysedateien sind TOKEN, keine Dollar. Der Preis kommt aus
`data/llm_kosten.jsonl`, 34.391 Aufrufe mit Token UND Kosten:

    google/gemini-2.5-flash   23.384 Aufrufe · 304,6 Mio Token · 146,89 USD
                              → 0,000482 USD je 1.000 Token

Gemessen ueber 11.144 Auswertungen: 240,7 Mio Token fuer 58.765 ausgewertete Dokumente,
also **4.096 Token je Dokument**. Bisher ausgegeben: 116,02 USD.

    Doktyp              Dateien        Token      USD (einmalig)
    eigenerklaerung      13.131   53.784.901       25,92
    informationsblatt     5.396   22.102.150       10,65
    formblatt             2.986   12.230.730        5,90
    preisblatt            3.194   13.082.703        6,31

    eigenerklaerung + informationsblatt                36,58 USD
    laufend je Nacht (~200 neue Vorgaenge)              0,66 USD

Bezahlbar. Die Frage ist also nicht, ob man es sich leisten kann, sondern ob es etwas
bringt.

## Schritt 2: die Stichprobe — und sie sagt nein

⚠ **Was in den `eigenerklaerung`-Dokumenten steht**, aus dem Volltext gelesen:

    Eigenerklärung RUS / Bezug Russland          EU-VO 2022/576, Sanktionserklaerung
    Eigenerklärung zu Finanzsanktionen (NU)      dito, fuer Nachunternehmer
    Ausschlussgruende §§ 123, 124 GWB            gesetzlicher Standard
    Einheitliche Europäische Eigenerklärung      Text ist „; ; . ; ; ? ; ; ?"

Das sind **Formulare zum Unterschreiben**, keine Quellen von Anforderungen. Die EEE hat
nicht einmal extrahierbaren Text — ein leeres Ausfuellformular.

`informationsblatt` ist ueberwiegend Verfahrenshinweis: elektronische Angebotsabgabe,
Datenschutz, Nutzung der Vergabeplattform.

Ueber alle Dateien ausgezaehlt (Namensklassen, grob aber breit):

    Doktyp              inhaltstragend   Verfahren   unklar
    eigenerklaerung            9 %           0 %      91 %   (Bietergemeinschaft_Erklaerung …)
    informationsblatt          3 %          51 %      46 %
    formblatt                  3 %           4 %      93 %

Fuer 36,58 USD bekaeme man ueberwiegend Unterschriftsformulare. **Der Auftrag hat den Fall
selbst vorweggenommen:** „Wenn die Eigenerklaerung nur wiederholt, was die Aufforderung
sagt, ist der Gewinn null und die Kosten sind echt."

⚠ Es gibt eine echte Teilmenge — `BbgVergG_Mindestlohn_NUN.pdf`,
`VHB_BY_216_Verzeichnis_vorzulegende_Unterlagen` —, aber sie ueber den Dateinamen zu
fischen waere eine bruechige Regel fuer wenige Prozent. Wer sie will, baut sie als eigene
Doktyp-Regel in `doctypes.py`, nicht als Erweiterung von `AUSWERTUNG`.

## Der zweite Befund: 913 Dokumente, deren Typ schon auf der Liste steht

Beim Nachgehen der „254 fragenantworten" aus dem urspruenglichen Verdacht kamen **931**
Dateien heraus, deren NAME einen AUSWERTUNGS-Typ ergibt und die trotzdem in
`other_documents` liegen:

    254  fragenantworten        „Bieterfragen-Antworten_VV1-5_Version11.pdf"
    211  aufforderung           „VHB_ANGEBOTSSCHREIBEN", „Formblatt213_Angebot"
    174  leistungsbeschreibung  „LV_HLS_KIT_Neubau_ohne Preise.pdf"
    152  vertrag
    128  eignung                „VHB-124" — die Eigenerklaerung zur Eignung
     12  zuschlagskriterien

⚠ **Das ist KEIN Defekt im laufenden Betrieb.** Nach Auswertungsdatum aufgeschluesselt:

    ohne `analysiert_am` (Altbestand)   913
    ab dem 10.09.2026                     3   (in zehn Tagen)

913 von 931 stammen aus Auswertungen, die das Feld `analysiert_am` noch nicht tragen —
also von vor der Verbesserung des Klassifizierers. Der Zweig in `analyze_docs.py` ist
korrekt: was in `AUSWERTUNG` steht, landet nicht in `other_documents`.

**Es ist ein Rueckstand, und er ist billig aufzuloesen:**

    566 Vorgaenge betroffen
    nur die fehlplatzierten Dateien    1,80 USD
    ganze Vorgaenge neu (3.990 Dok.)   7,88 USD

Fuer 7,88 USD kommen 254 Bieterfragen-Antworten und 122 Eignungsnachweise in die
Auswertung — Dokumente, die Fristen aendern und Nachweise fordern. Das ist der
zehnfache Gegenwert der 36,58 USD, die die Typ-Erweiterung gekostet haette.

## Aufgabe (offen)

Die 566 Altbestands-Vorgaenge neu auswerten lassen. ⚠ Das kostet echtes Geld auf Svens
Schluessel — deshalb nicht ohne ausdrueckliche Ansage. Der Analyse-Arbeiter
(`scripts/analyse_arbeiter.sh`) laeuft ohnehin; es braucht einen Weg, genau diese
Vorgaenge erneut in die Schlange zu stellen.

## Abnahme
- Zahl der Vorgaenge mit `anf.quelle=unterlagen` vorher/nachher — das ist der Beleg.
- `pruefe-dichte.mjs` muss danach gruen bleiben.
- Tatsaechliche Kosten aus dem Kostenbuch gegen die geschaetzten 7,88 USD halten.
