// Offsets reveal no source values. Overlaps are resolved longest-first.
export function previewRanges(text, mappings) {
  const ranges = [];
  for (const mapping of [...mappings].sort(
    (a, b) => b.value.length - a.value.length,
  )) {
    let at = 0;
    while ((at = text.indexOf(mapping.value, at)) !== -1) {
      const end = at + mapping.value.length;
      const bounded = ["PERSON", "USERNAME"].includes(mapping.type);
      if (
        (!bounded ||
          (!/[\p{L}\p{N}_]/u.test(text[at - 1] || "") &&
            !/[\p{L}\p{N}_]/u.test(text[end] || ""))) &&
        !ranges.some((r) => at < r.end && end > r.start)
      )
        ranges.push({
          start: at,
          end,
          placeholder: mapping.placeholder,
          type: mapping.type,
        });
      at = end;
    }
  }
  return ranges.sort((a, b) => a.start - b.start);
}
export function previewSegments(text, ranges, selected) {
  const result = [];
  let offset = 0;
  const counts = {};
  const labels = new Map();
  for (const range of ranges || []) {
    if (range.start < offset || range.end > text.length) continue;
    if (!labels.has(range.placeholder)) {
      counts[range.type] = (counts[range.type] || 0) + 1;
      labels.set(range.placeholder, `[${range.type}_${counts[range.type]}]`);
    }
    if (range.start > offset)
      result.push({ text: text.slice(offset, range.start), masked: false });
    result.push({
      text: selected.includes(range.placeholder)
        ? labels.get(range.placeholder)
        : text.slice(range.start, range.end),
      masked: selected.includes(range.placeholder),
    });
    offset = range.end;
  }
  if (offset < text.length)
    result.push({ text: text.slice(offset), masked: false });
  return result;
}
