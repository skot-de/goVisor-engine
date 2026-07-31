"use client";

import Link from "next/link";
import { BausteinLibrary } from "@/components/explorer/BausteinLibrary";
import "../explorer.css";

// Ticket #23 §9 — Bausteinbibliothek als eigene Route. Lokal-first (localStorage); die
// verschlüsselte Ebene-B-Persistenz ist die Deploy-Schicht.
export default function BausteinePage() {
  return (
    <div className="baust-page">
      <header className="baust-top">
        <div className="logo">govisor</div>
        <Link href="/" className="baust-back">← Zurück zu den Leads</Link>
      </header>
      <BausteinLibrary />
    </div>
  );
}
