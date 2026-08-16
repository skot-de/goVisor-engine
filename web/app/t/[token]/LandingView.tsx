"use client";

import Link from "next/link";
import { useSprache } from "@/lib/i18n";
import type { Baustein, Landing, Zeile } from "@/lib/outreach";

/* Client-Hälfte der Outreach-Landing (die Server-Hälfte liegt in `page.tsx`).
 *
 * **Warum überhaupt geteilt.** `page.tsx` liest die vorberechnete `outreach.json` vom
 * Dateisystem und muss deshalb Server-Komponente bleiben. Die Oberflächensprache steht
 * aber im `localStorage` des Browsers, und `useSprache` ist ein Hook, den es auf dem
 * Server schlicht nicht gibt. Also lädt der Server die Daten und reicht sie hier hinein;
 * übersetzt wird ausschliesslich in dieser Datei.
 *
 * Nicht übersetzt und mit Absicht: Baustein-Titel, Grenz-Sätze, Firmen- und
 * Vergabestellen-Namen, Beträge, Daten. Das sind Vergabedaten und generierter Befund,
 * keine Oberfläche.
 *
 * **Was diese Datei NICHT tun darf:** einen fehlenden Baustein durch einen Platzhalter
 * ersetzen. Fehlt einer, dann weil er für diese Firma nicht belegt ist. Genau daran ist
 * die Vorfassung gescheitert: sie hatte für jeden Abschnitt einen Ersatz, und der stand
 * dann unter einer Überschrift, die ihn als Befund ausgab. */

/** Was hier endet, endet nicht auf dieselbe Weise. */
function artText(a: Zeile["art"], t: (s: string) => string) {
  if (a === "auslauf") return t("läuft aus");
  if (a === "fertigstellung") return t("wird fertig");
  return t("endet");
}

function Vertragstabelle({ zeilen }: { zeilen: Zeile[] }) {
  const { t } = useSprache();
  // Spalte nur zeigen, wenn irgendwo ein belegter Wert steht. Sonst stünde eine
  // Überschrift „Volumen" über einer Spalte aus Gedankenstrichen, und die liest sich
  // wie ein Fehler, obwohl sie die Wahrheit ist: der Wert wurde nie veröffentlicht.
  const mitVolumen = zeilen.some((z) => z.vol);
  return (
    <table className="ov-tbl">
      <thead>
        <tr>
          <th>{t("Vorhaben")}</th>
          <th>{t("Vergabestelle")}</th>
          {mitVolumen && <th className="r">{t("Volumen")}</th>}
          <th className="r">{t("Endet")}</th>
          <th>{t("Art")}</th>
        </tr>
      </thead>
      <tbody>
        {zeilen.map((z, i) => (
          <tr key={i}>
            <td><div className="fn">{z.titel || t("(ohne Titel)")}</div></td>
            <td>{z.buyer}</td>
            {mitVolumen && <td className="r m">{z.vol ?? ""}</td>}
            <td className="r m">{z.ende ?? ""}</td>
            <td className={z.art === "auslauf" ? "ov-soon" : ""}>{artText(z.art, t)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function BausteinKarte({ b, signup }: { b: Baustein; signup: string }) {
  const { t } = useSprache();
  return (
    <div className="ov-card">
      <div className="ov-ch"><h2>{b.titel}</h2></div>

      {b.zahlen && b.zahlen.some((z) => z.wert) && (
        <div className="ov-kpis">
          {b.zahlen.filter((z) => z.wert).map((z, i) => (
            <div className="ov-kpi" key={i}>
              <div className="k">{z.label}</div>
              <div className="v">{z.wert}</div>
            </div>
          ))}
        </div>
      )}

      {b.namen && b.namen.length > 1 && (
        <div className="ov-namen">{b.namen.join(" · ")}</div>
      )}

      {b.zeilen && b.zeilen.length > 0 && <Vertragstabelle zeilen={b.zeilen} />}

      {/* Die Grenze steht IM Baustein, nicht als Fussnote am Seitenende. Eine Einordnung,
          die man erst nach dem Scrollen findet, kommt nach der Schlussfolgerung. */}
      <div className="ov-grenze">{b.grenze}</div>

      <Link className="ov-bruecke" href={signup}>
        <span className="bp">{b.bruecke.produkt}</span>
        <span className="bt">{b.bruecke.text}</span>
      </Link>
    </div>
  );
}

/** Unbekanntes oder abgelaufenes Token. Kein Grund, den Rahmen wegzulassen. */
export function LandingMissing() {
  const { t } = useSprache();
  return (
    <div className="ov-body">
      <div className="ov-topbar"><span className="ov-logo">govisor</span></div>
      <div className="ov-miss">
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>{t("Auswertung nicht gefunden")}</h1>
        <p style={{ fontSize: 14, lineHeight: 1.6 }}>{t("Dieser Link ist ungültig oder abgelaufen.")}</p>
      </div>
    </div>
  );
}

export function LandingView({ d, token }: { d: Landing; token: string }) {
  const { t } = useSprache();
  // „Konto anlegen" führt ins ONBOARDING, nicht auf die Anmeldeseite. Vorher zeigte es auf
  // `/login?t=…`, eine Seite, die den Parameter nicht liest und „Willkommen zurück" sagt.
  // Wer nie ein Konto hatte, landete also im Wiedersehen.
  const signup = `/onboarding?t=${encodeURIComponent(token)}`;

  return (
    <div className="ov-body">
      <div className="ov-pv">
        <svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="2.5" /></svg>
        <span><b>{t("Auswertung für {firma}", { firma: d.name })}</b> {t("· erstellt aus öffentlichen Vergabedaten. Noch kein Konto.")}</span>
        <span className="r"><Link className="ov-pvbtn" href={signup}>{t("Konto anlegen")}</Link></span>
      </div>

      <div className="ov-topbar"><span className="ov-logo">govisor</span><span className="ov-branche">{t("Auswertung")}</span></div>

      <div className="ov-pagepad"><div className="ov-wrap">
        <div className="ov-finding">
          <div className="eyebrow">{t("Auswertung · Stand {datum}", { datum: d.stand })}</div>
          {/* Der Firmenname gehört in die Überschrift. Vorher stand er nur in der dünnen
              Leiste ganz oben, und die Überschrift sagte bloss „Ihrer Verträge". */}
          <h1>{d.name}</h1>
          <p className="ov-lede">{t("Das ist alles öffentlich. Wir haben es nur zusammengetragen.")}</p>
          <div className="src">
            <svg viewBox="0 0 24 24"><path d="M12 8v5M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>
            {t("Aus öffentlichen Vergabebekanntmachungen. Keine Daten von Ihnen, kein Konto nötig.")}
          </div>
        </div>

        {d.bausteine.map((b) => <BausteinKarte key={b.id} b={b} signup={signup} />)}

        <div className="ov-closing">
          <h3>{t("Diese Auswertung gehört Ihnen")}</h3>
          <p>{t("Mit einem Konto bleibt sie erhalten, wird täglich fortgeschrieben und um die Ausschreibungen ergänzt, die zu Ihrem Profil passen.")}</p>
          <div className="acts">
            <Link className="ov-btn ov-btn-p" href={signup}>{t("Konto anlegen, kostenlos")}</Link>
          </div>
          <div className="fine">{t("Kostenlos dauerhaft nutzbar · keine Zahlungsdaten · Auswertung bereits eingerichtet")}</div>
        </div>
      </div></div>
    </div>
  );
}
