"""Antwortvorschlaege zu einem Fragebogen, gebaut aus der Bausteinbibliothek des Kunden.

**Was das ist.** Die Vergabestelle verlangt einen Fragebogen (Excel, DOCX, PDF). Der Kunde hat
seine Referenzen, Zertifikate und bewaehrten Textbausteine in der Bibliothek liegen
(`web/components/explorer/BausteinLibrary.tsx`, Themen aus `blocks.THEMES`). Dieses Modul legt
beides zusammen: je Frage ein **Vorschlag mit Beleg**, den ein Mensch prueft und freigibt.

**Warum hier und nicht in einer Next-Route.** Die Geldwache sitzt in `llm.chat()` und nicht im
Aufrufer (s. Auto-Memory `govisor-geldwache`). Eine Route, die selbst bei OpenRouter anklopft,
umgeht Kontostand, Tagesbuch und Deckel. Deshalb laeuft die Erzeugung in Python; die Weboberflaeche
reicht nur Fragebogen und Bausteine herein und bekommt Vorschlaege zurueck.

⚠ **DIE EIGENTLICHE REGEL DIESES MODULS: nichts erfinden.** Ein Vorschlag darf ausschliesslich aus
den mitgegebenen Bausteinen bestehen, und jeder Beleg wird **nachgeprueft** — das Zitat muss
woertlich im genannten Baustein stehen (`docextract.verify_quote`, dieselbe Pruefung wie bei der
Dokumentenanalyse). Haelt ein Beleg nicht, faellt der Vorschlag auf `unbelegt` und wird **nicht**
als fertig angezeigt. Ohne passenden Baustein wird **gar kein Modell gefragt**: das spart Geld und
verhindert die freundliche Halluzination, die im Angebot am teuersten ist.

Der Reihe nach:

    text  = "1. Bitte beschreiben Sie Ihr Qualitaetsmanagement. 2. Welche Referenzen …"
    fragen = fragen_aus_text(text)
    for f in fragen:
        v = vorschlag(f, bausteine)        # bausteine = [{"id","theme","content"}, …]
        v["status"]                        # fertig | unbelegt | kein_baustein
"""
from __future__ import annotations

import json
import re

from . import blocks, docextract

# ─────────────────────────────────────────────────────────────────────────────────────────────
# 1. Fragen aus einem Fragebogen ziehen
# ─────────────────────────────────────────────────────────────────────────────────────────────

# Verben, mit denen eine Vergabestelle eine Antwort verlangt, ohne ein Fragezeichen zu setzen.
# ⚠ Ein Fragebogen besteht ueberwiegend aus solchen Saetzen ("Bitte legen Sie dar, …"), nicht aus
# echten Fragen. Wer nur auf "?" filtert, findet in einem typischen Bogen die Haelfte nicht.
_AUFFORDERUNG = re.compile(
    r"\b(beschreiben|erlaeutern|erläutern|benennen|darlegen|legen\s+Sie\s+dar|"
    r"geben\s+Sie\s+an|machen\s+Sie\s+Angaben|nachweisen|fuegen\s+Sie\s+bei|"
    r"fügen\s+Sie\s+bei|verfuegen\s+Sie|verfügen\s+Sie|wie\s+stellen\s+Sie)\b",
    re.I,
)

# Nummerierung am Zeilenanfang: "1.", "2.3", "2.3.", "A)", "(4)" — wird als Fragennummer
# uebernommen.
# ⚠ Die gepunktete Form braucht KEIN abschliessendes Satzzeichen ("2.3 Welche Referenzen …" ist
# die haeufigste Schreibweise in echten Boegen). Eine blanke Zahl dagegen schon, sonst frisst das
# Muster jede Zeile, die mit "3 Monate …" beginnt. Gemessen an einem Beispielbogen: ohne diese
# Unterscheidung blieb die Nummer bei jeder zweiten Frage im Fragetext stehen.
_NUMMER = re.compile(r"^\s*(?:\(?([0-9]+\.[0-9]+(?:\.[0-9]+)*)\)?[.)]?\s+"
                     r"|\(?([0-9]+|[A-Z])\)?[.)]\s+)")

_MIN_LAENGE = 12          # kuerzere Zeilen sind Spaltenkoepfe, keine Fragen
_MAX_LAENGE = 600         # laengere sind Vertragstext, der zufaellig ein Fragezeichen enthaelt


def fragen_aus_text(text: str, max_fragen: int = 200) -> list[dict]:
    """Zerlegt den Text eines Fragebogens in einzelne Fragen.

    Erkannt wird eine Zeile, die **entweder** auf ein Fragezeichen endet **oder** eine
    Aufforderung enthaelt (s. `_AUFFORDERUNG`). Die Nummer wird abgetrennt und mitgefuehrt,
    damit der Vorschlag spaeter an der richtigen Stelle im Bogen landet.

    ⚠ **Grenze, die bekannt ist und nicht uebertuencht wird:** eine Excel-Tabelle kommt hier als
    Zellentext an (eine Zelle je Zeile, aus dem XLSX-Leser weiter oben). Verteilt eine
    Vergabestelle eine Frage ueber mehrere Zellen, erkennt dieses Modul zwei Fragmente statt
    einer Frage. Das faellt dem pruefenden Menschen auf, weil der Vorschlag dann nicht passt —
    es erzeugt aber keinen falschen Vorschlag, und das ist die Richtung, in die der Fehler
    fallen soll.
    """
    fragen: list[dict] = []
    for rohzeile in text.splitlines():
        zeile = " ".join(rohzeile.split())
        if not (_MIN_LAENGE <= len(zeile) <= _MAX_LAENGE):
            continue
        m = _NUMMER.match(zeile)
        nummer = (m.group(1) or m.group(2)) if m else None
        rest = zeile[m.end():] if m else zeile
        if not rest:
            continue
        if not (rest.rstrip().endswith("?") or _AUFFORDERUNG.search(rest)):
            continue
        fragen.append({"nr": nummer, "frage": rest.strip(), "thema": blocks.assign_theme(rest)})
        if len(fragen) >= max_fragen:
            break
    return fragen


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 2. Passende Bausteine finden — ohne Modell, deterministisch
# ─────────────────────────────────────────────────────────────────────────────────────────────

def _deckung(fw: set[str], bw: set[str]) -> float:
    """Anteil der Frageworte, die im Baustein vorkommen — **komposita-tolerant**.

    ⚠ Ohne diese Toleranz trifft `Qualitaetsmanagementsystem` sein `Qualitaetsmanagement` nicht,
    und genau diese Frage findet dann keinen Baustein. Es ist dieselbe Eigenschaft des Deutschen,
    derer wegen unsere Teilstring-Suche dem Postgres-Stemmer ueberlegen ist (`govisor/search.py`:
    „Grosswaermepumpe" 15 Treffer gegen 0) — hier wirkt sie nur in die andere Richtung, und sie
    wird genauso gebraucht.

    Mindestlaenge 6, damit nicht `ist` in `Leistung` trifft.
    """
    if not fw:
        return 0.0
    treffer = 0
    for w in fw:
        if w in bw:
            treffer += 1
        elif len(w) >= 6 and any(len(b) >= 6 and (w in b or b in w) for b in bw):
            treffer += 1
    return treffer / len(fw)


def kandidaten(frage: dict, bausteine: list[dict], n: int = 3) -> list[dict]:
    """Die bis zu `n` Bausteine, die am besten zur Frage passen.

    Bewertung bewusst **ohne Modell**: gleiches Thema zaehlt schwer, danach die Ueberlappung der
    Schlagworte. `blocks.assign_theme` und `blocks.derive_keywords` sind dieselben Funktionen,
    mit denen die Bausteine beim Anlegen beschriftet wurden — eine zweite, abweichende Logik
    hier waere ein stiller Riss zwischen Ablage und Suche.

    Rueckgabe sind Kopien mit `_score`, absteigend. Leere Liste heisst: nichts passt, und dann
    wird **kein Modell gefragt** (s. `vorschlag`).
    """
    fw = set(blocks.derive_keywords(frage["frage"], n=8))
    treffer = []
    for b in bausteine:
        inhalt = (b.get("content") or "").strip()
        if not inhalt:
            continue
        score = 0.0
        if b.get("theme") and b["theme"] == frage.get("thema"):
            score += 2.0
        bw = set(blocks.derive_keywords(inhalt, n=12))
        score += 3.0 * _deckung(fw, bw)
        if score <= 0:
            continue
        treffer.append({**b, "_score": round(score, 3)})
    treffer.sort(key=lambda x: (-x["_score"], len(x.get("content") or "")))
    return treffer[:n]


# ─────────────────────────────────────────────────────────────────────────────────────────────
# 3. Den Vorschlag erzeugen und seinen Beleg nachpruefen
# ─────────────────────────────────────────────────────────────────────────────────────────────

_ANWEISUNG = (
    "Du formulierst einen Antwortentwurf fuer einen Vergabe-Fragebogen. Benutze AUSSCHLIESSLICH "
    "die mitgegebenen Textbausteine des Unternehmens. Erfinde keine Zahlen, Namen, Zertifikate, "
    "Referenzen oder Fristen. Was die Bausteine nicht hergeben, bleibt weg.\n\n"
    "Antworte als JSON-Objekt:\n"
    '{"antwort": "<Entwurf, deutsch, sachlich>", '
    '"belege": [{"baustein": "<id>", "zitat": "<woertliche Passage aus genau diesem Baustein>"}]}\n\n'
    "Jede inhaltliche Aussage im Entwurf braucht einen Beleg. Das Zitat muss WOERTLICH in dem "
    "genannten Baustein stehen. Reicht kein Baustein, gib eine leere Antwort und leere Belege."
)


def _nachricht(frage: dict, kand: list[dict]) -> list[dict]:
    teile = [f"Frage {frage.get('nr') or ''}: {frage['frage']}".strip(), "", "Bausteine:"]
    for b in kand:
        teile.append(f"--- id={b.get('id') or b.get('theme')} thema={b.get('theme')}")
        teile.append((b.get("content") or "").strip())
    return [{"role": "system", "content": _ANWEISUNG},
            {"role": "user", "content": "\n".join(teile)}]


def pruefe_belege(antwort: str, belege: list[dict], kand: list[dict]) -> tuple[bool, list[str]]:
    """Haelt jeder Beleg? Liefert (alles_ok, Liste der Beanstandungen).

    Geprueft wird mit `docextract.verify_quote`, also derselben normalisierten Enthaltensein-
    Pruefung wie bei der Dokumentenanalyse. Zwei Dinge koennen schiefgehen, und beide sind
    schon vorgekommen: ein Zitat, das **nirgends** steht (erfunden), und ein Zitat, das in
    einem **anderen** Baustein steht als angegeben (verwechselt). Das zweite ist harmloser,
    aber es macht die Herkunftsangabe falsch — und die ist hier der ganze Punkt.
    """
    nach_id = {str(b.get("id") or b.get("theme")): (b.get("content") or "") for b in kand}
    maengel: list[str] = []
    if antwort.strip() and not belege:
        maengel.append("Entwurf ohne jeden Beleg")
    for i, beleg in enumerate(belege, 1):
        bid, zitat = str(beleg.get("baustein", "")), (beleg.get("zitat") or "").strip()
        if not zitat:
            maengel.append(f"Beleg {i}: leeres Zitat")
            continue
        if bid not in nach_id:
            maengel.append(f"Beleg {i}: Baustein {bid!r} war nicht mitgegeben")
            continue
        if not docextract.verify_quote(zitat, nach_id[bid]):
            woanders = [k for k, t in nach_id.items() if docextract.verify_quote(zitat, t)]
            maengel.append(
                f"Beleg {i}: Zitat steht nicht in {bid!r}"
                + (f", sondern in {woanders[0]!r}" if woanders else " (steht nirgends)")
            )
    return (not maengel), maengel


def vorschlag(frage: dict, bausteine: list[dict], chat_fn=None, n_kandidaten: int = 3) -> dict:
    """Ein Antwortvorschlag zu einer Frage.

    `status` ist das Ergebnis und entscheidet, was die Oberflaeche zeigt:

    ===============  ====================================================================
    `kein_baustein`  nichts passt. **Es wird kein Modell gefragt.** Kein Entwurf, kein Geld.
    `unbelegt`       ein Entwurf kam, aber ein Beleg haelt nicht. Wird NICHT als fertig
                     angezeigt; `maengel` sagt, was nicht stimmt.
    `fertig`         Entwurf da, alle Belege geprueft. Wartet auf den Menschen.
    ===============  ====================================================================

    ⚠ `fertig` heisst **geprueft, nicht freigegeben**. Nichts aus diesem Modul geht ohne einen
    Menschen in ein Angebot; die Freigabe ist ein Schritt in der Oberflaeche und keine Zusage
    dieser Funktion.
    """
    kand = kandidaten(frage, bausteine, n=n_kandidaten)
    if not kand:
        return {"frage": frage, "status": "kein_baustein", "antwort": "", "belege": [],
                "kandidaten": [], "maengel": []}

    if chat_fn is None:                                   # spaeter Import: Tests brauchen kein Netz
        from . import llm

        def chat_fn(messages):                            # noqa: E306
            with llm.kontext(zweck="antwortvorschlag"):
                return llm.chat(messages, model=llm.mit_boden(llm.gewaehltes_modell()))

    roh = chat_fn(_nachricht(frage, kand))
    try:
        daten = json.loads(roh[roh.index("{"):roh.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"frage": frage, "status": "unbelegt", "antwort": "", "belege": [],
                "kandidaten": kand, "maengel": ["Antwort des Modells war kein JSON"]}

    antwort = (daten.get("antwort") or "").strip()
    belege = [b for b in (daten.get("belege") or []) if isinstance(b, dict)]
    if not antwort:
        return {"frage": frage, "status": "kein_baustein", "antwort": "", "belege": [],
                "kandidaten": kand, "maengel": ["Modell sah keinen passenden Baustein"]}

    ok, maengel = pruefe_belege(antwort, belege, kand)
    return {"frage": frage, "status": "fertig" if ok else "unbelegt", "antwort": antwort,
            "belege": belege, "kandidaten": kand, "maengel": maengel}


def vorschlaege(fragen: list[dict], bausteine: list[dict], chat_fn=None) -> dict:
    """Alle Fragen abarbeiten. Liefert die Vorschlaege plus eine Zaehlung je `status`.

    Die Zaehlung ist die Zahl, die der Nutzer sieht ("7 von 12 Fragen vorbereitet") — und sie
    zaehlt **nur** `fertig`. Ein `unbelegt` als halben Erfolg zu verbuchen waere genau die
    Schoenrechnung, die das Versprechen dieses Produkts aushoehlt.
    """
    raus = [vorschlag(f, bausteine, chat_fn=chat_fn) for f in fragen]
    zaehlung = {"fertig": 0, "unbelegt": 0, "kein_baustein": 0}
    for v in raus:
        zaehlung[v["status"]] = zaehlung.get(v["status"], 0) + 1
    return {"vorschlaege": raus, "zaehlung": zaehlung,
            "fragen_gesamt": len(fragen), "fertig": zaehlung["fertig"]}
