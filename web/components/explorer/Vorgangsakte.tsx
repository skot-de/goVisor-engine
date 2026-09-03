"use client";
import { useEffect, useState } from "react";
import { useSprache } from "@/lib/i18n";

/* Die Vorgangsakte: Ausschreibung, Korrekturen, Unterlagen und Zuschlag unter EINER Nummer.
 *
 * Bis hierher waren das drei getrennte Welten. Eine Vergabe war ein Lead, ihre Korrekturen
 * waren weitere Leads, ihr Zuschlag lag in `awards`, ihre Dateien in `doc-listing` — und
 * nichts davon wusste voneinander. `data/gold/<L>/vorgaenge.parquet` fuehrt sie seit dem
 * 2026-09-01 zusammen; diese Seite ist der erste Ort, an dem man das sieht.
 *
 * ⚠ DREI STELLEN, AN DENEN DIE SEITE EHRLICH SEIN MUSS, statt Vollstaendigkeit zu suggerieren:
 *   1. Wie der Vorgang zusammengesetzt wurde (amtlich verknuepft vs. ueber Rueckverweis).
 *   2. Dass eine Dateiliste nicht dasselbe ist wie gelesene Unterlagen.
 *   3. Dass alte Vorgaenge fast nie Dateien haben, WEIL wir erst seit August 2026 abrufen,
 *      und nicht, weil es keine gab. */

type Verlauf = { datum: string | null; art: string; label: string; n: number;
                 ids: string[]; unterlagen: boolean };
type Dok = { notice: string; quelle: string | null; url: string | null; gelesen: boolean;
             n: number; dateien: Array<{ name: string; typ: string }>; gekuerzt: number };
type Glied = { vorgang: string; position: number; jahr: number | null;
               konfidenz: number | null; titel: string | null; duenn: boolean;
               wurzel: boolean; anschluss_direkt: boolean; vorgaenger_jahr: number | null };
type Akte = {
  id: string; land: string; titel: string | null; cpv: string | null; schluessel: string;
  vollstaendig: boolean; von: string | null; bis: string | null;
  zahlen: Record<string, number>; verlauf: Verlauf[]; dokumente: Dok[];
  unterlagen_grund: "angekuendigt" | "vor_abrufstart" | "kein_abruf" | null;
  kette?: { kette: string; position: number; n_glieder: number; min_konfidenz: number | null;
            methode: string; dauerangebot: boolean; gekuerzt: number; glieder: Glied[];
            guete: "belastbar" | "plausibel" | "schwach" | null;
            duennes_glied_sichtbar: boolean };
};
type Antwort = { vorhanden: boolean; akte?: Akte; grund?: string; error?: string };

const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"];

// ⚠ OHNE `t()`, WEIL DAS DATUM KEIN SATZ IST. Der Leerfall dagegen schon — der geht in
// der Anzeige durch `t("ohne Datum")` und nicht hier, wo es kein `t` gibt.
const tag = (d: string): string => {
  const [j, m, t] = d.split("-");
  return `${t}.${m}.${j}`;
};
const monat = (d: string | null): string => {
  if (!d) return "";
  const [j, m] = d.split("-");
  return `${MONATE[Number(m) - 1]} ${j}`;
};

// Wie der Schluessel zustande kam. Das ist keine Nebensache: eine ueber Rueckverweise
// zusammengesetzte Akte darf nicht aussehen wie eine amtlich verknuepfte.
const HERKUNFT: Record<string, { text: string; ton: string }> = {
  folder: { text: "Bekanntmachungen amtlich verknüpft", ton: "ok" },
  rueckref: { text: "Bekanntmachungen über Rückverweis verknüpft", ton: "" },
  // ⚠ HIESS BIS ZUM 2026-09-02 „einzeln, keine Verknuepfung gefunden" — und stand damit bei
  // 6.048 Akten DIREKT UEBER einer Vorgeschichte mit mehreren Gliedern. Der Vermerk meint
  // die Bekanntmachungen DIESES Vorgangs, die Kette meint die Nachfolge zwischen Vorgaengen;
  // zwei verschiedene Dinge, die im alten Wortlaut wie ein Widerspruch aussahen.
  allein: { text: "nur eine Bekanntmachung", ton: "" },
};

/* Wie belastbar die Vorgeschichte ist. Die Bänder kommen aus `export_vorgaenge.KETTE_GUETE`
 * und sind gemessen, nicht geschätzt; hier steht nur, wie sie heissen und aussehen.
 *
 * ⚠ WARUM DAS UEBERHAUPT AN DIE OBERFLAECHE MUSS. Eine Kette ist NIE amtlich, sondern
 * erschlossen — und 64 % der Ketten sitzen im schwächsten Band. Sie alle mit demselben
 * Satz zu zeigen, macht aus einer knappen Aehnlichkeit dieselbe Aussage wie aus einem
 * starken Inhaltsvergleich. Genau diese Unterscheidung trifft die Anzeige bei den
 * Unterlagen ja auch („gelesen" gegen „nur gelistet"). */
const GUETE: Record<string, { text: string; ton: string; satz: string }> = {
  belastbar: {
    text: "Verknüpfung belastbar", ton: "ok",
    satz: "Die Vorgänge sind über einen starken Inhaltsvergleich verknüpft. Amtlich ist die Verbindung trotzdem nicht.",
  },
  plausibel: {
    text: "Verknüpfung plausibel", ton: "",
    satz: "Die Verknüpfung ist plausibel, aber nicht belegt. Sie beruht auf Käufer und Leistung.",
  },
  schwach: {
    text: "Verknüpfung schwach", ton: "warn",
    satz: "Die Verknüpfung beruht auf einer knappen Ähnlichkeit. Als Hinweis brauchbar, als Beleg nicht.",
  },
};

const ART_TON: Record<string, string> = {
  cn: "aus", can: "zu", corrigendum: "kor", pin: "vor", other: "",
};

export function Vorgangsakte() {
  const { t } = useSprache();
  const [id, setId] = useState<string | null>(null);
  const [land, setLand] = useState<string>("DE");
  const [lead, setLead] = useState<string | null>(null);
  const [antwort, setAntwort] = useState<Antwort | null>(null);
  const [laedt, setLaedt] = useState(false);

  useEffect(() => {
    const lies = () => {
      const p = new URLSearchParams(window.location.search);
      setId(p.get("id"));
      setLand((p.get("land") || "DE").toUpperCase());
      setLead(p.get("lead"));
    };
    lies();
    window.addEventListener("popstate", lies);
    return () => window.removeEventListener("popstate", lies);
  }, []);

  useEffect(() => {
    if (!id && !lead) { setAntwort(null); return; }
    setLaedt(true);
    const q = id
      ? `id=${encodeURIComponent(id)}&land=${encodeURIComponent(land)}`
      : `lead=${encodeURIComponent(lead!)}`;
    fetch(`/api/vorgang?${q}`)
      .then((r) => r.json())
      .then(setAntwort)
      .catch(() => setAntwort({ vorhanden: false, error: "nicht erreichbar" }))
      .finally(() => setLaedt(false));
  }, [id, land, lead]);

  // ⚠ DAS LAND MUSS MIT. Ohne es faellt der Sprung auf die Vorgabe `DE` zurueck und eine
  // oesterreichische Kette landet bei der deutschen Akte mit derselben Nummer — es gibt 48
  // solche Nummern. Eine Kette verlaesst ihr Land nicht, also ist es immer das der Akte.
  const oeffne = (ziel: string, zielLand: string) => {
    window.history.pushState(
      {}, "", `/vorgang?id=${encodeURIComponent(ziel)}&land=${encodeURIComponent(zielLand)}`);
    setLead(null);
    setLand(zielLand);
    setId(ziel);
  };

  if (!id && !lead) {
    return (
      <div className="vg-wrap">
        <header className="vg-kopf">
          <h1>{t("Vorgang")}</h1>
          <p>{t("Ein Vorgang führt Ausschreibung, Korrekturen, Unterlagen und Zuschlag unter einer Nummer zusammen. Erreichbar aus einer Vergabe heraus oder über den Deep-Link mit der Vorgangsnummer.")}</p>
        </header>
      </div>
    );
  }
  if (laedt) return <div className="vg-load">{t("Lade Vorgang …")}</div>;
  if (!antwort) return null;

  if (antwort.error) {
    return <div className="vg-wrap"><p className="vg-leer">{antwort.error}</p></div>;
  }
  if (!antwort.vorhanden || !antwort.akte) {
    return (
      <div className="vg-wrap">
        <p className="vg-leer">
          {t("Zu dieser Vergabe ist keine Akte hinterlegt.")}{" "}
          {t("Aufbereitet sind die Vorgänge der heute ausgeschriebenen Vergaben samt ihrer Vorgeschichte.")}
        </p>
      </div>
    );
  }

  const a = antwort.akte;
  const h = HERKUNFT[a.schluessel] || { text: a.schluessel, ton: "" };
  const z = a.zahlen;
  // Weist irgendein Ereignis des Vorgangs Unterlagen aus? Entscheidet den Leertext unten.
  const guete = a.kette?.guete ? GUETE[a.kette.guete] : null;

  return (
    <div className="vg-wrap">
      <header className="vg-kopf">
        <div className="vg-zeile">
          <span className="vg-nr">{a.id}</span>
          <span className={`vg-tag ${h.ton}`}>{t(h.text)}</span>
          {a.vollstaendig
            ? <span className="vg-tag ok">{t("Ausschreibung und Zuschlag vorhanden")}</span>
            : <span className="vg-tag">{t("Zuschlag noch offen")}</span>}
        </div>
        <h1>{a.titel || t("ohne Titel")}</h1>
        <p className="vg-meta">
          {a.cpv ? <>{t("CPV {c}", { c: a.cpv })} · </> : null}
          {a.von ? t("{von} bis {bis}", { von: monat(a.von), bis: monat(a.bis) }) : null}
          {" · "}
          {z.angedockt > 0
            ? <>{z.angedockt === 1
                  ? t("ein Zuschlag über Käufer und Titel zugeordnet, nicht amtlich verknüpft.")
                  : t("{n} Zuschläge über Käufer und Titel zugeordnet, nicht amtlich verknüpft.", { n: z.angedockt })}{" · "}</>
            : null}
          {z.bekanntmachungen === 1
            ? t("eine Bekanntmachung")
            : t("{n} Bekanntmachungen", { n: z.bekanntmachungen })}
        </p>
      </header>

      <section className="vg-block">
        <h2>{t("Verlauf")}</h2>
        <ol className="vg-verlauf">
          {a.verlauf.map((e, i) => (
            <li key={i} className={ART_TON[e.art] || ""}>
              <span className="vg-datum">{e.datum ? tag(e.datum) : t("ohne Datum")}</span>
              <span className="vg-art">
                {t(e.label)}
                {e.n > 1 ? <em>{t("{n} am selben Tag", { n: e.n })}</em> : null}
              </span>
              <span className="vg-ids">
                {e.ids.slice(0, 3).join(", ")}
                {e.ids.length > 3 ? ` +${e.ids.length - 3}` : ""}
              </span>
              {e.unterlagen ? <span className="vg-tag ok">{t("Unterlagen")}</span> : null}
            </li>
          ))}
        </ol>
      </section>

      <section className="vg-block">
        <h2>{t("Unterlagen")}</h2>
        {a.dokumente.length === 0 ? (
          <p className="vg-hinweis">
            {/* ⚠ DREI GRUENDE, DIE ALLE „keine Unterlagen" HEISSEN. Der Grund kommt aus dem
                Export (`_unterlagen_grund`), damit die Anzeige ihn nicht raten muss: der
                erste Entwurf schob es IMMER aufs Alter und behauptete das auch bei 7.453
                Vorgaengen von August 2026 oder spaeter, denen es nicht galt. */}
            {a.unterlagen_grund === "angekuendigt"
              ? <>{t("Diese Vergabe weist Unterlagen aus, abgerufen haben wir die Dateiliste noch nicht.")}{" "}
                 {t("Der Abruf läuft laufend nach; welche Portale ihn zulassen, steht in der Herkunft der jeweiligen Vergabe.")}</>
              : a.unterlagen_grund === "vor_abrufstart"
                ? <>{t("Zu diesem Vorgang liegt keine Dateiliste vor.")}{" "}
                   {t("Unterlagen holen wir erst seit August 2026 ein; ältere Vorgänge tragen deshalb Bekanntmachungen und Zuschlag, aber selten Dateien. Rückwirkend gibt sie kein Portal heraus.")}</>
                : <>{t("Zu diesem Vorgang liegt keine Dateiliste vor.")}{" "}
                   {t("Nicht jedes Portal gibt eine Liste der Unterlagen ohne Anmeldung heraus. Woher wir sie bekommen, steht in der Herkunft der jeweiligen Vergabe.")}</>}
          </p>
        ) : (
          a.dokumente.map((d) => (
            <div key={d.notice} className="vg-dok">
              <div className="vg-dok-kopf">
                <strong>{d.n === 1 ? t("eine Datei") : t("{n} Dateien", { n: d.n })}</strong>
                <span className="fs">{d.quelle}</span>
                {/* Der Unterschied zwischen „gelesen" und „nur gelistet" muss stehen
                    bleiben. Eine Dateiliste ist ein Inhaltsverzeichnis, kein Inhalt. */}
                <span className={`vg-tag ${d.gelesen ? "ok" : "warn"}`}>
                  {d.gelesen ? t("gelesen") : t("nur gelistet")}
                </span>
                {d.url ? <a href={d.url} target="_blank" rel="noopener noreferrer">
                  {t("zum Portal")}</a> : null}
              </div>
              <ul className="vg-dateien">
                {d.dateien.map((f, i) => (
                  <li key={i}><span className={`vg-typ t-${f.typ}`}>{t(f.typ)}</span>{f.name}</li>
                ))}
              </ul>
              {d.gekuerzt > 0
                ? <p className="fs">{t("und {n} weitere Dateien", { n: d.gekuerzt })}</p>
                : null}
            </div>
          ))
        )}
      </section>

      {a.kette ? (
        <section className="vg-block">
          <h2>
            {t("Vorgeschichte")}
            {guete ? <span className={`vg-tag ${guete.ton}`}>{t(guete.text)}</span> : null}
          </h2>
          <p className="vg-hinweis">
            {a.kette.n_glieder === 1
              ? t("Eine weitere Vergabe hängt inhaltlich mit dieser zusammen.")
              : t("{n} Vergaben, die inhaltlich aufeinander folgen.", { n: a.kette.n_glieder })}
            {" "}
            {guete ? t(guete.satz) : t("Die Verknüpfung ist erschlossen, nicht amtlich. Sie beruht auf Käufer und Leistung.")}
            {a.kette.dauerangebot
              ? <> {t("Der Takt ist hoch: das sieht nach einem laufenden Abruf aus, nicht nach einzelnen Neuvergaben.")}</>
              : null}
            {/* Das schwaechste Glied kann ausserhalb des angezeigten Fensters liegen. Ohne
                diesen Satz widerspricht sich die Seite: oben „schwach", unten kein einziges
                markiertes Glied. */}
            {guete && a.kette.guete === "schwach" && !a.kette.duennes_glied_sichtbar
              ? <> {t("Die dünne Stelle liegt ausserhalb der hier gezeigten Glieder.")}</>
              : null}
          </p>
          <ol className="vg-kette">
            {a.kette.glieder.map((g) => (
              <li key={g.vorgang} className={g.vorgang === a.id ? "hier" : ""}>
                <span className="vg-jahr">{g.jahr ?? "?"}</span>
                {/* ⚠ DIE LISTE IST NACH JAHR SORTIERT, DIE NACHFOLGE IST EIN BAUM. 58 % der
                    angezeigten Glieder folgen NICHT auf die Zeile darueber, weil Nachfolger
                    verzweigen: mehrere Vergaben koennen denselben Vorgaenger haben. Ein
                    Vermerk, der stillschweigend die Zeile darueber meint, sagt deshalb in
                    der Mehrzahl der Faelle etwas Falsches. Darum steht hier, worauf das
                    Glied tatsaechlich folgt. */}
                {g.wurzel
                  ? <span className="vg-tag">{t("Anfang der Kette")}</span>
                  : !g.anschluss_direkt && g.vorgaenger_jahr
                    ? <span className="vg-tag">{t("folgt auf {jahr}", { jahr: g.vorgaenger_jahr })}</span>
                    : null}
                {g.duenn
                  ? <span className="vg-tag warn" title={t("Der Anschluss an den Vorgänger ist nur knapp belegt.")}>{t("Anschluss knapp")}</span>
                  : null}
                {g.vorgang === a.id
                  ? <strong>{g.titel || t("ohne Titel")}</strong>
                  : <button type="button" onClick={() => oeffne(g.vorgang, a.land)}>
                      {g.titel || t("ohne Titel")}</button>}
                {g.vorgang === a.id
                  ? <span className="vg-tag ok">{t("dieser Vorgang")}</span> : null}
              </li>
            ))}
          </ol>
          {a.kette.gekuerzt > 0
            ? <p className="fs">{a.kette.gekuerzt === 1
                ? t("ein weiteres Glied in dieser Kette")
                : t("{n} weitere Glieder in dieser Kette", { n: a.kette.gekuerzt })}</p>
            : null}
        </section>
      ) : null}
    </div>
  );
}
