"use client";

/** Die Werkzeuge des Bausteine-Bereichs — stehen in der Bereichsleiste des Rahmens.
 *
 * Der Knopf lag bis 2026-08-15 im Inhalt, und die Bereichsleiste blieb auf dieser Seite
 * leer. Eine Leiste, die nur Hoehe haelt, ist Polsterung; eine, die die Werkzeuge des
 * Bereichs traegt, ist ein Rahmen. Derselbe Umzug wie bei den Unternehmens-Reitern. */
export function BausteineLeiste({ importOpen, onImport }: {
  importOpen: boolean; onImport: (offen: boolean) => void;
}) {
  return (
    // `colbtn` statt `btn btn-s`: das ist die Knopf-Klasse DES RAHMENS (dieselbe wie
    // Filter/Spalten/Export in der Shell). `.btn-s` haette hier nichts bewirkt — sein
    // Aussehen haengt an `.baust-page .btn-s`, und die Bereichsleiste liegt ausserhalb
    // dieses Wrappers. Der Knopf stand dadurch als nackter Text da.
    //
    // Die richtige Lehre ist nicht „Regel nachziehen", sondern: was IN der Leiste steht,
    // gehoert zum Rahmen und soll in jedem Bereich gleich aussehen.
    <button className="colbtn" aria-expanded={importOpen}
      onClick={() => onImport(!importOpen)}>
      {importOpen ? "Import schließen" : "Aus alten Angeboten importieren"}
    </button>
  );
}
