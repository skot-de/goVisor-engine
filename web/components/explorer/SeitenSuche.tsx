"use client";
/**
 * Die Suchleiste der eigenstaendigen Seiten — damit die Topbar ueberall gleich aufgebaut ist.
 *
 * **Warum sie hier ueberhaupt steht.** Svens Vorgabe: „die topbar sollte im grundaufbau
 * immer gleich sein. die suche kann bleiben und nur die zusätzlichen sachen wie
 * filter/sortieren fallen halt raus." Genau so: Logo und Suche tragen alle Seiten, die
 * Listen-Werkzeuge (Filter, Spalten, Export) nur die Listen.
 *
 * **Und warum sie wirklich sucht.** Diese Seiten haben keinen Listenzustand — die Leiste
 * koennte hier reine Zierde sein. Eine Suche, die aussieht wie eine Suche und nichts tut,
 * ist schlimmer als keine: sie verspricht etwas. Deshalb schickt sie den Begriff als `?q=`
 * an die Akquise, die ihn dort in ein Such-Token verwandelt.
 */
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSprache } from "@/lib/i18n";

export function SeitenSuche() {
  const router = useRouter();
  const { t } = useSprache();
  const [wert, setWert] = useState("");

  function absenden(e: React.FormEvent) {
    e.preventDefault();
    const q = wert.trim();
    if (!q) return;
    router.push(`/leads?q=${encodeURIComponent(q)}`);
  }

  return (
    <form className="tsearch seitensuche" onSubmit={absenden} role="search">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.4-3.4" />
      </svg>
      <input
        value={wert}
        onChange={(e) => setWert(e.target.value)}
        placeholder={t("Suchen — Ort, PLZ, Auftraggeber, Stichwort")}
        aria-label={t("Suchen")}
        autoComplete="off"
      />
    </form>
  );
}
