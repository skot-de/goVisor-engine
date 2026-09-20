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
import { useSprache } from "@/lib/i18n";

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
  const { t } = useSprache();
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

  if (dateien === null) return <p className="dok-laedt">{t("Unterlagen werden gelesen …")}</p>;

  if (!dateien.length) {
    return (
      <div className="dok-leer">
        <b>{t("Keine Unterlagen abgelegt.")}</b>{" "}
        {/* Der Grund gehoert dazu: „keine" kann heissen „noch nicht geholt", „Portal gibt
            nichts heraus" oder „hier gibt es keine Dateien". Ohne Unterscheidung sucht
            man an der falschen Stelle.

            ⚠ ZWEI FALLEN AUF EINMAL, gemeldet von Sven am 2026-09-20 („super viele
            tippfehler"): `<b>` und `<span>` sind Inline-Elemente und standen ohne
            Trennung nebeneinander — im Browser wurde daraus „abgelegt.keine". Und der
            Grund aus `lead_dokumente.py` lautete woertlich „keine Unterlagen abgelegt",
            also derselbe Satz noch einmal. Ein Grund, der den Zustand wiederholt, ist
            keiner. */}
        <span>{grund || t("Für diese Vergabe liegt bei uns kein Archiv.")}</span>
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

  /* ⚠ ZUGEKLAPPT, NICHT WEG. Sven am 2026-09-20: „den dokumenten index muessen wir anders
     machen, der nimmt im zweifel super viel platz". Gemessen ueber 293 Vorgaenge mit
     abgelegten Unterlagen: Median 19 Dateien, p90 35, Maximum 99 — als offene Liste 911 px,
     also der ganze erste Bildschirm, bevor die Auswertung anfaengt.

     Die Kopfzeile traegt deshalb die Gruppen samt Anzahl. Wer wissen will, OB ein
     Leistungsverzeichnis dabei ist, sieht es ohne zu klicken; wer die Datei braucht, klappt
     auf. Das war der Grund, warum die Liste urspruenglich VOR der Analyse stand, und der
     bleibt gueltig. */
  return (
    <details className="dk">
      <summary>
        {/* Der Pfeil ist die Ansage: hier geht etwas auf. Ohne ihn liest sich die Zeile
            wie eine Ueberschrift. */}
        <span className="dk-pfeil" aria-hidden="true">›</span>
        <b>{dateien.length === 1 ? t("1 Datei") : t("{n} Dateien", { n: dateien.length })}</b>
        <span className="dk-ges">· {groesse(gesamt)}</span>
        <span className="dk-chips">
          {RANG.map((r) => nachGruppe.get(r.name)?.length
            ? <span key={r.name} className="dk-g">{t(r.name)}<b>{nachGruppe.get(r.name)!.length}</b></span>
            : null)}
        </span>
        {/* ⚠ „ungefiltert" ist kein Beiwerk: hier greift KEINE PII-Schwaerzung, anders als
            beim extrahierten Text. Wer die Datei oeffnet, muss wissen, dass es das Original
            ist. Deshalb steht der Satz in der IMMER sichtbaren Kopfzeile, nicht im Inneren. */}
        <span className="dk-roh">{t("Original, ungefiltert")}</span>
        <span className="dk-auf">{t("alle zeigen")}</span>
      </summary>
      <div className="dk-body">
        {RANG.map((r) => {
          const liste = nachGruppe.get(r.name);
          if (!liste?.length) return null;
          return (
            <section key={r.name}>
              <div className="dk-h">{t(r.name)}<span>{liste.length}</span></div>
              {liste.sort((a, b) => a.name.localeCompare(b.name, "de")).map((d) => {
                const url = `/api/lead/datei?lead=${encodeURIComponent(leadId)}`
                          + `&datei=${encodeURIComponent(d.pfad)}`;
                /* ⚠ DER DATEINAME ZUERST, DER ORDNER DAHINTER. Gemessen an 3.160 Dateien
                   tragen 74 % der Eintraege einen Ordnerpfad vor dem Namen; der Eintrag ist
                   damit im Median 58 statt 39 Zeichen lang, und in einer Liste steht
                   derselbe Pfad zehnmal untereinander. Der Pfad bleibt sichtbar, er sagt
                   etwas (etwa „vom_unternehmen_auszufuellende_dokumente") — aber leise. */
                const teile = String(d.name).replace(/\\/g, "/").split("/");
                const datei = teile.pop() || d.name;
                const ordner = teile.join("/");
                return (
                  <div key={d.pfad + d.archiv} className="dk-z">
                    {d.gesperrt ? (
                      // Ausfuehrbares wird gar nicht erst verlinkt — nicht als Download,
                      // nicht als Ansicht. Sichtbar bleibt es trotzdem: markieren statt
                      // filtern, sonst wundert sich jemand ueber die fehlende Datei.
                      <span className="dk-n dok-gesperrt" title={t("Dateityp wird nicht ausgeliefert")}>{datei}</span>
                    ) : (
                      <a className="dk-n" href={url} target="_blank" rel="noopener noreferrer">{datei}</a>
                    )}
                    <span className="dk-o">{ordner}</span>
                    <span className="dk-m">
                      {d.fehler ? d.fehler : `${d.endung.replace(".", "") || "?"} · ${groesse(d.bytes)}`}
                    </span>
                  </div>
                );
              })}
            </section>
          );
        })}
      </div>
    </details>
  );
}

export default Dokumente;
