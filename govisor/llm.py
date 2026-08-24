"""OpenRouter-Client mit Multi-Key-Fallback.

Mehrere API-Keys hinterlegen und das Budget bündeln: läuft ein Key auf **402 (Guthaben leer)**,
mustert der Client ihn (prozessweit) aus und rotiert automatisch zum nächsten. Rate-Limit (429)
→ kurzer Backoff, dann nächster Key.

Keys werden in dieser Priorität geladen (erste Fundstelle je Key gewinnt, Duplikate raus):
  1. Env  ``OPENROUTER_KEYS``            — Komma-getrennt
  2. Datei ``.secrets/openrouter.keys``  — ein Key je Zeile (``#``-Kommentare erlaubt)
  3. Datei ``.secrets/openrouter.key``   — einzelner Key (Abwärtskompatibilität)
Alle Dateien liegen unter ``.secrets/`` (gitignored). Nutzung:

    from govisor.llm import chat
    text = chat([{"role": "user", "content": "hallo"}], model="google/gemini-2.5-flash")
"""
from __future__ import annotations

import os as _os
import sys
import threading as _threading
from pathlib import Path as _Path

import contextlib
import os
import threading
import time
from pathlib import Path

import requests

from govisor import kostenbuch

URL = "https://openrouter.ai/api/v1/chat/completions"

# ── ANBIETERBODEN: DERSELBE MODELL, DER GUENSTIGSTE WEG ──────────────────────────────
#
# Gemessen am 2026-08-23 fuehrt OpenRouter fuer `google/gemini-2.5-flash` SIEBEN Endpunkte:
#
#     0,150 / 1,250 $/Mio   google-ai-studio/flex
#     0,300 / 2,500 $/Mio   google-ai-studio · google-vertex/global · google-vertex/eu
#     0,540 / 4,500 $/Mio   google-ai-studio/priority · google-vertex/global/priority
#
# Dasselbe Modell, Spanne 3,6-fach. Ohne Angabe verteilt OpenRouter nach „price-based load
# balancing": gewichtet nach dem inversen Quadrat des Preises. Guenstig bevorzugt, aber eben
# NICHT immer — wir landeten regelmaessig auf den teuren Endpunkten, ohne es zu merken.
#
# ⚠ `provider.sort = "price"` REICHT NICHT. Es sortiert nur; die Flex-Endpunkte bleiben
# gesperrt. Nur die Endung `:floor` macht sie zusaetzlich zulaessig — laut OpenRouter-Doku
# „a superset of setting provider.sort to price". Wer nur sortiert, zahlt weiter 0,300.
#
# Was das kostet: nichts. Gleiches Modell, gleicher Kontext (1.048.576), gleiche
# Ausgabegrenze (65.535). Was es bringt: bis zur Haelfte. Was es riskiert: Flex ist die
# niedrigere Dienstguete — langsamer, mehr Warteschlange. Fuer einen Nachtarbeiter mit
# Wachhund ist das gleichgueltig, aber es ist eine Behauptung, bis das Kostenbuch sie
# belegt. Deshalb wird ab hier jeder Aufruf mit Preis und Dauer mitgeschrieben.
_MODELL_ROH = os.environ.get("OR_MODEL", "google/gemini-2.5-flash")

# Preisdeckel je Mio Token, Format „Eingabe/Ausgabe" (z. B. „0.30/2.50"). Ohne Angabe kein
# Deckel. Er ist der Guertel zum Hosentraeger: `:floor` waehlt den billigsten Endpunkt, der
# Deckel verbietet den teuren auch dann, wenn der billige gerade ausfaellt.
#
# ⚠ NICHT VORBELEGEN. Ein fest eingebauter Deckel gilt auch fuer ein Modell, das jemand
# spaeter per OR_MODEL setzt — und sperrt dann womoeglich JEDEN Endpunkt aus. Der Aufruf
# scheitert mit „no allowed providers", und die Ursache steht an einer Stelle, an die
# niemand schaut. Wer deckeln will, deckelt bewusst.
# Schalter fuer den Boden. „aus" fuehrt jeden Aufruf ohne `:floor` — noetig, um den Boden
# ueberhaupt MESSEN zu koennen: ohne eine Vergleichsgruppe ohne Boden ist die Ersparnis eine
# Behauptung. Der Vergleich laeuft ueber `scripts/kostenbericht.py --boden`.
# Obergrenze der Ausgabe je Aufruf. ⚠ KEINE Sparmassnahme, sondern eine Ausreisser-Bremse.
#
# Gemessen am 2026-08-24 ueber 311 Produktionsaufrufe: der Amtierende braucht im Median
# 775 Ausgabe-Token, im 90.-Perzentil 6.242, im Hoechstfall 50.964. Der Kandidat
# `nex-agi/nex-n2-mini` erzeugte in EINEM Aufruf 65.536 — exakt die Obergrenze des
# Endpunkts. Er hoerte schlicht nicht auf zu schreiben und brauchte dafuer 760 Sekunden,
# gegen 2,6 s im Median beim Amtierenden.
#
# Ohne Angabe gilt die Grenze des Anbieters, und die ist bei jedem anders. 56.000 liegt
# ueber allem, was wir je legitim gebraucht haben (50.964), und deckelt trotzdem den
# Ausreisser. Wer sie enger zieht, schneidet echte Antworten ab — und eine abgeschnittene
# Antwort ist unparsbar, kostet also doppelt: einmal bezahlt, nichts bekommen.
OR_MAX_TOKENS = int(os.environ.get("OR_MAX_TOKENS", "56000"))

# Harte Gesamtfrist je Aufruf, in Sekunden. 0 = aus.
#
# ⚠ DER `timeout` VON `requests` REICHT NICHT. Er misst die Pause ZWISCHEN Bytes, nicht die
# Gesamtdauer. Am 2026-08-24 lief ein Aufruf an `nex-agi/nex-n2-mini` 761 Sekunden durch,
# obwohl `timeout=120` gesetzt war — die Gegenstelle haelt die Verbindung mit Fuellbytes
# offen, und damit laeuft der Lesetimeout nie ab.
#
# Gemessen ueber 311 Produktionsaufrufe des Amtierenden: Median 3,7 s, 95.-Perzentil
# 36,4 s, Maximum 185,1 s. 600 s ist also weit jenseits von allem Legitimen und faengt nur
# den echten Haenger. Der Pruefstand setzt sich fuer Kandidaten eine engere Frist.
OR_FRIST = float(os.environ.get("OR_FRIST", "600"))
OR_BODEN = os.environ.get("OR_BODEN", "an").lower()
# ⚠ `:floor` IST EINE BITTE, KEINE GARANTIE — und das ist der teuerste Irrtum dieses
# Moduls gewesen. Gemessen am 2026-08-24 ueber 311 Aufrufe, ALLE mit `:floor` gesendet:
#
#     304× Standard 0,300/2,500  ueber „Google" (Vertex)
#       5× Flex     0,150/1,250  ueber „Google AI Studio"
#
# Der Boden sortiert nach Preis und erlaubt Flex — aber `allow_fallbacks` steht auf wahr,
# und sobald der billigste Endpunkt nicht sofort liefert, geht es eine Stufe hoeher, ohne
# dass irgendwo etwas steht. Wir haben 2,45 $ gezahlt statt 1,27 $: **48 % zu viel**.
#
# Ich hatte nach den ersten fuenf Aufrufen „der Boden greift, arithmetisch bewiesen"
# gemeldet. Die fuenf stimmten. Die naechsten 304 nicht.
#
# Was wirklich zwingt, ist der Preisdeckel: mit `max_price` auf dem Bodenpreis geht der
# Aufruf an Flex — nachgemessen, derselbe Prompt, einmal 0,00000460 $ ohne und
# 0,00000245 $ mit Deckel. Der Deckel wird deshalb aus dem Modell selbst abgeleitet.
OR_STRENG = os.environ.get("OR_STRENG", "an").lower()
OR_MAX_PREIS = os.environ.get("OR_MAX_PREIS", "")

# „deny" schliesst Anbieter aus, die Eingaben speichern duerfen. Ebenfalls nicht vorbelegt:
# ob der Flex-Endpunkt darunter faellt, sagt die OpenRouter-Schnittstelle nicht (das Feld
# `data_policy` kam bei allen sieben Endpunkten leer zurueck). Einschalten heisst hier also
# moeglicherweise: den halben Preis wieder aufgeben. Das ist eine Abwaegung, keine Vorgabe.
OR_DATENSCHUTZ = os.environ.get("OR_DATENSCHUTZ", "")
_SECRETS = Path(os.environ.get("GOVISOR_SECRETS", ".secrets"))

# ── ZWEITER ANBIETER: CEREBRAS ───────────────────────────────────────────────────────
#
# Am 2026-08-18 lief das OpenRouter-Guthaben mitten im Rueckstau-Abbau leer: 526 Analysen,
# dann 402 bei jedem Aufruf. Der Arbeiter drehte weiter Runden, ohne dass etwas passierte.
# Ein zweiter Anbieter ist deshalb keine Bequemlichkeit, sondern die Sicherung dagegen, dass
# ein leeres Konto die ganze Kette anhaelt.
#
# Cerebras spricht die OpenAI-Schnittstelle, hat aber EIGENE Modellnamen — „google/
# gemini-2.5-flash" gibt es dort nicht. Deshalb traegt jeder Anbieter sein eigenes
# Standardmodell; ein von aussen gesetztes Modell gilt nur fuer den Anbieter, zu dem es passt
# (erkennbar am Schraegstrich in OpenRouter-Namen).
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_MODEL = os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b")
TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"
TOGETHER_MODEL = os.environ.get("TOGETHER_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
SAMBANOVA_URL = "https://api.sambanova.ai/v1/chat/completions"
# DeepSeek-V3.1 statt gpt-oss-120b: gemessen findet gpt-oss rund ein Drittel weniger
# Pruefpunkte als Gemini (34 statt 53) und verwirft mehr Zitate (19 % statt 11 %). Ein
# groesseres Modell ist hier die naheliegende Wahl, solange Guthaben da ist.
# Gemessen am 2026-08-18 an derselben Frage: gpt-oss-120b 1,1 s · Llama-3.3-70B 2,0 s ·
# DeepSeek-V3.2 lief nach 180 s in den Timeout, DeepSeek-V3.1 brauchte 78 s. Die grossen
# DeepSeek-Modelle sind dort also unbrauchbar langsam — nicht falsch, nur nicht benutzbar,
# wenn 4.500 Vorgaenge warten.
SAMBANOVA_MODEL = os.environ.get("SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct")
XAI_URL = "https://api.x.ai/v1/chat/completions"
# Gemessen 2026-08-18: grok-4-fast-non-reasoning 0,9 s, grok-3-mini 8,7 s. Bei 4.300
# wartenden Vorgaengen entscheidet die Antwortzeit ueber Stunden, nicht ueber Sekunden.
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4-fast-non-reasoning")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar")
_LOCK = threading.Lock()
_EXHAUSTED: set[str] = set()   # Keys ohne Guthaben (402), prozessweit gemerkt
# Wer hat zuletzt geantwortet? JE FADEN, nicht global: der Analyse-Lauf schickt 40 Anfragen
# gleichzeitig, und eine gemeinsame Variable wuerde die Herkunft der Ergebnisse vertauschen.
# Ohne diese Angabe steht im Ergebnis nicht, welches Modell es erzeugt hat — und dann laesst
# sich spaeter nicht mehr sagen, warum ein Bestand anders aussieht als der daneben.
_LETZTER = threading.local()
# Wofuer wird gerade Geld ausgegeben? Ebenfalls JE FADEN. Ohne diese Angabe steht im
# Kostenbuch zwar der Preis, aber nicht der Anlass — und dann laesst sich hinterher nicht
# trennen, was die Produktion gekostet hat und was ein Versuch. Genau diese Trennung fehlte
# am 2026-08-23, als ein Deckel-Test das Guthaben des Analyse-Arbeiters aufbrauchte.
_KONTEXT = threading.local()
# Engere Frist fuer den laufenden Abschnitt — je Faden, wie alles andere hier.
_FRIST = threading.local()


def _load_keys() -> list[str]:
    keys: list[str] = []
    env = os.environ.get("OPENROUTER_KEYS")
    if env:
        keys += [k.strip() for k in env.split(",") if k.strip()]
    for name in ("openrouter.keys", "openrouter.key"):
        p = _SECRETS / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                k = line.strip()
                if k and not k.startswith("#") and k not in keys:
                    keys.append(k)
    return keys


def _load_keys_aus(anbieter: str) -> list[str]:
    """Keys eines Anbieters: erst Umgebung, dann `.secrets/<anbieter>.keys|.key`."""
    keys: list[str] = []
    env = os.environ.get(f"{anbieter.upper()}_KEYS")
    if env:
        keys += [k.strip() for k in env.split(",") if k.strip()]
    for name in (f"{anbieter}.keys", f"{anbieter}.key"):
        p = _SECRETS / name
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                k = line.strip()
                if k and not k.startswith("#") and k not in keys:
                    keys.append(k)
    return keys


def _load_cerebras_keys() -> list[str]:
    return _load_keys_aus("cerebras")


def _anbieter() -> list[dict]:
    """Die Anbieterliste — seit 2026-08-21 **nur noch OpenRouter**.

    **Warum die anderen weg sind.** Die Kette aus fuenf Anbietern stammte aus einer Zeit mit
    Restguthaben bei xAI, Perplexity, Together, SambaNova und Cerebras. Sven am 2026-08-21:
    „das kommt aus der zeit wo ich noch rest budgets bei den anbietern hatte. nun muss ich
    aktiv nachladen und das mache ich dann nur bei openrouter." Wer nur eine Kasse fuellt,
    braucht keine Verteilungslogik — und bekommt eine Eigenschaft geschenkt, die vorher
    fehlte: **derselbe Bestand entsteht mit demselben Modell**.

    **Was das behebt.** Bis hierher entschied das Guthaben, welches Modell eine Vergabe
    analysierte. Gemessen an 3.544 produktiv gerechneten Vergaben (`scripts/llm_qualitaet.py`)
    war das ein Bestand ohne gemeinsame Aussage:

        google/gemini-2.5-flash      43,3 belegte Punkte · 15 % verworfen ·  5 % gruen
        cerebras/gpt-oss-120b        27,1 ·  19 % ·  7 % gruen
        xai/grok-4-fast              25,1 ·  23 % · 26 % gruen · 14 % ganz ohne Befund
        perplexity/sonar             22,5 ·  17 % · 11 % gruen
        together/Llama-3.3-70B       16,9 ·  22 % · 90 % gruen
        sambanova/Llama-3.3-70B      16,2 ·  28 % · 86 % gruen

    Die letzte Spalte ist die schlimmste: die Modelle, die am **wenigsten** finden, erklaeren
    fast alles fuer unproblematisch. Fuer den Nutzer heisst gruen „keine Huerden".

    **Was mit dem Wegfall verlorengeht — bewusst notiert, damit es niemand neu entdeckt:**

    * Perplexitys `sonar` brauchte zwingend `disable_search: True`. Ohne den Schalter
      recherchierte es im Netz und lieferte 20 Webquellen je Antwort — unter der Belegpflicht
      (Zitat AUS DEM DOKUMENT) entstehen so Saetze, die stimmen koennen und trotzdem nicht in
      den Unterlagen stehen.
    * Cerebras war auf kurze Fragen mit 0,9 s das schnellste und lief bei den langen
      Volltexten dieser Aufgabe reproduzierbar in sein Ratenlimit (429).
    * Together und SambaNova fuhren **dasselbe** Llama-3.3-70B mit messbar verschiedenem
      Ergebnis (16,9 bei 22 % gegen 16,2 bei 28 %) — gleiche Gewichte, andere Auslieferung.

    Ein Wiedereinstieg ist ein Listeneintrag; die Schluessel-Lader bleiben erhalten.
    """
    return [
        {"name": "openrouter", "url": URL, "keys": _load_keys(), "model": DEFAULT_MODEL},
    ]
def mit_boden(modell: str | None) -> str:
    """Haengt `:floor` an, wenn noch keine Route dransteht und der Boden eingeschaltet ist.

    ⚠ **Anhaengen statt voraussetzen — und zwar aus einem konkreten Grund.** Der Boden als
    blosse Vorgabe in `DEFAULT_MODEL` waere in der Produktion wirkungslos gewesen:
    `scripts/analyse_arbeiter.sh` setzt `OR_MODEL="google/gemini-2.5-flash"` ausdruecklich,
    und `scripts/analyze_docs.py` trug denselben Namen noch einmal fest eingebaut. Die
    Vorgabe haette also genau an der einen Stelle nicht gegriffen, an der das Geld ausgegeben
    wird — und im Kostenbuch haette trotzdem plausibel etwas gestanden.

    Eine bereits gesetzte Route (`:nitro`, `:floor`) bleibt unangetastet: wer den schnellen
    Weg ausdruecklich will, bekommt ihn.
    """
    if not modell or OR_BODEN == "aus":
        return modell or ""
    # ⚠ NICHT NUR AUF `:floor`/`:nitro` PRUEFEN. In der Warteschlange stand am 2026-08-24
    # `openai/gpt-5-nano:batch` — eine Variante, die `kostenbuch.weg()` nicht kennt. Die
    # alte Bedingung haette daraus `openai/gpt-5-nano:batch:floor` gemacht, also einen
    # Namen, den es nicht gibt. Jede Endung nach dem letzten Schraegstrich ist eine
    # Variante; wer schon eine hat, bekommt keine zweite.
    letztes = modell.rsplit("/", 1)[-1]
    return modell if ":" in letztes else modell + ":floor"


DEFAULT_MODEL = mit_boden(_MODELL_ROH)


_BODEN: dict[str, tuple[float, float] | None] = {}
_BODEN_SPERRE = threading.Lock()


def bodendeckel(modell: str) -> tuple[float, float] | None:
    """Der guenstigste Endpunktpreis DIESES Modells, einmal je Prozess geholt.

    Ein fest eingebauter Deckel waere falsch: er gilt sonst auch fuer ein Modell, das
    jemand per OR_MODEL setzt, und sperrt womoeglich jeden Endpunkt aus. Aus dem Modell
    abgeleitet kann das nicht passieren — der eigene Bodenpreis ist per Definition
    erreichbar.
    """
    grund = kostenbuch.grundmodell(modell)
    with _BODEN_SPERRE:
        if grund in _BODEN:
            return _BODEN[grund]
    wert = None
    try:
        from govisor import modellkatalog as _mk
        b = _mk.bodenpreis(grund)
        if b:
            wert = (b["ein"], b["aus"])
    except Exception:                                    # noqa: BLE001
        wert = None                                      # kein Deckel ist besser als ein falscher
    with _BODEN_SPERRE:
        _BODEN[grund] = wert
    return wert


def _or_extra(modell: str | None = None) -> dict:
    """Der OpenRouter-`provider`-Block — Preisdeckel und Datenrichtlinie, beide optional.

    Die Endung `:floor` steckt im Modellnamen (s. DEFAULT_MODEL) und nicht hier; sie ist
    das Einzige, was den Flex-Endpunkt freischaltet. Dieser Block ergaenzt nur die Grenzen.
    """
    prov: dict = {}
    if not OR_MAX_PREIS and OR_STRENG != "aus" and modell:
        b = bodendeckel(modell)
        if b:
            prov["max_price"] = {"prompt": b[0], "completion": b[1]}
    if OR_MAX_PREIS:
        # „0.30/2.50" → {"prompt": 0.30, "completion": 2.50}, in $ je Mio Token.
        try:
            ein, _, aus = OR_MAX_PREIS.partition("/")
            prov["max_price"] = {"prompt": float(ein), "completion": float(aus or ein)}
        except ValueError:
            print(f"⚠ OR_MAX_PREIS unlesbar: {OR_MAX_PREIS!r} — erwartet 0.30/2.50. "
                  f"Es wird ohne Preisdeckel gefahren.", file=sys.stderr, flush=True)
    if OR_DATENSCHUTZ:
        prov["data_collection"] = OR_DATENSCHUTZ
    return {"provider": prov} if prov else {}


def available_keys() -> int:
    """Anzahl konfigurierter Keys ueber ALLE Anbieter, die (noch) nicht leer sind."""
    return sum(1 for a in _anbieter() for k in a["keys"] if k not in _EXHAUSTED)


@contextlib.contextmanager
def frist(sekunden: float | None):
    """Engere Gesamtfrist je Aufruf für den folgenden Abschnitt. ``None`` laesst OR_FRIST.

    Der Pruefstand nutzt das, um einen unbekannten Kandidaten kurz zu halten, ohne die
    Produktion anzufassen.
    """
    vorher = getattr(_FRIST, "s", None)
    if sekunden is not None:
        _FRIST.s = sekunden
    try:
        yield
    finally:
        _FRIST.s = vorher


def _post_mit_frist(url, headers, body, timeout, frist_s):
    """`requests.post` mit ECHTER Gesamtfrist. Gibt (antwort, None) oder (None, grund).

    ⚠ Der Faden wird bei Fristablauf **liegengelassen**, nicht abgebrochen — Python kann
    einen blockierten Socket-Lesevorgang nicht von aussen unterbrechen. Er laeuft aus und
    verschwindet. Das ist bewusst in Kauf genommen: ein liegengelassener Faden kostet
    Speicher, ein haengender Lauf kostet die Nacht.
    """
    if not frist_s:
        return requests.post(url, headers=headers, json=body, timeout=timeout), None
    kiste: dict = {}

    def hol():
        try:
            kiste["r"] = requests.post(url, headers=headers, json=body, timeout=timeout)
        except Exception as e:                           # noqa: BLE001
            kiste["e"] = e

    t = threading.Thread(target=hol, daemon=True)
    t.start()
    t.join(frist_s)
    if t.is_alive():
        return None, f"Frist von {frist_s:.0f} s überschritten"
    if "e" in kiste:
        raise kiste["e"]
    return kiste.get("r"), None


@contextlib.contextmanager
def kontext(*, zweck: str | None = None, vorgang: str | None = None):
    """Anlass der folgenden Aufrufe fuers Kostenbuch — je Faden, verschachtelbar.

    ::

        with llm.kontext(zweck="analyse", vorgang=notice_id):
            chat(...)

    ⚠ **Kein globales Umbiegen.** Derselbe Fehler wie beim Anbieter-Zwang (s. `chat`): der
    Analyse-Lauf faehrt vierzig Faeden, und eine gemeinsame Variable wuerde die Anlaesse
    untereinander vertauschen. Beim Verlassen wird der vorherige Stand zurueckgelegt, nicht
    geleert — sonst verliert ein aeusserer Block seinen Zweck an einen inneren.
    """
    vorher = (getattr(_KONTEXT, "zweck", None), getattr(_KONTEXT, "vorgang", None))
    if zweck is not None:
        _KONTEXT.zweck = zweck
    if vorgang is not None:
        _KONTEXT.vorgang = vorgang
    try:
        yield
    finally:
        _KONTEXT.zweck, _KONTEXT.vorgang = vorher


def _buchen(anbieter: str, modell: str, daten: dict, sekunden: float,
            leer: bool = False) -> None:
    """Preis, Weg und Dauer einer Antwort ins Kostenbuch.

    Die Kosten stehen seit der Umstellung der OpenRouter-Nutzungsabrechnung **immer** in der
    Antwort; ein Zusatzaufruf waere weder noetig noch bezahlbar (er kostet Zeit je Analyse).
    Fehlen sie doch, wird die Zeile trotzdem geschrieben — mit `kosten_usd: null`. Eine
    Luecke, die man zaehlen kann, ist besser als eine Zeile, die fehlt.
    """
    if not isinstance(daten, dict):
        return
    u = daten.get("usage") or {}
    if not isinstance(u, dict):
        u = {}
    det = u.get("cost_details") or {}
    pd = u.get("prompt_tokens_details") or {}
    kostenbuch.notiere(
        anbieter=anbieter, modell=modell,
        # OpenRouter nennt hier den Anbieter, der tatsaechlich geantwortet hat
        # („Google AI Studio"). Das ist die einzige Stelle, an der sich pruefen laesst,
        # ob `:floor` den Flex-Endpunkt wirklich getroffen hat.
        endpunkt=str(daten.get("provider") or ""),
        vorgang=getattr(_KONTEXT, "vorgang", None),
        zweck=getattr(_KONTEXT, "zweck", None),
        eingabe_token=u.get("prompt_tokens"),
        ausgabe_token=u.get("completion_tokens"),
        cache_token=(pd or {}).get("cached_tokens") if isinstance(pd, dict) else None,
        kosten_usd=u.get("cost"),
        upstream_usd=(det or {}).get("upstream_inference_cost") if isinstance(det, dict) else None,
        sekunden=sekunden, leer=leer)


def letzter_verbrauch() -> dict:
    """Preis, Endpunkt und Dauer des letzten erfolgreichen Aufrufs IN DIESEM FADEN."""
    return {"endpunkt": getattr(_LETZTER, "endpunkt", None),
            "kosten_usd": getattr(_LETZTER, "kosten_usd", None),
            "sekunden": getattr(_LETZTER, "sekunden", None)}


def letzter_anbieter() -> tuple[str | None, str | None]:
    """(Anbieter, Modell) des letzten erfolgreichen Aufrufs IN DIESEM FADEN."""
    return getattr(_LETZTER, "anbieter", None), getattr(_LETZTER, "modell", None)


def anbieter_stand() -> list[dict]:
    """Wer koennte gerade liefern? Fuer Betriebsanzeigen (s. /api/intern/lauf)."""
    return [{"name": a["name"], "modell": a["model"],
             "keys": len(a["keys"]),
             "frei": sum(1 for k in a["keys"] if k not in _EXHAUSTED)}
            for a in _anbieter()]


def _is_credit_error(status: int, text: str) -> bool:
    if status == 402:
        return True
    t = (text or "").lower()
    return status in (400, 403) and any(w in t for w in ("credit", "insufficient", "quota", "balance"))


# ── GELDWACHE ──────────────────────────────────────────────────────────────────────────
#
# ⚠ **Sie sitzt HIER und nicht im Aufrufer.** Bis zum 21.08. stand die einzige Bremse in
# `scripts/analyze_docs.py` (`BUDGET_USD`) — also im Produktionsweg. Jedes von Hand
# geschriebene Skript ging daran vorbei, und genau so ist an dem Abend ein Testlauf
# gestartet, der 1,71 $ verbraucht und **kein einziges verwertbares Ergebnis** geliefert
# hat: erst lief er in eine Zeitgrenze, dann in ein leeres Konto. `chat()` ist die Tuer,
# durch die jeder Aufruf geht; eine Bremse davor kann niemand versehentlich umgehen.
#
# Drei Grenzen, drei verschiedene Fehler:
#   · RESERVE  — was NIE ausgegeben wird. Schuetzt den Tagesbetrieb davor, dass ein
#                Versuch das Konto leerraeumt. Genau das ist passiert.
#   · LIMIT    — was EIN Prozess hoechstens ausgeben darf. Fängt Ausreisser und Schleifen.
#   · TAKT     — wie oft nachgefragt wird. Der Kontostand kostet einen HTTP-Aufruf; ihn vor
#                jedem Chat zu holen waere teurer als das, was er schuetzt.
RESERVE_USD = float(_os.environ.get("GOVISOR_RESERVE_USD", "1.00"))
# ⚠ **TAGESDECKEL — die Grenze, die die anderen beiden nicht ziehen.** Reserve und Limit
# schuetzen vor EINEM Ausreisser; sie sagen nichts darueber, wie viel ein Tag insgesamt
# kosten darf. Der Analyse-Arbeiter rechnet Runde fuer Runde, jede unter dem Lauf-Limit —
# und kam so am 22.08. auf ~11 $ an einem Tag, ohne dass irgendeine Bremse falsch lag.
# Bei 0,045 $ je Vorgang und einer offenen Beschaffungsluecke von ~5.983 Vergaben waeren
# das rund 271 $, die sonst niemand geplant haette.
# 6,00 $ statt der ersten 3,00 — gerechnet, nicht geraten. Zufluss ~233 Vergaben je
# Kalendertag (Fristen der naechsten 42 Tage durch 42; Gegenprobe ueber Bestand geteilt
# durch mittlere Laufzeit: 311). Kosten 0,048 $ je Vorgang (gemessen ueber 310 Vorgaenge).
# Bei der heutigen Abdeckung von 43 % sind das ~5,7 $/Tag mit 10 % Puffer; 3,00 $ reichten
# nicht einmal dafuer und wurden am 22.08. nach 4,02 $ gerissen, waehrend 886 Vorgaenge
# warteten. Bei VOLLER Abdeckung waeren es 12–16 $/Tag — dann traegt erst der Stapelweg
# (halber Preis) und der Dublettenwall (−22 %) die Rechnung.
TAG_USD = float(_os.environ.get("GOVISOR_TAG_USD", "6.00"))
LIMIT_USD = float(_os.environ.get("GOVISOR_LIMIT_USD", "5.00"))

# ── SCHONUNG: EIN TOPF, DEN DIE PRODUKTION NICHT ANRUEHRT ────────────────────────────
#
# Der Testtopf (`GOVISOR_TEST_USD`) begrenzt bisher nur den Pruefstand — er SCHUETZT ihn
# nicht. Beide teilen sich Reserve und Tagesdeckel, und der Analyse-Arbeiter laeuft alle
# 30 Sekunden, der Pruefstand einmal nachts. Wer zuerst da ist, nimmt alles.
#
# Genau das ist am 2026-08-23 passiert, nur andersherum: ein Versuch frass das Guthaben des
# Arbeiters auf, danach stand die Produktion, waehrend der Versuch weiterlief. Die Lehre
# war „getrennte Toepfe" — gebaut wurde aber nur eine Obergrenze fuer den einen, keine
# Untergrenze fuer den anderen.
#
# Die Schonung dreht es um: fuer ALLE Zwecke ausser dem Pruefstand liegen Reserve und
# Tagesdeckel um diesen Betrag straffer. Die Produktion haelt also frueher an und laesst
# dem Test sein Geld stehen — ohne dass irgendwo eine Reihenfolge verabredet werden muss.
SCHONUNG_USD = float(_os.environ.get("GOVISOR_SCHONUNG_USD", "0.50"))
GESCHONT = ("pruefstand", "bench")      # Zwecke, die aus dem geschonten Topf zahlen duerfen
_TAKT = int(_os.environ.get("GOVISOR_BUDGET_TAKT", "20"))

_geld_sperre = _threading.Lock()
_geld = {"start": None, "stand": None, "n": 0, "naechste": 1, "gewarnt": False, "stopp": None}


class BudgetErschoepft(RuntimeError):
    """Die Geldwache hat abgebrochen — kein Anbieterfehler, eine Entscheidung."""


def kontostand(frisch: bool = False) -> float | None:
    """Verbleibendes OpenRouter-Guthaben in Dollar. ``None``, wenn nicht ermittelbar.

    ⚠ Ueber `curl`, nicht ueber `urllib`. Auf dieser Maschine scheitert urllib an der
    TLS-Kette und gibt still `None` zurueck — eine Bremse, die still ausfaellt, ist
    schlimmer als keine, weil sie Sicherheit vortaeuscht.
    """
    if not frisch and _geld["stand"] is not None:
        return _geld["stand"]
    import json as _json
    import subprocess as _sp
    schluessel = _os.environ.get("OPENROUTER_API_KEY")
    if not schluessel:
        pfad = _Path(__file__).resolve().parent.parent / ".secrets" / "openrouter.key"
        if pfad.exists():
            schluessel = pfad.read_text(encoding="utf-8").strip()
    if not schluessel:
        return None
    try:
        r = _sp.run(["curl", "-s", "--max-time", "20", "-H",
                     f"Authorization: Bearer {schluessel}",
                     "https://openrouter.ai/api/v1/credits"],
                    capture_output=True, text=True, timeout=30)
        d = _json.loads(r.stdout)["data"]
        _geld["stand"] = float(d["total_credits"]) - float(d["total_usage"])
        return _geld["stand"]
    except Exception:                                         # noqa: BLE001
        return None


def _tagesbuch(stand: float) -> float:
    """Was HEUTE schon ausgegeben wurde, prozessuebergreifend.

    Gemerkt wird nicht die Summe, sondern der **erste Kontostand des Tages** — daraus
    ergibt sich der Verbrauch durch Subtraktion. Das ueberlebt parallele Prozesse ohne
    Sperre und ohne Addierfehler: es gibt nichts hochzuzaehlen, was doppelt gezaehlt
    werden koennte.

    ⚠ Ein Aufladen mitten am Tag setzt die Tagesrechnung faktisch zurueck (der Stand steigt
    ueber den Startwert). Das ist gewollt: wer nachlaedt, hat sich entschieden.
    """
    import datetime as _dt
    import json as _json

    pfad = _Path(__file__).resolve().parent.parent / "data" / ".llm_tagesbudget.json"
    heute = _dt.date.today().isoformat()
    try:
        d = _json.loads(pfad.read_text(encoding="utf-8"))
    except Exception:                                         # noqa: BLE001
        d = {}
    if d.get("datum") != heute:
        d = {"datum": heute, "start_stand": stand}
        try:
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_text(_json.dumps(d), encoding="utf-8")
        except Exception as e:                                # noqa: BLE001
            # ⚠ NICHT still verschlucken. Schlaegt das Schreiben fehl, legt der naechste
            # Aufruf das Buch neu an — mit dem dann niedrigeren Stand als Startwert. Der
            # Tagesdeckel misst danach nur noch, was seit diesem Moment ausgegeben wurde,
            # und greift nie. Genau so ist er am 22.08. lautlos ausgefallen: ein
            # Startwert von 8,03 $ verschwand, der naechste Aufruf schrieb 5,43 $, und
            # der Verbrauch dazwischen war aus der Rechnung.
            with _geld_sperre:
                if not _geld.get("buch_gewarnt"):
                    _geld["buch_gewarnt"] = True
                    print(f"  ⚠ Tagesbuch nicht schreibbar ({type(e).__name__}) — "
                          f"der Tagesdeckel ist AUS.", flush=True)
    return max(0.0, float(d.get("start_stand", stand)) - stand)


def _geldwache() -> None:
    """Vor jedem Chat. Wirft `BudgetErschoepft`, wenn Reserve oder Limit gerissen sind.

    ⚠ **Faellt der Kontostand nicht zu ermitteln, wird NICHT blockiert.** Ein Netzproblem
    darf den Tagesbetrieb nicht anhalten. Gewarnt wird trotzdem, einmal je Prozess — sonst
    laeuft man monatelang ohne Schutz und haelt sich fuer geschuetzt.

    ⚠ **Zwei Vorkehrungen gegen Ueberschwingen, beide aus einer Messung.** Die erste Fassung
    prueffte stur jeden 20. Aufruf. Am 2026-08-22 lief damit ein Test mit sechs Faeden und
    teuren Aufrufen auf **8,48 $ bei einem Limit von 5,00 $** — 3,48 $ daneben. Zwei Gruende:
      · Sechs Faeden kommen an der Pruefung vorbei, bevor einer abbricht → der Abbruch ist
        jetzt **klebrig**: einmal gefallen, wirft JEDER weitere Aufruf sofort, ohne Netz.
      · Ein fester Takt kennt den Preis nicht. Er richtet sich jetzt nach dem GEMESSENEN
        Preis je Aufruf: je weniger Luft bis zur Grenze, desto frueher die naechste Pruefung.
    """
    with _geld_sperre:
        if _geld["stopp"]:
            raise BudgetErschoepft(_geld["stopp"])
        _geld["n"] += 1
        n = _geld["n"]
        faellig = n >= _geld["naechste"]
        if faellig:
            # Sofort weitersetzen, damit parallele Faeden nicht alle zugleich pruefen.
            _geld["naechste"] = n + _TAKT
    if not faellig:
        return
    stand = kontostand(frisch=True)
    if stand is None:
        with _geld_sperre:
            if not _geld["gewarnt"]:
                _geld["gewarnt"] = True
                print("  ⚠ Kontostand nicht ermittelbar — die Geldwache ist AUS.", flush=True)
        return
    with _geld_sperre:
        if _geld["start"] is None:
            _geld["start"] = stand
            # ⚠ Den Startwert AUSGEBEN. Am 22.08. habe ich zweimal Verbrauch dem falschen
            # Verursacher zugeschrieben, weil ich den Kontostand vor dem Start gemessen
            # hatte statt beim Start — dazwischen lief ein anderer Prozess. Wer den Wert
            # im eigenen Protokoll hat, muss nicht raten.
            print(f"  Geldwache: Start bei {stand:.2f} $ "
                  f"(Reserve {RESERVE_USD:.2f} · Lauf {LIMIT_USD:.2f} · Tag {TAG_USD:.2f})",
                  flush=True)
        ausgegeben = _geld["start"] - stand
        # Preis je Aufruf aus dem, was tatsaechlich passiert ist — nicht aus einer Schaetzung.
        # Genau die Schaetzung lag am 22.08. um das Vierfache daneben.
        je_aufruf = ausgegeben / n if n and ausgegeben > 0 else 0.0
        # Fuer alles ausser dem Pruefstand liegen die Grenzen um die Schonung straffer.
        schonung = 0.0 if getattr(_KONTEXT, "zweck", None) in GESCHONT else SCHONUNG_USD
        luft = min(LIMIT_USD - ausgegeben if LIMIT_USD else float("inf"),
                   stand - RESERVE_USD - schonung,
                   TAG_USD - schonung - _tagesbuch(stand) if TAG_USD else float("inf"))
        if je_aufruf > 0:
            # Halbe Luft als Sicherheitsabstand: lieber einmal zu oft fragen als einmal
            # zu spaet. Ein Kontostand-Abruf kostet nichts ausser einer Sekunde.
            schritte = max(1, min(_TAKT, int(luft / je_aufruf / 2)))
        else:
            schritte = _TAKT
        _geld["naechste"] = n + schritte

        heute = _tagesbuch(stand)
        grund = None
        if TAG_USD and heute > TAG_USD - schonung:
            grund = (f"heute schon {heute:.2f} $ ausgegeben (Tagesdeckel {TAG_USD:.2f} $"
                     + (f" minus {schonung:.2f} $ Schonung für den Prüfstand" if schonung
                        else "") + ") — abgebrochen. Anheben: GOVISOR_TAG_USD")
        elif stand < RESERVE_USD + schonung:
            grund = (f"Guthaben {stand:.2f} $ unter der Reserve von "
                     f"{RESERVE_USD + schonung:.2f} $"
                     + (f" (davon {schonung:.2f} $ Schonung für den Prüfstand)"
                        if schonung else "") + " — "
                     f"abgebrochen, damit der Tagesbetrieb weiterlaufen kann. "
                     f"Aufladen: openrouter.ai/credits")
        if not grund and LIMIT_USD and ausgegeben > LIMIT_USD:
            grund = (f"dieser Lauf hat {ausgegeben:.2f} $ verbraucht (Limit {LIMIT_USD:.2f} $) "
                     f"— abgebrochen. Hoeher setzen: GOVISOR_LIMIT_USD")
        if grund:
            _geld["stopp"] = grund
    if grund:
        raise BudgetErschoepft(grund)


def probe(model: str | None = None) -> dict:
    """EIN billiger Aufruf, bevor ein Stapel startet — mit Kosten davor und danach.

    ⚠ Der Grund steht in der Geldwache oben: am 21.08. sind 80 Aufrufe losgelaufen, ohne
    dass je einer bewiesen hatte, dass die Mechanik traegt. Ein Cent vorher haette den
    ganzen Abend gerettet.
    """
    vorher = kontostand(frisch=True)
    antwort = chat([{"role": "user", "content": "Antworte nur mit: ok"}], model=model)
    nachher = kontostand(frisch=True)
    return {"antwort": (antwort or "").strip()[:40], "vorher": vorher, "nachher": nachher,
            "kosten": None if None in (vorher, nachher) else round(vorher - nachher, 4)}


class AllKeysExhausted(RuntimeError):
    pass


def chat(messages: list[dict], model: str | None = None, temperature: float = 0,
         timeout: int = 120, max_retries: int = 3, anbieter: str | None = None) -> str:
    """Chat-Completion mit Key- UND Anbieter-Rotation. Wirft erst, wenn niemand mehr kann.

    Reihenfolge: alle Keys des ersten Anbieters, dann der naechste Anbieter. Leeres Guthaben
    (402) mustert den Key prozessweit aus, 429 fuehrt zu kurzem Backoff und Wiederholung.

    `model` gilt nur fuer den passenden Anbieter: ein Name mit Schraegstrich („google/…")
    ist ein OpenRouter-Name und waere bei Cerebras ein Fehler. Ohne Angabe nimmt jeder
    Anbieter sein eigenes Standardmodell.
    """
    _geldwache()
    versuchte = 0
    last_err = "?"
    # `anbieter` zwingt EINEN Anbieter — fuer Vergleichsmessungen und fuer Verfahren, die
    # bewusst zwei verschiedene Haeuser befragen (scripts/entity_adjudicate.py).
    #
    # ⚠ WARUM ALS PARAMETER UND NICHT PER MONKEYPATCH. Genau das war der erste Entwurf: die
    # Aufrufstelle bog `_anbieter` global um und stellte es danach zurueck. Mit acht Faeden
    # sah ein Faden die Einschraenkung des anderen; im Ergebnis stand „perplexity nicht
    # verfuegbar", obwohl der Schluessel da war, und die halbe Messung war Unsinn. Globale
    # Umschaltung und Parallelitaet vertragen sich nicht, nie.
    liste = [a for a in _anbieter() if not anbieter or a["name"] == anbieter]
    for anb in liste:
        keys = [k for k in anb["keys"] if k not in _EXHAUSTED]
        if not keys:
            continue
        # ⚠ EIN MODELLNAME GILT NUR BEI SEINEM ANBIETER. Der erste Entwurf riet am
        # Schraegstrich („google/…" = OpenRouter) — das faellt spaetestens bei Together auf
        # die Nase, dessen Namen genauso aussehen („meta-llama/Llama-3.3-70B-Instruct-Turbo").
        # Ein von aussen gesetztes Modell (OR_MODEL) meint immer OpenRouter; die anderen
        # Anbieter nehmen ihr eigenes, sonst antwortet die Gegenstelle mit „model not found".
        modell = model if (model and anb["name"] == "openrouter") else anb["model"]
        # Der Preisdeckel haengt am tatsaechlich verwendeten Modell, nicht an der
        # Anbieterliste — deshalb hier und nicht in `_anbieter()`.
        extra = _or_extra(modell) if anb["name"] == "openrouter" else anb.get("extra", {})
        body = {"model": modell, "temperature": temperature, "messages": messages,
                **({"max_tokens": OR_MAX_TOKENS} if OR_MAX_TOKENS else {}),
                **extra}
        for key in keys:
            versuchte += 1
            ohne_deckel = False
            for attempt in range(max_retries):
                try:
                    t0 = time.time()
                    r, ueberzogen = _post_mit_frist(
                        anb["url"], {"Authorization": f"Bearer {key}",
                                     "Content-Type": "application/json"},
                        body, timeout, getattr(_FRIST, "s", None) or OR_FRIST)
                    if ueberzogen:
                        # ⚠ Der Aufruf wird oben zu Ende gerechnet und ABGERECHNET, auch
                        # wenn wir die Antwort nie sehen. Deshalb eine Zeile ohne Preis:
                        # sie erklaert spaeter die Luecke in `kostenbericht.py --abgleich`.
                        kostenbuch.notiere(
                            anbieter=anb["name"], modell=modell, endpunkt="",
                            vorgang=getattr(_KONTEXT, "vorgang", None),
                            zweck=getattr(_KONTEXT, "zweck", None),
                            kosten_usd=None, sekunden=time.time() - t0, abgebrochen=True)
                        last_err = f"{ueberzogen} ({anb['name']}/{modell})"
                        break                            # dieses Modell haengt — Key wechseln hilft nicht
                    if r.status_code == 200:
                        # ⚠ NICHT BLIND `["content"]`. Cerebras' gpt-oss-120b liefert
                        # `{"role","content","reasoning"}` und laesst `content` gelegentlich
                        # leer, wenn die Antwort im Denkteil steht. Gemessen am 2026-08-18:
                        # 2 von 5 Vorgaengen starben an `KeyError: 'content'` — und weil der
                        # Fehler wie ein Netzfehler aussah, wanderte der Lauf durch alle Keys
                        # und meldete am Ende „alle Anbieter erschoepft". Ein Formatunterschied
                        # als Guthabenproblem verkleidet: die teuerste Sorte Fehlermeldung.
                        daten = r.json()
                        m = (daten.get("choices") or [{}])[0].get("message") or {}
                        inhalt = m.get("content") or m.get("reasoning") or ""
                        if inhalt.strip():
                            dauer = time.time() - t0
                            _LETZTER.anbieter = anb["name"]
                            # ⚠ OHNE ROUTING-ENDUNG festhalten. `analyze_docs` schreibt
                            # diesen Namen in jeden Datensatz, und `llm_qualitaet.py`
                            # gruppiert danach. Stuende hier „…flash:floor", zerfiele die
                            # Historie desselben Modells in zwei Reihen — und der
                            # Vorher-Nachher-Vergleich, um den es beim Boden gerade geht,
                            # waere genau dadurch unmoeglich.
                            _LETZTER.modell = kostenbuch.grundmodell(modell)
                            _LETZTER.endpunkt = str(daten.get("provider") or "")
                            _u = daten.get("usage") or {}
                            _LETZTER.kosten_usd = _u.get("cost") if isinstance(_u, dict) else None
                            _LETZTER.sekunden = dauer
                            _buchen(anb["name"], modell, daten, dauer)
                            return inhalt
                        # ⚠ AUCH LEERE ANTWORTEN KOSTEN GELD. Ein 200 ohne verwertbaren
                        # Inhalt wird von OpenRouter trotzdem abgerechnet — die Tokens sind
                        # erzeugt worden. Die erste Fassung buchte hier nicht und das Buch
                        # meldete am 2026-08-23 rund 20 % weniger, als das Konto verlor.
                        _buchen(anb["name"], modell, daten, time.time() - t0, leer=True)
                        last_err = f"leere Antwort ({anb['name']})"
                        continue
                    if _is_credit_error(r.status_code, r.text):
                        with _LOCK:
                            _EXHAUSTED.add(key)
                        last_err = f"402/Guthaben leer ({anb['name']}, …{key[-6:]})"
                        break                       # dieser Key ist durch → naechster Key
                    if r.status_code == 429:
                        last_err = f"429 Rate-Limit ({anb['name']})"
                        time.sleep(2 * (attempt + 1))
                        continue
                    # ⚠ 4xx IST KEIN GUTHABEN-PROBLEM. „Kontext zu lang", „Modell nicht
                    # verfuegbar", „unbekannter Parameter" — dreimal wiederholen aendert
                    # daran nichts, und am Ende meldete der Lauf „alle Anbieter erschoepft".
                    # Gemessen am 2026-08-18 im Modellvergleich: Cerebras und ein
                    # Together-Modell fielen so aus, und die Ursache stand nirgends. Ein
                    # Anbieterfehler gehoert sofort weitergereicht, mit Klartext.
                    # ⚠ EINMAL OHNE DECKEL NACHFASSEN. Wenn der billigste Endpunkt gerade
                    # niemanden hat, antwortet OpenRouter mit „no allowed providers". Den
                    # Lauf daran scheitern zu lassen waere schlimmer als der doppelte
                    # Preis — aber es gehoert sichtbar ins Buch, wie oft das passiert.
                    if (400 <= r.status_code < 500 and extra.get("provider", {}).get("max_price")
                            and "provider" in r.text.lower() and not ohne_deckel):
                        ohne_deckel = True
                        body.pop("provider", None)
                        last_err = f"Preisdeckel liess niemanden zu ({anb['name']}) — einmal ohne"
                        continue
                    last_err = f"HTTP {r.status_code} ({anb['name']}/{modell}): {r.text[:140]}"
                    if 400 <= r.status_code < 500:
                        break
                except Exception as e:              # Netz/Timeout → Retry
                    last_err = f"{type(e).__name__}: {str(e)[:80]}"
                    time.sleep(2 * (attempt + 1))
    wer = anbieter or "alle Anbieter"
    raise AllKeysExhausted(f"Alle {versuchte} Keys ({wer}) fehlgeschlagen — zuletzt: {last_err}")
