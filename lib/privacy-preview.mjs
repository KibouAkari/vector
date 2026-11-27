// Offsets reveal no source values; selection is applied before resolving overlaps.
export function previewRanges(text, mappings) {
  const ranges = [];
  const placeholders = /<VEC_[A-Z_]+_[a-f0-9]{32}>|<[A-Z0-9_]+_[A-F0-9]{6}>/g;
  const parts = text.split(new RegExp(`(${placeholders.source})`, "g"));
  let base = 0;
  for (const part of parts) {
    if (new RegExp(`^(?:${placeholders.source})$`).test(part)) {
      base += part.length;
      continue;
    }
    for (const mapping of mappings) {
      if (!mapping.value) continue;
      const bounded = ["PERSON", "USERNAME"].includes(mapping.type);
      const escaped = mapping.value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const pattern = new RegExp(
        `(?=(${bounded ? "(?<![\\p{L}\\p{N}_])" : ""}${escaped}${bounded ? "(?![\\p{L}\\p{N}_])" : ""}))`,
        "gu",
      );
      for (const match of part.matchAll(pattern)) {
        ranges.push({
          start: base + match.index,
          end: base + match.index + mapping.value.length,
          placeholder: mapping.placeholder,
          type: mapping.type,
        });
      }
    }
    base += part.length;
  }
  return ranges.sort((a, b) => a.start - b.start || b.end - a.end);
}
export function previewSegments(text, ranges, selected) {
  const result = [];
  let offset = 0;
  const counts = {};
  const labels = new Map();
  for (const range of ranges || []) {
    if (!labels.has(range.placeholder)) {
      counts[range.type] = (counts[range.type] || 0) + 1;
      labels.set(range.placeholder, `[${range.type}_${counts[range.type]}]`);
    }
  }
  for (const range of ranges || []) {
    if (!selected.includes(range.placeholder) || range.start < offset || range.end > text.length) continue;
    if (range.start > offset)
      result.push({ text: text.slice(offset, range.start), masked: false });
    result.push({
      text: labels.get(range.placeholder),
      masked: true,
    });
    offset = range.end;
  }
  if (offset < text.length)
    result.push({ text: text.slice(offset), masked: false });
  return result;
}
