/**
 * Append a plate label to the print name. When `plateLabel` is provided (resolved
 * by the caller from the linked archive's plate list — see #881 follow-up), it
 * is used verbatim, including the explicit "Plate 1" case on multi-plate 3MFs.
 * Falls back to parsing `plate_N.gcode` from the MQTT gcode_file path, and in
 * that fallback we only show N > 1 because we can't tell from the path alone
 * whether the 3MF is multi-plate.
 */
export function formatPrintName(
  name: string | null,
  gcodeFile: string | null | undefined,
  t: (key: string, fallback: string, opts?: Record<string, unknown>) => string,
  plateLabel?: string | null,
): string {
  if (!name) return '';
  if (plateLabel) return `${name} — ${plateLabel}`;
  if (!gcodeFile) return name;
  const match = gcodeFile.match(/plate_(\d+)\.gcode/);
  if (match && parseInt(match[1], 10) > 1) {
    return `${name} — ${t('printers.plateNumber', 'Plate {{number}}', { number: match[1] })}`;
  }
  return name;
}


// Transport UUIDs are file identity, not a useful project title. Never use fuzzy
// matching: similarly named versions can be different prints.
export function resolvePrintDisplayName(
  raw: string | null | undefined,
  archives: { filename: string; print_name?: string | null }[] = [],
): string {
  if (!raw) return '';
  const stem = (s: string) => s.replace(/^.*[\\/]/, '').replace(/(?:\.gcode)?\.3mf$/i, '');
  const exact = archives.find(a => stem(a.filename) === stem(raw) && a.print_name?.trim());
  return exact?.print_name?.trim() || stem(raw).replace(/^checked-[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}-/i, '');
}
