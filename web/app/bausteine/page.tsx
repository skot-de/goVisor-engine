"use client";

import { BausteinLibrary } from "@/components/explorer/BausteinLibrary";
import { useState } from "react";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import { BausteineLeiste } from "@/components/explorer/BausteineLeiste";
import { BereichsNav } from "@/components/explorer/BereichsNav";
import "../explorer.css";

// Ticket #23 §9 — Bausteinbibliothek als eigene Route, aber im GLEICHEN Gerüst wie die
// Lead-Ansichten: dieselbe Hauptnavigation links. Vorher war das eine Sackgasse mit
// Zurück-Link — wer hier landete, verlor jedes Menü.
export default function BausteinePage() {
  const [importOpen, setImportOpen] = useState(false);
  const [theme, setTheme] = useState("");
  const [themen, setThemen] = useState<{ key: string; label: string; anzahl: number }[]>([]);
  return (
    <div className="app">
      <AppTop werkzeuge={<BausteineLeiste importOpen={importOpen} onImport={setImportOpen} />} />
      {/* Themen in derselben Zeile wie die Abschnitte der anderen Bereiche. Der
          Import-Knopf bleibt oben: er TUT etwas, er waehlt nichts aus. */}
      <div className="bereichsleiste">
        <BereichsNav aktiv={theme} onWechsel={setTheme} gruppen={[{ punkte: themen }]} />
      </div>
      <div className="body">
        <AppRail current="bausteine" />
        {/* `.baust-page` traegt saemtliche Styles der Bibliothek (alle Regeln sind
            darunter geschachtelt) — die Klasse muss bleiben, auch wenn der frueher
            eigene Seitenrahmen weg ist. */}
        <div className="main seitenmain baust-page">
          <BausteinLibrary importOpen={importOpen} onImport={setImportOpen}
            theme={theme} onTheme={setTheme} onThemen={setThemen} />
        </div>
      </div>
    </div>
  );
}
