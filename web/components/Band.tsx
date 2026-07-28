/**
 * Band-Meter (drei Segmente) — verbatim aus dem Prototyp.
 * Zeigt eine grobe Höhe (hoch/mittel/niedrig) ohne Scheingenauigkeit.
 * `na` = keine Grundlage: gestrichelt, kursives Label — sichtbar anders als „niedrig".
 */
export function Band({
  level,
  label,
}: {
  level: "hoch" | "mittel" | "niedrig" | "na";
  label?: string;
}) {
  return (
    <span className="band" data-level={level}>
      <span className="segs">
        <i />
        <i />
        <i />
      </span>
      {label ? <span className="lbl">{label}</span> : null}
    </span>
  );
}
