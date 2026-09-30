"use client";
/**
 * Kuratierung (Admin-Portal, Bereich 5). Ansicht + Pflege der curated/-CSVs, die den naechsten
 * Gold-/Silber-Lauf steuern. Quelle: /api/intern/kuratierung. Middleware sperrt /intern auf istAdmin.
 * Schreiben auf data/-Dateien ist serverseitig fail-closed gegen laufende Laeufe abgesichert.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import "../../intern.css";

type Art = {
  id: string; label: string; editierbar: boolean; perLand: boolean; laender: string[] | null;
  gross: boolean; hinweis: string; pfad: string; unterData: boolean; vorhanden: boolean;
  zeilen: number | null; stand: string | null;
};
type Detail = {
  id: string; label: string; editierbar: boolean; gross?: boolean; perLand?: boolean;
  laender?: string[] | null; spalten: string[]; pflicht?: string[];
  zeilen?: Record<string, string>[]; probe?: Record<string, string>[]; count?: number;
  pfad: string; unterData?: boolean; hinweis: string; wirkung?: string;
};

const LAENDER = ["DE", "AT", "CH", "LU"];

export default function KuratierungPage() {
  const [land, setLand] = useState("DE");
  const [index, setIndex] = useState<Art[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [entwurf, setEntwurf] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const ladeIndex = useCallback(async () => {
    try {
      const r = await fetch(`/api/intern/kuratierung?country=${land}`, { cache: "no-store" });
      if (r.status === 404) { setFehler("Kein Zugriff — als Admin anmelden (istAdmin)."); return; }
      const j = await r.json();
      setIndex(j.arten); setFehler(null);
    } catch { setFehler("Laden fehlgeschlagen."); }
  }, [land]);

  const ladeDetail = useCallback(async (id: string) => {
    setDetail(null); setEntwurf({});
    try {
      const r = await fetch(`/api/intern/kuratierung?kind=${id}&country=${land}`, { cache: "no-store" });
      const j = await r.json();
      if (j.error) { setFehler(j.error); return; }
      setDetail(j); setFehler(null);
    } catch { setFehler("Laden fehlgeschlagen."); }
  }, [land]);

  useEffect(() => { ladeIndex(); }, [ladeIndex]);
  useEffect(() => { if (sel) ladeDetail(sel); }, [sel, land, ladeDetail]);

  const anlegen = async () => {
    if (!detail) return;
    setBusy(true); setFehler(null);
    try {
      const r = await fetch("/api/intern/kuratierung", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ kind: detail.id, country: land, action: "append", row: entwurf }),
      });
      const j = await r.json();
      if (!r.ok) { setFehler(j.error || "Anlegen fehlgeschlagen."); return; }
      setEntwurf({}); await ladeDetail(detail.id); await ladeIndex();
    } finally { setBusy(false); }
  };

  const loeschen = async (i: number) => {
    if (!detail) return;
    setBusy(true); setFehler(null);
    try {
      const r = await fetch("/api/intern/kuratierung", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ kind: detail.id, country: land, action: "delete", index: i }),
      });
      const j = await r.json();
      if (!r.ok) { setFehler(j.error || "Loeschen fehlgeschlagen."); return; }
      await ladeDetail(detail.id); await ladeIndex();
    } finally { setBusy(false); }
  };

  const rows = detail?.zeilen ?? detail?.probe ?? [];

  return (
    <main className="cp-wrap">
      <header className="cp-top">
        <h1>Kuratierung</h1>
        <nav className="cp-nav">
          <Link href="/intern/betrieb">Betrieb</Link>
          <Link href="/intern/konten">Konten</Link>
          <Link href="/intern/qualitaet">Datenqualität</Link>
          <Link href="/intern/kosten">LLM & Kosten</Link>
          <select value={land} onChange={(e) => setLand(e.target.value)} aria-label="Land">
            {LAENDER.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </nav>
      </header>
      {fehler && <p className="cp-hinweis">{fehler}</p>}

      <div className="kur-split">
        <aside className="kur-liste">
          {(index ?? []).map((a) => {
            const gesperrt = a.perLand && a.laender && !a.laender.includes(land);
            return (
              <button key={a.id} className={`kur-eintrag ${sel === a.id ? "kur-aktiv" : ""}`}
                disabled={!!gesperrt} onClick={() => setSel(a.id)}>
                <span className="kur-name">{a.label}</span>
                <span className="kur-meta">
                  {gesperrt ? `nur ${a.laender?.join("/")}`
                    : a.vorhanden ? `${a.zeilen ?? "—"} Zeilen · ${a.stand ?? ""}` : "leer"}
                  {a.editierbar ? "" : " · Ansicht"}
                  {a.unterData ? " · data/" : ""}
                </span>
              </button>
            );
          })}
        </aside>

        <section className="kur-detail">
          {!detail && <p className="cp-klein">Links eine Kuratierungsquelle waehlen.</p>}
          {detail && <>
            <h3>{detail.label}</h3>
            <p className="cp-klein">{detail.hinweis}</p>
            <p className="cp-klein">Datei: <code>{detail.pfad}</code>{detail.unterData ? " (externe Platte)" : ""}</p>
            {detail.wirkung && <p className="cp-klein">⚠ {detail.wirkung}</p>}
            {detail.gross && <p className="cp-klein">Grosse Datei — Vorschau der ersten {rows.length} von {detail.count} Zeilen.</p>}

            <div className="kur-tabelle">
              <table>
                <thead><tr>
                  {detail.spalten.map((s) => <th key={s}>{s}</th>)}
                  {detail.editierbar && <th></th>}
                </tr></thead>
                <tbody>
                  {detail.editierbar && (
                    <tr className="kur-neu">
                      {detail.spalten.map((s) => (
                        <td key={s}>
                          <input value={entwurf[s] ?? ""} placeholder={detail.pflicht?.includes(s) ? "Pflicht" : ""}
                            onChange={(e) => setEntwurf({ ...entwurf, [s]: e.target.value })} />
                        </td>
                      ))}
                      <td><button onClick={anlegen} disabled={busy}>+ anlegen</button></td>
                    </tr>
                  )}
                  {rows.map((z, i) => (
                    <tr key={i}>
                      {detail.spalten.map((s) => <td key={s} title={z[s]}>{z[s]}</td>)}
                      {detail.editierbar && (
                        <td><button className="kur-del" onClick={() => loeschen(i)} disabled={busy}>löschen</button></td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>}
        </section>
      </div>
    </main>
  );
}
