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

  async function starten() {
    if (text.trim().length < MIN_TEXT) {
      setFehler(`Bitte mindestens ${MIN_TEXT} Zeichen einfuegen.`);
      return;
    }
    setBusy(true); setFehler(""); setErgebnis(null); setAuftrag(null);
    try {
      const r = await fetch("/api/antwortauftrag", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ text, lead_id: leadId ?? null }),
      });
      const d = await r.json();
      if (d.error || !d.auftrag) {
        setFehler(d.error || "Der Auftrag konnte nicht angelegt werden.");
        setBusy(false);
        return;
      }
      setAuftrag(d.auftrag);
      uhr.current = setTimeout(() => nachfragen(d.auftrag.id), TAKT_MS);
    } catch {
      setFehler("Der Auftrag konnte nicht angelegt werden.");
      setBusy(false);
    }
  }

  const laeuft = busy || auftrag?.status === "offen" || auftrag?.status === "laeuft";

  return (
    <section className="antw">
      <h2 className="antw-titel">Antwortvorschlaege aus Ihren Bausteinen</h2>
      <p className="antw-hilfe">
        Fuegen Sie den Fragenteil des Fragebogens ein, eine Frage je Zeile. Aus einer
        Excel-Tabelle genuegt die Spalte mit den Fragen. Zu jeder Frage entsteht ein Entwurf,
        der ausschliesslich aus Ihren eigenen Bausteinen gebaut wird.
      </p>

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
      </div>

      {ergebnis && <Ergebnisteil ergebnis={ergebnis} />}
    </section>
  );
}

function Ergebnisteil({ ergebnis }: { ergebnis: Ergebnis }) {
  const z = ergebnis.zaehlung;
  const nachStatus = (s: Vorschlag["status"]) => ergebnis.vorschlaege.filter(v => v.status === s);

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
