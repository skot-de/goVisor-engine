import { unzipSync } from "fflate";
import { createRequire } from "node:module";
import path from "node:path";

/* ⚠ **HIER STEHT BEWUSST KEIN `import "server-only"`.** Das waere die naheliegende Wache, und sie
 * saesse an der falschen Stelle: `server-only` ist von Next bereitgestellt und aus reinem Node
 * nicht aufloesbar — mit ihm laesst sich diese Datei nicht mehr headless pruefen, und ein
 * ungepruefter Dateileser ist schlimmer als ein theoretisch falsch importierbarer. Die Wache
 * steht deshalb in `app/api/antwortauftrag/route.ts`, also an der Grenze, an der sie wirkt. */

/* Fragebogen aus einer Datei lesen: XLSX, PDF, Text.
 *
 * ⚠ **WARUM SERVERSEITIG UND NICHT IM BROWSER.** Der erste Entwurf wollte im Browser lesen, damit
 * die Datei das Geraet nicht verlaesst. Dagegen stand pdf.js: es braucht einen Web-Worker, dessen
 * Verdrahtung in Next/Turbopack eine eigene Baustelle ist — und die haette ich ohne laufenden
 * Browser nicht pruefen koennen. Serverseitig laeuft dieselbe Bibliothek in Node, ohne Worker,
 * ohne Bundle-Zuwachs, und sie ist **headless pruefbar** (`tests/test_fragebogen_lesen.mjs`).
 *
 * ⚠ **GESPEICHERT WIRD NICHTS.** Die Bytes leben in diesem Aufruf und sonst nirgends: kein
 * Blob-Speicher, keine Datei auf der Platte, kein Feld in der Datenbank. In den Auftrag geht
 * ausschliesslich der ausgelesene Text, verschluesselt. Die Datei reist damit zwar bis zum
 * Server (im Browser-Entwurf waere sie geblieben), aber sie bleibt nicht dort.
 */

export type Art = "xlsx" | "pdf" | "text";
export type Gelesen = { text: string; art: Art; hinweis?: string };

/** Mehr als das nimmt kein Fragebogen ein. Die Grenze schuetzt vor dem versehentlich
 *  hochgeladenen Gesamtpaket der Vergabeunterlagen, nicht vor Angriff (dafuer s. ZIP_GRENZE). */
export const MAX_BYTES = 25 * 1024 * 1024;
/** ⚠ Zip-Bombe. Eine XLSX ist ein ZIP, und 1 MB komprimiert koennen 10 GB entpackt sein.
 *  `unzipSync` entpackt in den Speicher — ohne diese Grenze reicht eine Datei, um den Dienst
 *  umzulegen. Gilt je Eintrag UND in der Summe. */
export const ZIP_GRENZE = 80 * 1024 * 1024;
export const MAX_TEXT = 400_000;        // wie `/api/blocks-import`

export class NichtLesbar extends Error {}

const ENTITAETEN: Record<string, string> = {
  "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'",
};
const entschaerft = (s: string) =>
  s.replace(/&(amp|lt|gt|quot|apos);/g, (m) => ENTITAETEN[m])
   .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
   .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)));

/** Alle `<t>`-Inhalte eines XML-Stuecks, in Reihenfolge.
 *
 * ⚠ Hier wird XML mit regulaeren Ausdruecken gelesen, und das ist normalerweise ein Fehler.
 * Begruendung fuer die Ausnahme: dieses XML ist maschinenerzeugt und streng regelmaessig, ein
 * echter Parser (`DOMParser`) existiert in Node nicht ohne weitere Abhaengigkeit, und der
 * Alternativweg waere eine zweite Bibliothek fuer einen Zweck, den zwei Zeilen erledigen.
 * Tabellenzellen mit `<` im Text sind als `&lt;` kodiert, koennen das Muster also nicht brechen.
 */
function textStuecke(xml: string): string[] {
  return [...xml.matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g)].map((m) => entschaerft(m[1]));
}

function xlsxZuText(bytes: Uint8Array): Gelesen {
  let dateien: Record<string, Uint8Array>;
  try {
    let summe = 0;
    dateien = unzipSync(bytes, {
      filter: (f) => {
        if (f.originalSize > ZIP_GRENZE) throw new NichtLesbar("Eintrag in der Datei zu gross.");
        summe += f.originalSize;
        if (summe > ZIP_GRENZE) throw new NichtLesbar("Datei entpackt zu gross.");
        // Nur was gebraucht wird. Bilder und Makros bleiben ungelesen im Paket.
        return f.name === "xl/sharedStrings.xml" || /^xl\/worksheets\/sheet\d+\.xml$/.test(f.name);
      },
    });
  } catch (e) {
    if (e instanceof NichtLesbar) throw e;
    throw new NichtLesbar("Die Excel-Datei konnte nicht geoeffnet werden.");
  }

  const roh = (name: string) =>
    dateien[name] ? new TextDecoder("utf-8").decode(dateien[name]) : "";
  const geteilt = textStuecke(roh("xl/sharedStrings.xml"));

  const blaetter = Object.keys(dateien)
    .filter((n) => n.startsWith("xl/worksheets/"))
    .sort((a, b) => a.localeCompare(b, "en", { numeric: true }));

  const zeilen: string[] = [];
  for (const blatt of blaetter) {
    for (const [, inhalt] of roh(blatt).matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)) {
      const felder: string[] = [];
      for (const [, attr, zelle] of inhalt.matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)) {
        const typ = /\bt="([^"]+)"/.exec(attr)?.[1];
        if (typ === "s") {
          const i = Number(/<v>(\d+)<\/v>/.exec(zelle)?.[1]);
          // ⚠ Eine Kennzahl ohne Eintrag in der Tabelle ist KEIN leeres Feld, sondern eine
          //   kaputte Datei. Sie stillschweigend zu ueberspringen verschiebt Spalten.
          if (Number.isInteger(i) && i < geteilt.length) felder.push(geteilt[i]);
        } else if (typ === "inlineStr") {
          felder.push(textStuecke(zelle).join(" "));
        } else {
          const v = /<v>([\s\S]*?)<\/v>/.exec(zelle)?.[1];
          if (v != null) felder.push(entschaerft(v));
        }
      }
      /* Eine TABELLENZEILE wird EINE Textzeile. Ein Fragebogen hat die Nummer in einer Spalte
       * und die Frage in der naechsten ("1." | "Bitte beschreiben Sie …"); zusammengefuegt
       * entsteht genau die Form, die `fragen_aus_text` erkennt. Je Zelle eine Zeile wuerde die
       * Nummer von ihrer Frage trennen und aus einer Frage zwei Fragmente machen. */
      const zeile = felder.join(" ").replace(/\s+/g, " ").trim();
      if (zeile) zeilen.push(zeile);
    }
  }
  if (!zeilen.length) {
    throw new NichtLesbar("In der Excel-Datei wurde kein Text gefunden.");
  }
  return { text: zeilen.join("\n"), art: "xlsx" };
}

/** Wo pdf.js seine mitgelieferten Daten findet (Schriftmasse, CJK-Tabellen).
 *
 * ⚠ **Ohne das warnt pdf.js bei JEDEM PDF** („Ensure that the `standardFontDataUrl` API parameter
 * is provided") und faellt auf Ersatzmasse zurueck. Das bricht nichts sichtbar — die Entnahme
 * lief auch vorher — kann aber bei Dokumenten, die auf den 14 Standardschriften aufbauen, die
 * Zeichenzuordnung verschlechtern. Gefunden im Serverprotokoll beim Abschalten, nicht von einem
 * Test: eine Warnung ist kein Fehlschlag, und niemand sieht hin.
 *
 * Der Pfad wird zur LAUFZEIT aufgeloest. Das geht nur, weil `pdfjs-dist` in
 * `next.config.mjs` als externes Paket gefuehrt wird und damit aus `node_modules` kommt; waere
 * es gebuendelt, gaebe es dieses Verzeichnis daneben gar nicht. Der abschliessende Schraegstrich
 * gehoert dazu, pdf.js haengt die Dateinamen direkt an. */
function pdfDatenPfade(): { standardFontDataUrl: string; cMapUrl: string; cMapPacked: boolean } {
  const wurzel = path.dirname(createRequire(import.meta.url).resolve("pdfjs-dist/package.json"));
  return {
    standardFontDataUrl: path.join(wurzel, "standard_fonts") + path.sep,
    cMapUrl: path.join(wurzel, "cmaps") + path.sep,
    cMapPacked: true,
  };
}

async function pdfZuText(bytes: Uint8Array): Promise<Gelesen> {
  /* Spaet geladen: pdf.js ist gross, und die meisten Auftraege sind Excel oder Text. */
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  /* ⚠ `getDocument` gibt einen LADEVORGANG zurueck, und nur der hat `destroy()`. Das Dokument
   * selbst kennt in pdf.js 6 nur `cleanup()`. Wer `doc.destroy()` ruft, bekommt
   * "doc.destroy is not a function" — und wer das im `finally` tut, verdeckt damit sogar den
   * echten Fehler davor. Hier gefunden, weil der Test mit einer echten PDF-Datei laeuft. */
  let vorgang;
  let doc;
  try {
    vorgang = pdfjs.getDocument({
      data: bytes,
      /* ⚠ Ein Fragebogen ist ein FREMDES Dokument, also so wenig Zugriff wie moeglich.
       * `useWorkerFetch: false` verbietet pdf.js, Ressourcen nachzuladen; `disableFontFace`
       * verhindert, dass Schriftarten aus der Datei verarbeitet werden. Fuer reine
       * Textentnahme braucht es keines von beiden.
       * `isEvalSupported: false` stand hier zuerst und ist WEG, nicht vergessen: pdf.js 6
       * kennt die Option nicht mehr, weil es kein `eval` mehr benutzt. Eine wirkungslose
       * Sicherheitsoption stehenzulassen ist schlimmer als keine, weil sie Sicherheit
       * vortaeuscht. */
      useWorkerFetch: false,
      disableFontFace: true,
      ...pdfDatenPfade(),
    });
    doc = await vorgang.promise;
  } catch (e) {
    await vorgang?.destroy().catch(() => {});
    /* ⚠ Die Ursache MITGEBEN. Hier stand ein `catch {}` ohne Bindung, und als pdf.js in der
     * Next-Umgebung anders scheiterte als im Test, war nicht herauszufinden warum — die
     * Meldung sagte nur "konnte nicht geoeffnet werden". Ein Fehler, der seine Ursache
     * wegwirft, kostet genau dann Zeit, wenn man sie am dringendsten braucht. */
    throw new NichtLesbar("Die PDF-Datei konnte nicht geoeffnet werden.", { cause: e });
  }

  const teile: string[] = [];
  try {
    for (let s = 1; s <= doc.numPages; s++) {
      const seite = await doc.getPage(s);
      const inhalt = await seite.getTextContent();
      /* Zeilen aus `y`-Lage bilden: pdf.js liefert Textstuecke, keine Zeilen. Ohne das steht
       * der ganze Bogen in einer Zeile, und `fragen_aus_text` arbeitet zeilenweise. */
      let letzteY: number | null = null;
      let zeile = "";
      for (const st of inhalt.items as { str: string; transform?: number[] }[]) {
        const y = st.transform?.[5] ?? null;
        if (letzteY !== null && y !== null && Math.abs(y - letzteY) > 2) {
          if (zeile.trim()) teile.push(zeile.replace(/\s+/g, " ").trim());
          zeile = "";
        }
        zeile += st.str;
        if (y !== null) letzteY = y;
      }
      if (zeile.trim()) teile.push(zeile.replace(/\s+/g, " ").trim());
    }
  } finally {
    await vorgang.destroy();
  }

  const text = teile.join("\n");
  if (!text.trim()) {
    /* ⚠ Das ist der haeufige Fall und darf NICHT wie ein Fehler des Nutzers klingen: ein
     * gescannter Bogen ist ein Bild, und Texterkennung gibt es hier nicht. */
    throw new NichtLesbar(
      "In dieser PDF-Datei steht kein auslesbarer Text. Sie ist wahrscheinlich ein Scan. "
      + "Bitte fuegen Sie die Fragen als Text ein.");
  }
  return { text, art: "pdf" };
}

export async function textAusDatei(bytes: Uint8Array, name: string): Promise<Gelesen> {
  if (!bytes.length) throw new NichtLesbar("Die Datei ist leer.");
  if (bytes.length > MAX_BYTES) {
    throw new NichtLesbar(`Die Datei ist groesser als ${Math.round(MAX_BYTES / 1024 / 1024)} MB.`);
  }
  const endung = (name.match(/\.([a-z0-9]+)$/i)?.[1] || "").toLowerCase();

  let gelesen: Gelesen;
  if (endung === "xlsx" || endung === "xlsm") gelesen = xlsxZuText(bytes);
  else if (endung === "pdf") gelesen = await pdfZuText(bytes);
  else if (endung === "txt" || endung === "csv" || endung === "tsv") {
    gelesen = { text: new TextDecoder("utf-8").decode(bytes), art: "text" };
  } else if (endung === "xls") {
    // Ehrlich benennen statt mit einem Fehler aus der ZIP-Schicht zu scheitern: eine .xls ist
    // kein ZIP, und `unzipSync` wuerde "konnte nicht geoeffnet werden" melden.
    throw new NichtLesbar("Das alte Excel-Format (.xls) wird nicht gelesen. "
                          + "Bitte als .xlsx speichern.");
  } else if (endung === "doc" || endung === "docx") {
    throw new NichtLesbar("Word-Dateien werden noch nicht gelesen. "
                          + "Bitte die Fragen als Text einfuegen.");
  } else {
    throw new NichtLesbar(`Dateityp .${endung || "?"} wird nicht gelesen.`);
  }

  if (gelesen.text.length > MAX_TEXT) {
    return { ...gelesen, text: gelesen.text.slice(0, MAX_TEXT),
             hinweis: "Die Datei war sehr lang und wurde gekuerzt." };
  }
  return gelesen;
}
