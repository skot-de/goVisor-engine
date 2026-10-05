import { zipSync, strToU8 } from "fflate";

/* Eine .docx aus Überschriften und Absätzen bauen — ohne Abhängigkeit ausser `fflate`.
 *
 * **Warum selbst geschrieben.** Eine `.docx` ist ein ZIP mit festgelegter XML-Struktur, und
 * `fflate` liegt seit dem Fragebogen-Leser bereits im Baum (dort `unzipSync`, hier `zipSync`).
 * Die Bibliothek `docx` wären rund 2 MB für etwas, das in einer Datei beherrschbar ist — und
 * eine weitere Abhängigkeit in einem `node_modules`, das als Symlink im Haupt-Baum liegt.
 *
 * ⚠ **Word ist unerbittlich.** Fehlt ein Teil oder stimmt ein Namensraum nicht, öffnet sich die
 * Datei gar nicht, und zwar ohne brauchbare Meldung. Deshalb prüft `tests/test_docx.py` jede
 * erzeugte Datei: entpacken, alle Pflichtteile vorhanden, XML wohlgeformt, Text wiederfindbar.
 * Eine Datei, die Word nicht öffnet, merkt man sonst beim Kunden.
 *
 * Aufbau des Pakets (alle vier Teile sind Pflicht):
 *
 *     [Content_Types].xml          sagt, welcher Teil welchen Typ hat
 *     _rels/.rels                  zeigt auf das Hauptdokument
 *     word/document.xml            der Inhalt
 *     word/styles.xml              Normal und Ueberschrift 1 bis 3
 *     word/_rels/document.xml.rels verbindet Dokument und Formatvorlagen
 */

export type DocxTeil =
  | { art: "ueberschrift"; text: string; ebene: 1 | 2 | 3 }
  | { art: "absatz"; text: string };

const NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships";
const NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types";
const T_DOC = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** XML-Maskierung. ⚠ Auch `>` wird maskiert: nicht zwingend, aber `]]>` in einem Text wäre
 *  sonst eine Falle, und die Kosten sind null. */
function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}

/* Steuerzeichen, die XML 1.0 nicht erlaubt. Ein einziges davon — etwa aus einer kopierten PDF —
 * macht die Datei unlesbar, und Word sagt nur „Inhalt unlesbar". Tabulator, Zeilenumbruch und
 * Wagenruecklauf bleiben, der Rest fliegt raus. */
const VERBOTEN = /[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g;
const sauber = (s: string) => s.replace(VERBOTEN, "");

function absatz(text: string, stil?: string): string {
  const inhalt = sauber(text);
  /* Mehrzeiliger Text wird zu MEHREREN Absaetzen. Ein `w:br` waere die Alternative, aber dann
   * haengt der ganze Block an einer Formatvorlage und laesst sich in Word nicht einzeln
   * umformatieren — und genau das will jemand, der den Entwurf uebernimmt. */
  const zeilen = inhalt.split(/\r?\n/);
  return zeilen.map((z) => {
    const pPr = stil ? `<w:pPr><w:pStyle w:val="${stil}"/></w:pPr>` : "";
    if (!z.trim()) return `<w:p>${pPr}</w:p>`;
    return `<w:p>${pPr}<w:r><w:t xml:space="preserve">${esc(z)}</w:t></w:r></w:p>`;
  }).join("");
}

function dokumentXml(titel: string, teile: DocxTeil[]): string {
  const koerper = [
    absatz(titel, "Title"),
    ...teile.map((t) => (t.art === "ueberschrift"
      ? absatz(t.text, `Heading${t.ebene}`)
      : absatz(t.text))),
  ].join("");
  /* `w:sectPr` setzt A4 hochkant mit 2 cm Rand (Zwanzigstel eines Punktes: 11906 x 16838). Ohne
   * diesen Block nimmt Word seine Voreinstellung, und die ist je nach Gebietsschema Letter. */
  const sect = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    + '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"'
    + ' w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`
    + `<w:document xmlns:w="${NS_W}"><w:body>${koerper}${sect}</w:body></w:document>`;
}

function stilVorlage(id: string, name: string, groesse: number, fett: boolean,
                     gliederung?: number): string {
  const pPr = gliederung === undefined ? ""
    : `<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/>`
      + `<w:outlineLvl w:val="${gliederung}"/></w:pPr>`;
  return `<w:style w:type="paragraph" w:styleId="${id}"><w:name w:val="${name}"/>`
    + `<w:basedOn w:val="Normal"/><w:qFormat/>${pPr}`
    + `<w:rPr>${fett ? "<w:b/>" : ""}<w:sz w:val="${groesse}"/></w:rPr></w:style>`;
}

function stylesXml(): string {
  // `w:sz` zaehlt HALBE Punkte: 48 = 24 pt, 22 = 11 pt.
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`
    + `<w:styles xmlns:w="${NS_W}">`
    + `<w:style w:type="paragraph" w:default="1" w:styleId="Normal">`
    + `<w:name w:val="Normal"/><w:qFormat/>`
    + `<w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>`
    + `<w:rPr><w:sz w:val="22"/></w:rPr></w:style>`
    + stilVorlage("Title", "Title", 48, true)
    + stilVorlage("Heading1", "heading 1", 32, true, 0)
    + stilVorlage("Heading2", "heading 2", 28, true, 1)
    + stilVorlage("Heading3", "heading 3", 24, true, 2)
    + `</w:styles>`;
}

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`
  + `<Types xmlns="${NS_CT}">`
  + `<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>`
  + `<Default Extension="xml" ContentType="application/xml"/>`
  + `<Override PartName="/word/document.xml" ContentType="${T_DOC}.main+xml"/>`
  + `<Override PartName="/word/styles.xml" ContentType="${T_DOC}.styles+xml"/>`
  + `</Types>`;

const RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`
  + `<Relationships xmlns="${NS_REL}"><Relationship Id="rId1"`
  + ` Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"`
  + ` Target="word/document.xml"/></Relationships>`;

const DOC_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`
  + `<Relationships xmlns="${NS_REL}"><Relationship Id="rId1"`
  + ` Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"`
  + ` Target="styles.xml"/></Relationships>`;

/** Baut die Datei. Rückgabe sind die Bytes, das Schreiben macht der Aufrufer. */
export function baueDocx(titel: string, teile: DocxTeil[]): Uint8Array {
  return zipSync({
    "[Content_Types].xml": strToU8(CONTENT_TYPES),
    "_rels/.rels": strToU8(RELS),
    "word/document.xml": strToU8(dokumentXml(titel || "Ohne Titel", teile)),
    "word/styles.xml": strToU8(stylesXml()),
    "word/_rels/document.xml.rels": strToU8(DOC_RELS),
  }, { level: 6 });
}

/** Dateiname aus dem Titel: nur Unbedenkliches, nie leer. */
export function dateiname(titel: string): string {
  const k = (titel || "Dokument").normalize("NFKD")
    .replace(/[^\p{L}\p{N} _-]/gu, "").trim().replace(/\s+/g, "-").slice(0, 80);
  return `${k || "Dokument"}.docx`;
}
