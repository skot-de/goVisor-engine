"use client";

import { useMemo } from "react";
import { applyState, renderProfil, angaben } from "@/lib/explorerCore";

// Potenzial-Bereich (Unternehmenssicht): Chancen / Position / Profil.
// renderProfil kommt verbatim aus dem Prototyp; nur die Schale + Interaktion sind React.
export function ProfilView({
  potTab, profilStufe, offenerPicker, aktiveBranche, accountLimit, tick, onBodyAction,
}: {
  potTab: string;
  profilStufe: string;
  offenerPicker: string | null;
  aktiveBranche: string;
  accountLimit: boolean;
  tick: number;
  onBodyAction: (action: string, value: string, el: HTMLElement) => void;
}) {
  const html = useMemo(() => {
    applyState({ potTab, profilStufe, offenerPicker, aktiveBranche, accountLimit });
    return renderProfil();
    // tick erzwingt Neuberechnung nach In-Place-Mutationen (angaben, Partner-Schalter)
  }, [potTab, profilStufe, offenerPicker, aktiveBranche, accountLimit, tick]);

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    const t = e.target as HTMLElement;
    const actions = ["ptab", "pstufe", "partner", "angadd", "angset", "angrm", "editbestand"];
    for (const a of actions) {
      const el = t.closest<HTMLElement>(`[data-${a}]`);
      if (el) { onBodyAction(a, el.dataset[a] || "", el); return; }
    }
  }

  // Freitext-Eingaben (Auftragsgröße min/max) direkt in `angaben` schreiben — uncontrolled,
  // damit das Tippen im dangerouslySetInnerHTML-Baum nicht unterbrochen wird.
  function handleInput(e: React.FormEvent<HTMLDivElement>) {
    const el = e.target as HTMLInputElement;
    const key = el.dataset.ang;
    if (key) (angaben as Record<string, unknown>)[key] = el.value;
  }

  return <div onClick={handleClick} onInput={handleInput} dangerouslySetInnerHTML={{ __html: html }} />;
}
