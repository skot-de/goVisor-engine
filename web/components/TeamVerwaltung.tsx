"use client";
/**
 * Team einer Organisation: Mitglieder + Einladungen (Seats, Phase 2b).
 *
 * Inhaber/Admins laden Kollegen per E-Mail ein (verbraucht einen Seat); Supabase verschickt
 * die Einladungs-Mail, und beim Registrieren landet der Eingeladene ueber `handle_new_user`
 * (0026) in DIESER Org statt in einer Solo-Org. Mitglieder sehen das Team nur.
 *
 * ⚠ Ohne angewandte Migration 0024/0026 meldet die API `team:false` und die Sektion zeigt
 * nur einen Hinweis.
 */
import { useEffect, useState } from "react";
import { useSprache } from "@/lib/i18n";

type Mitglied = { email: string; role: string };
type Einladung = { id: string; email: string; role: string };
type Daten = { team: boolean; role: string | null; mitglieder: Mitglied[]; einladungen: Einladung[] };

export default function TeamVerwaltung({ melde }: { melde: (m: string) => void }) {
  const { t } = useSprache();
  const [d, setD] = useState<Daten | null>(null);
  const [email, setEmail] = useState("");
  const [rolle, setRolle] = useState("member");
  const [busy, setBusy] = useState(false);

  async function laden() {
    const r = await fetch("/api/org/mitglieder", { cache: "no-store" });
    if (r.ok) setD(await r.json());
  }
  useEffect(() => { laden(); }, []);

  async function einladen() {
    if (!email.trim() || busy) return;
    setBusy(true);
    const r = await fetch("/api/org/mitglieder", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: email.trim(), role: rolle }),
    });
    setBusy(false);
    const j = await r.json().catch(() => ({}));
    if (r.ok) { setEmail(""); melde(j.warnung || t("Einladung verschickt")); laden(); }
    else melde(j.error || t("Einladen fehlgeschlagen"));
  }

  async function seatsKaufen() {
    const r = await fetch("/api/kauf/checkout", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ art: "seat", menge: 1 }),
    });
    const j = await r.json().catch(() => ({}));
    if (r.ok && j.url) { window.location.href = j.url; return; }
    melde(j.error || t("Kauf nicht möglich"));
  }

  async function zuruecknehmen(i: Einladung) {
    if (!window.confirm(t("Einladung an {e} zurücknehmen?").replace("{e}", i.email))) return;
    const r = await fetch(`/api/org/mitglieder?id=${encodeURIComponent(i.id)}`, { method: "DELETE" });
    if (r.ok) { melde(t("Zurückgenommen")); laden(); } else melde(t("Zurücknehmen fehlgeschlagen"));
  }

  if (!d) return <p className="spin">{t("Lade …")}</p>;
  if (!d.team) return <p className="set-hint">{t("Team-Funktionen sind für dieses Konto noch nicht aktiviert.")}</p>;

  const darfEinladen = d.role === "owner" || d.role === "admin";
  return (
    <div className="set-profile">
      <p className="set-hint">{t("Mitglieder")}</p>
      <ul className="pv-list">
        {d.mitglieder.map((m) => (
          <li key={m.email} className="pv-row">
            <span className="pv-name">{m.email}</span>
            <span className="pv-acts">{t(m.role === "owner" ? "Inhaber" : m.role === "admin" ? "Admin" : "Mitglied")}</span>
          </li>
        ))}
      </ul>

      {d.einladungen.length > 0 && <>
        <p className="set-hint">{t("Offene Einladungen")}</p>
        <ul className="pv-list">
          {d.einladungen.map((i) => (
            <li key={i.id} className="pv-row">
              <span className="pv-name">{i.email}</span>
              <span className="pv-acts">
                {t(i.role === "admin" ? "Admin" : "Mitglied")}
                {darfEinladen && <button className="pv-btn pv-del" onClick={() => zuruecknehmen(i)}>{t("Zurücknehmen")}</button>}
              </span>
            </li>
          ))}
        </ul>
      </>}

      {darfEinladen ? (
        <div className="pv-neu">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 placeholder={t("E-Mail des Kollegen")} />
          <select value={rolle} onChange={(e) => setRolle(e.target.value)} className="pv-btn">
            <option value="member">{t("Mitglied")}</option>
            <option value="admin">{t("Admin")}</option>
          </select>
          <button className="pv-btn" onClick={einladen} disabled={!email.trim() || busy}>{t("Einladen")}</button>
          <button className="pv-btn" onClick={seatsKaufen}>{t("Seat dazukaufen")}</button>
        </div>
      ) : (
        <p className="set-hint">{t("Nur Inhaber und Admins können Kollegen einladen.")}</p>
      )}
    </div>
  );
}
