"use client";

/** Die Reiter des Unternehmens-Bereichs — stehen in der Bereichsleiste des Rahmens.
 *
 * Sie lagen bis 2026-08-15 im Inhalt. Dort waren sie inhaltlich am falschen Ort (Navigation
 * unter einer Ueberschrift) und liessen die Bereichsleiste leer — der Rahmen haette dann
 * auf dieser Seite nur gepolstert statt getragen. */
import { useSprache } from "@/lib/i18n";
import type { UnTab } from "./UnternehmenView";

export function UnternehmenTabs({ tab, onTab }: { tab: UnTab; onTab: (t: UnTab) => void }) {
  const { t } = useSprache();
  return (
    <div className="un-tabs" role="tablist">
      {(["profil", "bilanz", "chancen"] as const).map((k) => (
        <button key={k} role="tab" aria-selected={tab === k}
          className={`un-tab ${tab === k ? "on" : ""}`} onClick={() => onTab(k)}>
          {k === "profil" ? t("Eignungsprofil") : k === "bilanz" ? t("Unsere Bilanz") : t("Chancen")}
        </button>
      ))}
    </div>
  );
}
