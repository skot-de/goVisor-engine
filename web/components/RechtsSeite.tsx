import type { ReactNode } from "react";

/**
 * Die gemeinsame Huelle fuer Impressum und Datenschutzerklaerung.
 *
 * ⚠ EIGENES, KNAPPES STYLESHEET statt der App-Oberflaeche, aus demselben Grund wie bei
 * der Grounding Page: diese Seiten muessen auch dann lesbar sein, wenn das Design-System
 * sich aendert oder gar nicht laedt. Eine Pflichtangabe, die an einem CSS-Fehler haengt,
 * ist keine.
 *
 * ⚠ KEINE CLIENT-KOMPONENTE. Reines Server-HTML, damit die Seiten ohne Javascript
 * vollstaendig dastehen. Das ist hier kein Feinschliff: wer eine Pflichtangabe sucht,
 * soll sie finden, auch mit abgeschaltetem Javascript oder in einem Reader.
 */
export default function RechtsSeite(
  { titel, stand, kinder }: { titel: string; stand: string; kinder: ReactNode },
) {
  return (
    <main className="rs">
      <style>{STIL}</style>
      <h1>{titel}</h1>
      <p className="rs-stand">Stand: {stand}</p>
      {kinder}
    </main>
  );
}

const STIL = `
.rs { max-width: 48rem; margin: 0 auto; padding: 3rem 1.25rem 5rem;
      font: 400 1rem/1.7 system-ui, -apple-system, "Segoe UI", sans-serif; color: #16211d; }
.rs h1 { font-size: 2rem; line-height: 1.2; margin: 0 0 .25rem; letter-spacing: -.02em; }
.rs h2 { font-size: 1.2rem; margin: 2.5rem 0 .6rem; letter-spacing: -.01em; }
.rs h3 { font-size: 1rem; margin: 1.6rem 0 .3rem; }
.rs p { margin: .6rem 0; }
.rs-stand { font-size: .85rem; color: #5d7068; margin: 0 0 1.5rem;
            border-bottom: 1px solid #dde4e1; padding-bottom: 1rem; }
.rs-anschrift { font-style: normal; line-height: 1.8; }
.rs ul { margin: .6rem 0; padding-left: 1.15rem; }
.rs li { margin: .35rem 0; }
.rs-scroll { overflow-x: auto; }
.rs table { border-collapse: collapse; width: 100%; font-size: .9rem; margin: .6rem 0; }
.rs th, .rs td { border: 1px solid #dde4e1; padding: .5rem .7rem; text-align: left;
                 vertical-align: top; }
.rs thead th { background: #f2f6f4; font-size: .76rem; text-transform: uppercase;
               letter-spacing: .05em; color: #41534c; }
.rs tbody th { font-weight: 600; background: #fafcfb; }
.rs-hinweis { background: #fafcfb; border: 1px solid #dde4e1; border-left: 3px solid #b24a2e;
              padding: .8rem 1rem; margin: 1.2rem 0; font-size: .92rem; }
.rs-fuss { font-size: .85rem; color: #5d7068; margin-top: 3rem;
           border-top: 1px solid #dde4e1; padding-top: 1rem; }
@media (prefers-color-scheme: dark) {
  .rs { color: #e6ece9; }
  .rs-stand, .rs-fuss { color: #9fb0a9; border-color: #2c3a35; }
  .rs th, .rs td { border-color: #2c3a35; }
  .rs thead th { background: #1a2420; color: #c2cec9; }
  .rs tbody th { background: #151e1b; }
  .rs-hinweis { background: #151e1b; border-color: #2c3a35; border-left-color: #c96a4b; }
}
`;
