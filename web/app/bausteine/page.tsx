"use client";

import { BausteinLibrary } from "@/components/explorer/BausteinLibrary";
import { useState } from "react";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import { BausteineLeiste } from "@/components/explorer/BausteineLeiste";
import "../explorer.css";

// Ticket #23 §9 — Bausteinbibliothek als eigene Route, aber im GLEICHEN Gerüst wie die
// Lead-Ansichten: dieselbe Hauptnavigation links. Vorher war das eine Sackgasse mit
// Zurück-Link — wer hier landete, verlor jedes Menü.
export default function BausteinePage() {
  const [importOpen, setImportOpen] = useState(false);
  return (
    <div className="app">
      <AppTop leiste={<BausteineLeiste importOpen={importOpen} onImport={setImportOpen} />} />
      <div className="body">
        <AppRail current="bausteine" />
        {/* `.baust-page` traegt saemtliche Styles der Bibliothek (alle Regeln sind
            darunter geschachtelt) — die Klasse muss bleiben, auch wenn der frueher
            eigene Seitenrahmen weg ist. */}
        <div className="main seitenmain baust-page">
          <BausteinLibrary importOpen={importOpen} onImport={setImportOpen} />
        </div>
      </div>
    </div>
  );
}
