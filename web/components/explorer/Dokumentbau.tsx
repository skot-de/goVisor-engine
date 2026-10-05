"use client";
import { useCallback, useEffect, useState } from "react";

/* Dokumente aus Bausteinen zusammenstellen (Phase 1, Plan: `docs/funktion-dokument-bauen.md`).
 *
 * Links die Bibliothek, rechts das Dokument, dazwischen „uebernehmen". Ueberschriften und freier
 * Text als eigene Teilarten. Gespeichert wird auf Knopfdruck, nicht laufend.
 *
 * ⚠ SORTIEREN MIT KNOEPFEN, NICHT MIT ZIEHEN. Ziehen braucht entweder eine Bibliothek oder viel
 * eigenen Code, und es ist mit der Tastatur nicht bedienbar. Hoch und runter sind langweilig,
 * funktionieren aber ueberall und auch fuer jemanden, der keine Maus benutzt.
 *
 * ⚠ EIN TEIL DER ART `baustein` TRAEGT KEINEN TEXT, sondern eine Kennung. Was hier angezeigt
 * wird, kommt beim Laden aus der Bibliothek. Wer den Baustein pflegt, pflegt damit jedes
 * Dokument, das auf ihn zeigt — genau das ist der Zweck (s. Schema 0038).
 *
 * ⚠ Keine Gedankenstriche in den Texten dieser Datei (Vorgabe Sven).
 */

type Art = "baustein" | "ueberschrift" | "text";
type Teil = {
  art: Art; baustein_id: string | null; inhalt: string | null;
  ebene: number | null; thema?: string | null; quelle_fehlt?: boolean;
};
type DokKopf = { id: string; titel: string; lead_id: string | null; updated_at: string;
                 eigen?: boolean };
type Baustein = { id: string; theme: string; content: string };

const THEMEN: Record<string, string> = {
  referenzen: "Referenzen", unternehmensdarstellung: "Unternehmensdarstellung",
  zertifikate_qm: "Zertifikate & QM", datenschutz_avv: "Datenschutz & AVV",
  projektorganisation: "Projektorganisation", personal_qualifikation: "Personal & Qualifikation",
  technische_ausstattung: "Technische Ausstattung", nachhaltigkeit: "Nachhaltigkeit",
  sonstiges: "Sonstiges",
};

export function Dokumentbau() {
  const [liste, setListe] = useState<DokKopf[]>([]);
  const [dok, setDok] = useState<DokKopf | null>(null);
  const [teile, setTeile] = useState<Teil[]>([]);
  const [bausteine, setBausteine] = useState<Baustein[]>([]);
  const [thema, setThema] = useState("");
  const [fehler, setFehler] = useState("");
  const [hinweis, setHinweis] = useState("");
  const [busy, setBusy] = useState(false);
  const [schmutzig, setSchmutzig] = useState(false);

  const ladeListe = useCallback(async () => {
    try {
      const d = await (await fetch("/api/dokument")).json();
      if (d.error) { setFehler(d.error); return; }
      setListe(d.dokumente || []);
    } catch { setFehler("Die Dokumente konnten nicht geladen werden."); }
  }, []);

  useEffect(() => {
    ladeListe();
    (async () => {
      try {
        const d = await (await fetch("/api/blocks")).json();
        setBausteine((d.blocks || []).filter((b: Baustein) => b.id && b.content));
      } catch { /* ohne Bibliothek bleibt die linke Spalte leer, das ist sichtbar genug */ }
    })();
  }, [ladeListe]);

  async function oeffne(id: string) {
    setBusy(true); setFehler(""); setHinweis("");
    try {
      const d = await (await fetch(`/api/dokument?id=${encodeURIComponent(id)}`)).json();
      if (d.error) { setFehler(d.error); return; }
      setDok(d.dokument); setTeile(d.teile || []); setSchmutzig(false);
    } catch { setFehler("Das Dokument konnte nicht geladen werden."); }
    finally { setBusy(false); }
  }

  async function neu() {
    setBusy(true); setFehler("");
    try {
      const d = await (await fetch("/api/dokument", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ titel: "Neues Dokument" }),
      })).json();
      if (d.error || !d.dokument) { setFehler(d.error || "Anlegen fehlgeschlagen."); return; }
      setDok(d.dokument); setTeile([]); setSchmutzig(false);
      await ladeListe();
    } catch { setFehler("Anlegen fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  async function sichern() {
    if (!dok) return;
    setBusy(true); setFehler(""); setHinweis("");
    try {
      const r = await fetch(`/api/dokument?id=${encodeURIComponent(dok.id)}`, {
        method: "PATCH", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          titel: dok.titel,
          teile: teile.map((t) => ({ art: t.art, baustein_id: t.baustein_id,
                                     inhalt: t.inhalt, ebene: t.ebene })),
        }),
      });
      const d = await r.json();
      if (d.error) { setFehler(d.error); return; }
      setSchmutzig(false); setHinweis("Gespeichert.");
      await ladeListe();
    } catch { setFehler("Speichern fehlgeschlagen."); }
    finally { setBusy(false); }
  }

  async function loesche() {
    if (!dok) return;
    setBusy(true);
    try {
      await fetch(`/api/dokument?id=${encodeURIComponent(dok.id)}`, { method: "DELETE" });
      setDok(null); setTeile([]); await ladeListe();
    } finally { setBusy(false); }
  }

  const aendern = (f: (t: Teil[]) => Teil[]) => { setTeile(f); setSchmutzig(true); };

  const uebernehmen = (b: Baustein) =>
    aendern((t) => [...t, { art: "baustein", baustein_id: b.id, inhalt: null, ebene: null,
                            thema: b.theme }]);
  const ueberschrift = () =>
    aendern((t) => [...t, { art: "ueberschrift", baustein_id: null, inhalt: "Neue Ueberschrift",
                            ebene: 2 }]);
  const freitext = () =>
    aendern((t) => [...t, { art: "text", baustein_id: null, inhalt: "", ebene: null }]);

  function schiebe(i: number, um: number) {
    aendern((t) => {
      const n = [...t];
      const ziel = i + um;
      if (ziel < 0 || ziel >= n.length) return t;
      [n[i], n[ziel]] = [n[ziel], n[i]];
      return n;
    });
  }

  /* Einen Baustein-Teil in freien Text umwandeln: die Fassung wird eingefroren. Ausdruecklich
   * und auf Knopfdruck, nie automatisch — s. Schema 0038. */
  function einfrieren(i: number) {
    aendern((t) => t.map((x, j) => (j === i && x.art === "baustein" && x.inhalt
      ? { art: "text" as Art, baustein_id: null, inhalt: x.inhalt, ebene: null } : x)));
  }

  const gefiltert = thema ? bausteine.filter((b) => b.theme === thema) : bausteine;
  const themenImBestand = [...new Set(bausteine.map((b) => b.theme))];

  return (
    <section className="dok">
      <div className="dok-kopf">
        <h2 className="dok-titel">Dokument aus Bausteinen</h2>
        <div className="dok-leiste">
          <select className="dok-wahl" value={dok?.id || ""} disabled={busy}
            onChange={(e) => (e.target.value ? oeffne(e.target.value) : setDok(null))}>
            <option value="">Dokument waehlen</option>
            {liste.map((d) => (
              <option key={d.id} value={d.id}>
                {d.titel}{d.eigen === false ? " (Kollegin)" : ""}
              </option>
            ))}
          </select>
          <button className="dok-knopf" onClick={neu} disabled={busy}>Neues Dokument</button>
          {schmutzig && <span className="dok-schmutzig">nicht gespeichert</span>}
          {fehler && <span className="dok-fehler">{fehler}</span>}
          {hinweis && !fehler && <span className="dok-hinweis">{hinweis}</span>}
        </div>
      </div>

      {!dok ? (
        <p className="dok-hilfe">
          Waehlen Sie ein Dokument oder legen Sie eines an. Ein Dokument ist eine geordnete Folge
          aus Bausteinen, Ueberschriften und eigenem Text. Bausteine werden verwiesen, nicht
          kopiert: wer einen Baustein pflegt, pflegt jedes Dokument, das ihn verwendet.
        </p>
      ) : (
        <>
          <input className="dok-name" value={dok.titel} disabled={busy}
            onChange={(e) => { setDok({ ...dok, titel: e.target.value }); setSchmutzig(true); }} />

          <div className="dok-spalten">
            <div className="dok-vorrat">
              <h3 className="dok-unter">Bibliothek ({gefiltert.length})</h3>
              <div className="dok-themen">
                <button className={`dok-thema${thema ? "" : " dok-an"}`}
                  onClick={() => setThema("")}>Alle</button>
                {themenImBestand.map((t) => (
                  <button key={t} className={`dok-thema${thema === t ? " dok-an" : ""}`}
                    onClick={() => setThema(t)}>{THEMEN[t] || t}</button>
                ))}
              </div>
              {gefiltert.length === 0 && (
                <p className="dok-leer">
                  Keine Bausteine vorhanden. Legen Sie welche in der Bibliothek an, aus der
                  Checkliste oder aus einem alten Angebot.
                </p>
              )}
              {gefiltert.map((b) => (
                <article key={b.id} className="dok-baustein">
                  <span className="dok-marke">{THEMEN[b.theme] || b.theme}</span>
                  <p className="dok-auszug">{b.content.slice(0, 180)}
                    {b.content.length > 180 ? " ..." : ""}</p>
                  <button className="dok-uebernehmen" onClick={() => uebernehmen(b)}>
                    uebernehmen
                  </button>
                </article>
              ))}
            </div>

            <div className="dok-ziel">
              <h3 className="dok-unter">Dokument ({teile.length})</h3>
              <div className="dok-werkzeuge">
                <button className="dok-klein" onClick={ueberschrift}>Ueberschrift</button>
                <button className="dok-klein" onClick={freitext}>Eigener Text</button>
                <button className="dok-knopf" onClick={sichern} disabled={busy || !schmutzig}>
                  Speichern
                </button>
                <button className="dok-klein dok-weg" onClick={loesche} disabled={busy}>
                  Dokument loeschen
                </button>
              </div>

              {teile.length === 0 && (
                <p className="dok-leer">
                  Noch leer. Uebernehmen Sie links einen Baustein, oder legen Sie eine
                  Ueberschrift an.
                </p>
              )}

              {teile.map((t, i) => (
                <article key={i} className={`dok-teil dok-${t.art}${t.quelle_fehlt ? " dok-kaputt" : ""}`}>
                  <header className="dok-teilkopf">
                    <span className="dok-art">
                      {t.art === "baustein" ? (THEMEN[t.thema || ""] || "Baustein")
                        : t.art === "ueberschrift" ? `Ueberschrift ${t.ebene}` : "Eigener Text"}
                    </span>
                    <span className="dok-knoepfe">
                      <button onClick={() => schiebe(i, -1)} disabled={i === 0}
                        aria-label="nach oben">hoch</button>
                      <button onClick={() => schiebe(i, 1)} disabled={i === teile.length - 1}
                        aria-label="nach unten">runter</button>
                      {t.art === "baustein" && !t.quelle_fehlt && (
                        <button onClick={() => einfrieren(i)}
                          title="Diese Fassung einfrieren, spaetere Pflege wirkt dann nicht mehr">
                          einfrieren
                        </button>
                      )}
                      <button className="dok-weg"
                        onClick={() => aendern((x) => x.filter((_, j) => j !== i))}
                        aria-label="entfernen">entfernen</button>
                    </span>
                  </header>

                  {/* ⚠ Eine fehlende Quelle wird GEZEIGT, nicht verschwiegen. Ein stillschweigend
                      leerer Absatz liesse das Dokument vollstaendig aussehen, obwohl es das
                      nicht ist. */}
                  {t.quelle_fehlt ? (
                    <p className="dok-warnung">
                      Die Quelle dieses Teils ist nicht mehr da. Der Baustein wurde geloescht
                      oder laesst sich nicht lesen. Bitte entfernen oder ersetzen.
                    </p>
                  ) : t.art === "baustein" ? (
                    <p className="dok-inhalt">{t.inhalt}</p>
                  ) : (
                    <textarea className="dok-eingabe" value={t.inhalt || ""}
                      rows={t.art === "ueberschrift" ? 1 : 4}
                      onChange={(e) => aendern((x) => x.map((y, j) =>
                        (j === i ? { ...y, inhalt: e.target.value } : y)))} />
                  )}
                </article>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
