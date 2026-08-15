"use client";
/**
 * Die Vergabeunterlagen eines Leads — zum Ansehen, nicht nur zum Auswerten.
 *
 * **Warum es das gibt.** Wir laden die Unterlagen herunter, lesen sie aus und zeigen die
 * daraus abgeleiteten Aussagen — das Dokument selbst konnte man nie öffnen. Für einen Teil
 * des Bestands ist das die falsche Reihenfolge: gemessen 2026-08-15 sind **30 % der
 * bildreinen PDFs Pläne und Zeichnungen** und nur 2 % Fotodokumentation. Einen Lageplan
 * will man sehen; OCR machte daraus bestenfalls versprengte Beschriftungen.
 *
 * **Sortierung nach Nutzen, nicht nach Alphabet.** Wer eine Ausschreibung prüft, sucht
 * zuerst Leistungsverzeichnis und Aufforderung, nicht „Anlage 14b". Die Reihenfolge hier
 * ist deshalb eine Aussage darüber, was zuerst gebraucht wird — und keine Dateiliste.
 */
import { useEffect, useState } from "react";

type Datei = {
  archiv: string; pfad: string; name: string; endung: string;
  bytes: number; anzeigbar: boolean; gesperrt: boolean; fehler?: string;
};

/** Reihenfolge = Nutzen beim Prüfen einer Ausschreibung. Wer hier etwas ergänzt, ergänzt
 *  eine Behauptung darüber, was ein Bieter zuerst braucht. */
const RANG: { name: string; muster: RegExp }[] = [
  { name: "Leistung", muster: /lv|leistungsverz|leistungsbeschr|\.x8|\.d8|\.p8|gaeb/i },
  { name: "Aufforderung & Angebot", muster: /aufforder|angebot|anschreiben|bewerbung/i },
  { name: "Eignung & Nachweise", muster: /eignung|nachweis|erklaer|erklär|referenz|verpflicht/i },
  { name: "Vertrag & Bedingungen", muster: /vertrag|bedingung|avb|zvb|bvb|vob/i },
  { name: "Pläne & Zeichnungen", muster: /plan|zeichnung|lageplan|grundriss|schnitt|detail|\.dwg/i },
  { name: "Weitere Unterlagen", muster: /.*/ },
];

function gruppe(d: Datei): string {
  const k = `${d.pfad} ${d.name}`;
  return (RANG.find((r) => r.muster.test(k)) || RANG[RANG.length - 1]).name;
}

function groesse(b: number): string {
  if (b >= 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  if (b >= 1e3) return `${Math.round(b / 1e3)} KB`;
  return `${b} B`;
}

export function Dokumente({ leadId }: { leadId: string }) {
  const [dateien, setDateien] = useState<Datei[] | null>(null);
  const [grund, setGrund] = useState<string | null>(null);

  useEffect(() => {
    let abbruch = false;
    setDateien(null); setGrund(null);
    fetch(`/api/lead/dokumente?lead=${encodeURIComponent(leadId)}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { if (!abbruch) { setDateien(d.dateien || []); setGrund(d.grund || null); } })
      .catch((e) => { if (!abbruch) { setDateien([]); setGrund(String(e.message || e)); } });
    return () => { abbruch = true; };
  }, [leadId]);

  if (dateien === null) return <p className="dok-laedt">Unterlagen werden gelesen …</p>;

  if (!dateien.length) {
    return (
      <div className="dok-leer">
        <b>Keine Unterlagen abgelegt.</b>
        {/* Der Grund gehoert dazu: „keine" kann heissen „noch nicht geholt", „Portal gibt
            nichts heraus" oder „hier gibt es keine Dateien". Ohne Unterscheidung sucht
            man an der falschen Stelle. */}
        <span>{grund || "Für diese Vergabe liegt bei uns kein Archiv."}</span>
      </div>
    );
  }

  const nachGruppe = new Map<string, Datei[]>();
  for (const d of dateien) {
    const g = gruppe(d);
    if (!nachGruppe.has(g)) nachGruppe.set(g, []);
    nachGruppe.get(g)!.push(d);
  }
  const gesamt = dateien.reduce((s, d) => s + d.bytes, 0);

  return (
    <div className="dok-block">
      <p className="dok-kopf">
        <b>{dateien.length}</b> Datei{dateien.length === 1 ? "" : "en"} · {groesse(gesamt)}
        <span className="dok-hinweis">Original aus dem Vergabeportal — ungefiltert.</span>
      </p>

      {RANG.map((r) => {
        const liste = nachGruppe.get(r.name);
        if (!liste?.length) return null;
        return (
          <section key={r.name} className="dok-gruppe">
            <h4>{r.name}<span>{liste.length}</span></h4>
            <ul>
              {liste.sort((a, b) => a.name.localeCompare(b.name, "de")).map((d) => {
                const url = `/api/lead/datei?lead=${encodeURIComponent(leadId)}`
                          + `&datei=${encodeURIComponent(d.pfad)}`;
                return (
                  <li key={d.pfad + d.archiv}>
                    {d.gesperrt ? (
                      // Ausfuehrbares wird gar nicht erst verlinkt — nicht als Download,
                      // nicht als Ansicht. Sichtbar bleibt es trotzdem: markieren statt
                      // filtern, sonst wundert sich jemand ueber die fehlende Datei.
                      <span className="dok-gesperrt" title="Dateityp wird nicht ausgeliefert">
                        {d.name}
                      </span>
                    ) : (
                      <a href={url} target="_blank" rel="noopener noreferrer">{d.name}</a>
                    )}
                    <span className="dok-meta">
                      {d.fehler ? d.fehler : `${d.endung.replace(".", "") || "?"} · ${groesse(d.bytes)}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export default Dokumente;
