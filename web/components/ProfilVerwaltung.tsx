"use client";
/**
 * Profil-Umschalter + Profil-Verwaltung (Mehrfachprofile, Phase 2b).
 *
 * Eine Organisation kann mehrere Suchprofile fuehren (z. B. je Sparte/Region); ein Nutzer
 * nutzt genau eines aktiv und kann wechseln. Diese Sektion listet die Profile der eigenen
 * Org, schaltet um (`/api/profil/wechseln`) und legt an/benennt um/loescht (`/api/profil`).
 *
 * ⚠ Solange die Migration 0024/0025 nicht angewandt ist, liefert die API `mehrfach:false`;
 * dann zeigt die Sektion nur einen Hinweis statt einer leeren Liste.
 */
import { useEffect, useState } from "react";
import { useSprache } from "@/lib/i18n";
import { wechsleProfil } from "@/lib/useProfil";

type Prof = { id: string; name: string; active: boolean };
type Liste = { mehrfach: boolean; aktiv: string | null; limit: number; profiles: Prof[] };

export default function ProfilVerwaltung({ melde }: { melde: (m: string) => void }) {
  const { t } = useSprache();
  const [d, setD] = useState<Liste | null>(null);
  const [neu, setNeu] = useState("");
  const [busy, setBusy] = useState(false);

  async function laden() {
    const r = await fetch("/api/profil", { cache: "no-store" });
    if (r.ok) setD(await r.json());
  }
  useEffect(() => { laden(); }, []);

  async function anlegen() {
    if (!neu.trim() || busy) return;
    setBusy(true);
    const r = await fetch("/api/profil", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: neu.trim() }),
    });
    setBusy(false);
    const j = await r.json().catch(() => ({}));
    if (r.ok) { setNeu(""); melde(t("Profil angelegt")); laden(); }
    else melde(j.error || t("Anlegen fehlgeschlagen"));
  }

  async function umbenennen(p: Prof) {
    const name = window.prompt(t("Neuer Name"), p.name);
    if (!name || name === p.name) return;
    const r = await fetch("/api/profil", {
      method: "PATCH", headers: { "content-type": "application/json" },
      body: JSON.stringify({ id: p.id, name }),
    });
    if (r.ok) { melde(t("Umbenannt")); laden(); } else melde(t("Umbenennen fehlgeschlagen"));
  }

  async function loeschen(p: Prof) {
    if (!window.confirm(t("Profil „{n}“ wirklich löschen?").replace("{n}", p.name))) return;
    const r = await fetch(`/api/profil?id=${encodeURIComponent(p.id)}`, { method: "DELETE" });
    const j = await r.json().catch(() => ({}));
    if (r.ok) { melde(t("Gelöscht")); laden(); } else melde(j.error || t("Löschen fehlgeschlagen"));
  }

  async function kaufen() {
    const r = await fetch("/api/kauf/checkout", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ art: "profile", menge: 1 }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok && j.url) { window.location.href = j.url; return; }
    melde(j.error || t("Kauf nicht möglich"));
  }

  async function wechseln(p: Prof) {
    if (p.active || busy) return;
    setBusy(true);
    const ok = await wechsleProfil(p.id);
    setBusy(false);
    if (ok) { melde(t("Profil gewechselt")); laden(); } else melde(t("Wechseln fehlgeschlagen"));
  }

  if (!d) return <p className="spin">{t("Lade …")}</p>;
  if (!d.mehrfach) {
    return <p className="set-hint">{t("Mehrfachprofile sind für dieses Konto noch nicht aktiviert.")}</p>;
  }

  const voll = d.profiles.length >= d.limit;
  return (
    <div className="set-profile">
      <p className="set-hint">
        {t("{n} von {max} Profilen").replace("{n}", String(d.profiles.length)).replace("{max}", String(d.limit))}
      </p>
      <ul className="pv-list">
        {d.profiles.map((p) => (
          <li key={p.id} className={`pv-row ${p.active ? "pv-active" : ""}`}>
            <span className="pv-name">{p.name}{p.active ? ` · ${t("aktiv")}` : ""}</span>
            <span className="pv-acts">
              {!p.active && <button className="pv-btn" onClick={() => wechseln(p)}>{t("Wechseln")}</button>}
              <button className="pv-btn" onClick={() => umbenennen(p)}>{t("Umbenennen")}</button>
              {!p.active && d.profiles.length > 1 &&
                <button className="pv-btn pv-del" onClick={() => loeschen(p)}>{t("Löschen")}</button>}
            </span>
          </li>
        ))}
      </ul>
      <div className="pv-neu">
        <input value={neu} onChange={(e) => setNeu(e.target.value)} maxLength={80}
               placeholder={t("Name des neuen Profils")} disabled={voll} />
        <button className="pv-btn" onClick={anlegen} disabled={voll || !neu.trim() || busy}>
          {t("Profil anlegen")}
        </button>
      </div>
      {voll && (
        <p className="set-hint">
          {t("Kontingent erreicht — weitere Profile sind kostenpflichtig.")}{" "}
          <button className="pv-btn" onClick={kaufen}>{t("Profil dazukaufen")}</button>
        </p>
      )}
    </div>
  );
}
