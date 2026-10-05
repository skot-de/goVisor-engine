"use client";
import { useCallback, useEffect, useRef, useState } from "react";

/* Antwortvorschlaege zu einem Fragebogen (Funktion 1 der Go-live-Liste, Oberflaeche).
 *
 * Der Nutzer fuegt den Fragenteil des Bogens ein, die Route legt einen Auftrag ab
 * (`/api/antwortauftrag`), `scripts/antwort_arbeiter.py` rechnet, diese Ansicht fragt nach und
 * zeigt das Ergebnis zur Pruefung. Warum nicht sofort geantwortet wird, steht im Kopf der Route.
 *
 * ⚠ DIE WICHTIGSTE REGEL DIESER ANSICHT: `unbelegt` darf NICHT wie `fertig` aussehen.
 * Ein Entwurf, dessen Beleg nicht haelt, ist gefaehrlicher als keiner, weil er sich fertig
 * anfuehlt. Er wird deshalb getrennt eingeordnet, bekommt eine andere Farbe, nennt den Mangel und
 * hat KEINEN Uebernehmen-Knopf. Die Kopfzahl zaehlt ausschliesslich `fertig`.
 *
 * ⚠ Keine Gedankenstriche in den Texten dieser Datei (Vorgabe Sven).
 */

type Beleg = { baustein: string; zitat: string };
type Vorschlag = {
  frage: { nr: string | null; frage: string };
  status: "fertig" | "unbelegt" | "kein_baustein";
  antwort: string;
  belege: Beleg[];
  maengel: string[];
};
type Zaehlung = { fertig: number; unbelegt: number; kein_baustein: number };
type Auftrag = {
  id: string; status: "offen" | "laeuft" | "fertig" | "fehler";
  zaehlung: Zaehlung | null; fragen_gesamt: number | null; fehler: string | null;
};
type Ergebnis = { vorschlaege: Vorschlag[]; zaehlung: Zaehlung; fragen_gesamt: number;
                  fertig: number; hinweis?: string };

const MIN_TEXT = 40;
const TAKT_MS = 3000;

const BESCHRIFTUNG: Record<Vorschlag["status"], string> = {
  fertig: "belegt",
  unbelegt: "Beleg haelt nicht",
  kein_baustein: "kein passender Baustein",
};

export function Antwortvorschlaege({ leadId }: { leadId?: string }) {
  const [text, setText] = useState("");
  const [auftrag, setAuftrag] = useState<Auftrag | null>(null);
  const [ergebnis, setErgebnis] = useState<Ergebnis | null>(null);
  const [fehler, setFehler] = useState("");
  const [hinweis, setHinweis] = useState("");
  const [quelle, setQuelle] = useState("");     // Dateiname, fuer den Dokumenttitel
  const [busy, setBusy] = useState(false);
  const uhr = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stoppen = useCallback(() => {
    if (uhr.current) { clearTimeout(uhr.current); uhr.current = null; }
  }, []);

  /* ⚠ Aufraeumen beim Verlassen. Ohne das laeuft die Abfrage weiter, nachdem die Ansicht weg
   * ist, und schreibt in einen Zustand, den React verworfen hat. */
  useEffect(() => stoppen, [stoppen]);

  const nachfragen = useCallback(async (id: string) => {
    try {
      const r = await fetch(`/api/antwortauftrag?id=${encodeURIComponent(id)}`);
      const d = await r.json();
      if (d.error) { setFehler(d.error); setBusy(false); return; }
      setAuftrag(d.auftrag);
      if (d.auftrag?.status === "fertig") {
        setErgebnis(d.ergebnis ?? null);
        setBusy(false);
        return;
      }
      if (d.auftrag?.status === "fehler") {
        setFehler(d.auftrag.fehler || "Der Auftrag ist gescheitert.");
        setBusy(false);
        return;
      }
      uhr.current = setTimeout(() => nachfragen(id), TAKT_MS);
    } catch {
      /* Netz weg: nicht aufgeben, der Auftrag laeuft auf dem Server weiter. Ein Abbruch hier
       * saehe fuer den Nutzer wie ein verlorener Auftrag aus, und er wuerde ihn neu stellen,
       * also doppelt zahlen. */
      uhr.current = setTimeout(() => nachfragen(id), TAKT_MS * 2);
    }
  }, []);

  /* Beide Wege, Text und Datei, enden hier: Auftrag merken und nachfragen. */
  async function abschicken(rumpf: BodyInit, kopf?: HeadersInit) {
    setBusy(true); setFehler(""); setHinweis(""); setErgebnis(null); setAuftrag(null);
    try {
      const r = await fetch("/api/antwortauftrag", { method: "POST", headers: kopf, body: rumpf });
      const d = await r.json();
      if (d.error || !d.auftrag) {
        setFehler(d.error || "Der Auftrag konnte nicht angelegt werden.");
        setBusy(false);
        return;
      }
      if (d.hinweis) setHinweis(d.hinweis);
      setAuftrag(d.auftrag);
      uhr.current = setTimeout(() => nachfragen(d.auftrag.id), TAKT_MS);
    } catch {
      setFehler("Der Auftrag konnte nicht angelegt werden.");
      setBusy(false);
    }
  }

  function starten() {
    if (text.trim().length < MIN_TEXT) {
      setFehler(`Bitte mindestens ${MIN_TEXT} Zeichen einfuegen.`);
      return;
    }
    setQuelle("");
    abschicken(JSON.stringify({ text, lead_id: leadId ?? null }),
               { "content-type": "application/json" });
  }

  /* ⚠ Kein `content-type` setzen. Der Browser muss ihn fuer FormData selbst erzeugen, weil er
   * die Abschnittsgrenze enthaelt; ein von Hand gesetzter Wert macht die Anfrage unlesbar. */
  function dateiGewaehlt(e: React.ChangeEvent<HTMLInputElement>) {
    const datei = e.target.files?.[0];
    e.target.value = "";          // damit dieselbe Datei erneut gewaehlt werden kann
    if (!datei) return;
    setQuelle(datei.name.replace(/\.[a-z0-9]{1,5}$/i, ""));
    const fd = new FormData();
    fd.append("datei", datei);
    if (leadId) fd.append("lead_id", leadId);
    abschicken(fd);
  }

  const laeuft = busy || auftrag?.status === "offen" || auftrag?.status === "laeuft";

  return (
    <section className="antw">
      <h2 className="antw-titel">Antwortvorschlaege aus Ihren Bausteinen</h2>
      <p className="antw-hilfe">
        Laden Sie den Fragebogen als Excel oder PDF hoch, oder fuegen Sie den Fragenteil als
        Text ein. Zu jeder Frage entsteht ein Entwurf, der ausschliesslich aus Ihren eigenen
        Bausteinen gebaut wird.
      </p>

      <div className="antw-datei">
        <label className={`antw-dateiknopf${laeuft ? " antw-aus" : ""}`}>
          Datei waehlen
          <input type="file" accept=".xlsx,.xlsm,.pdf,.txt,.csv,.tsv"
            onChange={dateiGewaehlt} disabled={laeuft} hidden />
        </label>
        <span className="antw-dateihilfe">
          Excel oder PDF, bis 4 MB. Die Datei wird ausgelesen und nicht gespeichert.
          Ein eingescannter Bogen enthaelt keinen Text, dort hilft nur Einfuegen.
        </span>
      </div>

      <textarea className="antw-eingabe" value={text} rows={8}
        placeholder={"1. Bitte beschreiben Sie Ihr Qualitaetsmanagementsystem.\n"
          + "2. Welche Referenzen koennen Sie vorweisen?"}
        onChange={(e) => setText(e.target.value)} disabled={laeuft} />

      <div className="antw-leiste">
        <button className="antw-knopf" onClick={starten} disabled={laeuft}>
          {laeuft ? "Entwuerfe entstehen" : "Entwuerfe erzeugen"}
        </button>
        {laeuft && auftrag && (
          <span className="antw-lauf">
            {auftrag.status === "offen" ? "in der Warteschlange" : "wird bearbeitet"}
          </span>
        )}
        {fehler && <span className="antw-fehler">{fehler}</span>}
        {hinweis && !fehler && <span className="antw-lauf">{hinweis}</span>}
      </div>

      {ergebnis && <Ergebnisteil ergebnis={ergebnis} titel={dokumentTitel(quelle)} />}
    </section>
  );
}

/** Titel des Dokuments, das aus diesem Lauf entsteht. Nie leer, nie zweimal derselbe. */
function dokumentTitel(quelle: string): string {
  const tag = new Date().toLocaleDateString("de-DE");
  return quelle ? `Antworten ${quelle} (${tag})` : `Antworten vom ${tag}`;
}

function Ergebnisteil({ ergebnis, titel }: { ergebnis: Ergebnis; titel: string }) {
  const z = ergebnis.zaehlung;
  const nachStatus = (s: Vorschlag["status"]) => ergebnis.vorschlaege.filter(v => v.status === s);
  const [uebertrag, setUebertrag] = useState<"" | "laeuft" | "fehler">("");
  const [dokId, setDokId] = useState("");

  /* Die belegten Vorschlaege als Dokument ablegen (Phase 3). Damit schliesst sich der Kreis:
   * Fragebogen rein, geprueftes Dokument raus, von dort Word oder PDF.
   *
   * ⚠ NUR `fertig`, nie `unbelegt` — dieselbe Regel wie in der Anzeige. Ein Entwurf, dessen
   * Beleg nicht haelt, darf nicht ueber den Umweg Dokument doch noch in ein Angebot geraten.
   * Deshalb filtert diese Funktion selbst und verlaesst sich nicht darauf, dass der Knopf
   * nur zum richtigen Zeitpunkt sichtbar ist.
   *
   * ⚠ ABWEICHUNG VOM PLAN, bewusst: `docs/funktion-dokument-bauen.md` sagte „mitsamt Beleg".
   * Dafuer gaebe es im Dokument kein Feld, und der Beleg gehoert in die PRUEFUNG, nicht in die
   * Ausgabe; im abgegebenen Angebot waere er peinlich. Die Rueckverfolgung entsteht stattdessen
   * ueber die Form: jede Frage wird zur Ueberschrift, die Antwort steht darunter. Wer spaeter
   * wissen will, woher ein Absatz kommt, sieht die Frage ueber ihm. Steht im Plan nachgetragen.
   *
   * ⚠ Als Teile der Art `text`, NICHT als Baustein-Verweise. Der Entwurf ist aus mehreren
   * Bausteinen zusammengesetzt und vom Modell umformuliert; ein Verweis waere eine Luege ueber
   * seine Herkunft, und eine spaetere Baustein-Aenderung wuerde eine abgegebene Antwort
   * ruecklaufend veraendern.
   */
  async function insDokument() {
    const teile = nachStatus("fertig").flatMap((v) => ([
      { art: "ueberschrift", ebene: 2,
        inhalt: `${v.frage.nr ? `${v.frage.nr}. ` : ""}${v.frage.frage}` },
      { art: "text", inhalt: v.antwort },
    ]));
    if (!teile.length) return;
    setUebertrag("laeuft");
    try {
      const r = await fetch("/api/dokument", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ titel, teile }),
      });
      const d = await r.json();
      if (d.error || !d.dokument) { setUebertrag("fehler"); return; }
      setDokId(d.dokument.id);
      setUebertrag("");
    } catch { setUebertrag("fehler"); }
  }

  return (
    <div className="antw-ergebnis">
      {/* ⚠ Die Kopfzahl zaehlt NUR `fertig`. Ein `unbelegt` als halben Erfolg zu verbuchen
          waere die Schoenrechnung, die das Versprechen dieses Produkts aushoehlt. */}
      <p className="antw-summe">
        <strong>{ergebnis.fertig} von {ergebnis.fragen_gesamt} Fragen belegt vorbereitet.</strong>
        {z.unbelegt > 0 && <> {z.unbelegt} Entwurf
          {z.unbelegt === 1 ? "" : "e"} ohne haltbaren Beleg.</>}
        {z.kein_baustein > 0 && <> {z.kein_baustein} ohne passenden Baustein.</>}
      </p>
      {ergebnis.hinweis && <p className="antw-hinweis">{ergebnis.hinweis}</p>}

      {/* Uebergang ins Dokument. Erscheint nur, wenn es etwas Belegtes zu uebernehmen gibt. */}
      {ergebnis.fertig > 0 && (
        <div className="antw-uebernahme">
          {dokId ? (
            <>
              <span className="antw-uebernahme-ok">
                Dokument angelegt: {ergebnis.fertig} Antwort{ergebnis.fertig === 1 ? "" : "en"}
                {" "}uebernommen.
              </span>
              <a className="antw-knopf" href={`/dokumente?id=${encodeURIComponent(dokId)}`}>
                Dokument oeffnen
              </a>
            </>
          ) : (
            <>
              <button className="antw-knopf" onClick={insDokument}
                      disabled={uebertrag === "laeuft"}>
                {uebertrag === "laeuft" ? "wird angelegt" : "Als Dokument anlegen"}
              </button>
              <span className="antw-dateihilfe">
                Nur die {ergebnis.fertig} belegten Antworten wandern mit. Im Dokument koennen Sie
                sie umstellen, ergaenzen und als Word oder PDF ausgeben.
              </span>
            </>
          )}
          {uebertrag === "fehler" && (
            <span className="antw-fehler">Das Dokument konnte nicht angelegt werden.</span>
          )}
        </div>
      )}

      {nachStatus("fertig").map((v, i) => <Karte key={`f${i}`} v={v} />)}

      {nachStatus("unbelegt").length > 0 && (
        <>
          <h3 className="antw-abschnitt">Pruefen Sie diese selbst</h3>
          <p className="antw-hilfe">
            Hier stimmt der Beleg nicht mit dem Baustein ueberein. Der Entwurf steht da, damit
            Sie ihn beurteilen koennen, aber er ist nicht geprueft und nicht uebernehmbar.
          </p>
          {nachStatus("unbelegt").map((v, i) => <Karte key={`u${i}`} v={v} />)}
        </>
      )}

      {nachStatus("kein_baustein").length > 0 && (
        <>
          <h3 className="antw-abschnitt">Dafuer fehlt ein Baustein</h3>
          <ul className="antw-offen">
            {nachStatus("kein_baustein").map((v, i) => (
              <li key={`k${i}`}>{v.frage.nr ? `${v.frage.nr}. ` : ""}{v.frage.frage}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Karte({ v }: { v: Vorschlag }) {
  const [kopiert, setKopiert] = useState(false);
  async function kopieren() {
    try {
      await navigator.clipboard.writeText(v.antwort);
      setKopiert(true);
      setTimeout(() => setKopiert(false), 2000);
    } catch { /* Zwischenablage gesperrt: der Text steht sichtbar da, Markieren geht immer. */ }
  }
  return (
    <article className={`antw-karte antw-${v.status}`}>
      <header className="antw-kopf">
        <span className="antw-frage">
          {v.frage.nr ? `${v.frage.nr}. ` : ""}{v.frage.frage}
        </span>
        <span className={`antw-marke antw-marke-${v.status}`}>{BESCHRIFTUNG[v.status]}</span>
      </header>
      <p className="antw-antwort">{v.antwort}</p>

      {v.belege.length > 0 && (
        <details className="antw-belege">
          <summary>Woher das kommt ({v.belege.length})</summary>
          <ul>
            {v.belege.map((b, i) => (
              <li key={i}><code>{b.baustein}</code>: „{b.zitat}"</li>
            ))}
          </ul>
        </details>
      )}

      {v.maengel.length > 0 && (
        <ul className="antw-maengel">
          {v.maengel.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}

      {/* Uebernehmen gibt es nur fuer Geprueftes. */}
      {v.status === "fertig" && (
        <button className="antw-kopieren" onClick={kopieren}>
          {kopiert ? "kopiert" : "Text kopieren"}
        </button>
      )}
    </article>
  );
}
