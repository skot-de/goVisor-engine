"use client";
import { useCallback, useEffect, useState } from "react";
import { useSprache } from "@/lib/i18n";

/* Posteingang in der Kopfleiste: Hinweise zu den beobachteten Leads.
 *
 * Bis zum 2026-08-22 gab es für Hinweise KEINEN Zustellweg — `lib/email.ts` ist ein Stub,
 * einen Posteingang gab es nicht, und die Startseite versprach trotzdem eine Meldung.
 * Dies ist der Weg: er braucht keinen Provider, keine verifizierte Absenderdomain und
 * keinen DNS-Eintrag, und er zeigt beim ersten Besuch schon etwas an, weil `/api/alerts`
 * beim Abruf rechnet statt auf einen nächtlichen Lauf zu warten. */

type Alert = {
  id: string; lead_id: string; typ: string; titel: string;
  tage: number | null; created_at: string; gesehen_am: string | null;
};

export function Posteingang({ onOeffneLead }: { onOeffneLead?: (id: string) => void }) {
  const { t } = useSprache();
  const [offen, setOffen] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [hinweis, setHinweis] = useState<string | null>(null);

  const laden = useCallback(async () => {
    try {
      const r = await fetch("/api/alerts");
      const d = await r.json();
      setAlerts(d.alerts || []);
      setHinweis(d.error || null);
    } catch { /* offline: der alte Stand bleibt stehen */ }
  }, []);

  useEffect(() => { laden(); }, [laden]);

  // Klick daneben schliesst das Fach. Dieselbe Bauform wie das Sprachmenü nebenan: die
  // Schliess-Logik gehört in die Komponente, nicht in die Shell — sonst funktioniert sie
  // genau so lange, wie sie dort gerendert wird.
  useEffect(() => {
    if (!offen) return;
    function daneben(e: MouseEvent) {
      if (!(e.target as HTMLElement).closest(".postcell")) setOffen(false);
    }
    document.addEventListener("mousedown", daneben);
    return () => document.removeEventListener("mousedown", daneben);
  }, [offen]);

  const ungelesen = alerts.filter((a) => !a.gesehen_am).length;

  async function alleGelesen() {
    setAlerts((as) => as.map((a) => ({ ...a, gesehen_am: a.gesehen_am || new Date().toISOString() })));
    try { await fetch("/api/alerts", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ alle: true }) }); } catch { /* beim nächsten Laden erneut */ }
  }

  function text(a: Alert): string {
    if (a.typ === "deadline_3d" || a.typ === "deadline_14d") {
      return a.tage === 0 ? t("Angebotsfrist läuft heute ab")
        : a.tage === 1 ? t("Angebotsfrist läuft morgen ab")
        : t("Angebotsfrist in {n} Tagen", { n: a.tage ?? 0 });
    }
    return t("Vertrag läuft in {n} Tagen aus", { n: a.tage ?? 0 });
  }

  return (
    <div className="colcfg postcell">
      <button className="colbtn" type="button" aria-haspopup="menu" aria-expanded={offen}
        onClick={() => setOffen((o) => !o)}
        title={ungelesen ? t("{n} neue Hinweise", { n: ungelesen }) : t("Hinweise")}>
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
          strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
          <path d="M13.7 21a2 2 0 01-3.4 0" />
        </svg>
        {ungelesen > 0 && <span className="post-zahl">{ungelesen}</span>}
      </button>

      <div className="colmenu postmenu" data-open={offen ? "" : undefined} role="menu">
        <div className="post-kopf">
          <b>{t("Hinweise")}</b>
          {ungelesen > 0 && (
            <button className="post-alle" onClick={alleGelesen}>{t("Alle gelesen")}</button>
          )}
        </div>
        {hinweis ? <div className="post-leer">{hinweis}</div>
          : !alerts.length ? (
            <div className="post-leer">
              {t("Keine Hinweise. Wir melden uns, wenn bei einem gemerkten Lead die Frist näher rückt oder ein Vertrag ausläuft.")}
            </div>
          ) : alerts.map((a) => (
            <button key={a.id} className={`post-z ${a.gesehen_am ? "" : "neu"}`}
              onClick={() => { onOeffneLead?.(a.lead_id); setOffen(false); }}>
              <span className="post-t">{text(a)}</span>
              <span className="post-n">{a.titel}</span>
            </button>
          ))}
      </div>
    </div>
  );
}
