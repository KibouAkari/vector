// Local, read-only aggregation. No source JSON is returned to the provider.
function boundedInteger(value, fallback, maximum, label) {
  const number = value ?? fallback;
  if (!Number.isInteger(number) || number < 1 || number > maximum) {
    throw new Error(`Invalid ${label}.`);
  }
  return number;
}

function absolutePath(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.length > 4096 ||
      value.includes('\0') || value.split('/').includes('..')) {
    throw new Error('An explicit absolute source path is required.');
  }
  return value;
}

function completeItems(bulk) {
  if (bulk?.complete !== true || bulk.truncated === true || bulk.scan_truncated === true ||
      !Array.isArray(bulk.items) || !Number.isInteger(bulk.files_discovered) ||
      bulk.files_discovered < 1 || bulk.files_discovered !== bulk.files_returned ||
      bulk.items.length !== bulk.files_returned || bulk.items.some(item => item?.truncated)) {
    throw new Error('Local rankings require every source file, without truncation.');
  }
  return bulk.items;
}

function parseItem(item) {
  try {
    const document = JSON.parse(item.content);
    if (!document || typeof document !== 'object' || Array.isArray(document)) throw new Error();
    return document;
  } catch {
    throw new Error('A ranking source is not a valid JSON object.');
  }
}

function metricValues(document, path) {
  let nodes = [document];
  for (const segment of path) {
    const next = [];
    for (const node of nodes) {
      if (!node || typeof node !== 'object') continue;
      if (segment.startsWith('*')) {
        const suffix = segment.slice(1);
        for (const [key, value] of Object.entries(node)) {
          if (key.endsWith(suffix)) next.push(value);
        }
      } else if (Object.hasOwn(node, segment)) {
        next.push(node[segment]);
      }
    }
    nodes = next;
  }
  return nodes;
}

export async function readServerJsonRankings(args, inspect, identityMapper) {
  const path = absolutePath(args?.path);
  const identityPath = args.identity_map_path ? absolutePath(args.identity_map_path) : '';
  const limit = boundedInteger(args.limit, 10, 50, 'ranking limit');
  const maxFiles = boundedInteger(args.max_files, 120, 120, 'file limit');
  const metrics = args.metrics;
  if (!Array.isArray(metrics) || metrics.length < 1 || metrics.length > 12) {
    throw new Error('Provide between one and twelve numeric ranking metrics.');
  }
  const seenLabels = new Set();
  for (const metric of metrics) {
    if (!metric || typeof metric.label !== 'string' || !metric.label.trim() || metric.label.length > 100 ||
        seenLabels.has(metric.label) || typeof metric.unit !== 'string' || metric.unit.length > 40 ||
        typeof metric.divisor !== 'number' || !Number.isFinite(metric.divisor) || metric.divisor <= 0 ||
        !Array.isArray(metric.value_paths) || metric.value_paths.length < 1 || metric.value_paths.length > 20) {
      throw new Error('Invalid or duplicate ranking metric.');
    }
    seenLabels.add(metric.label);
    const paths = new Set();
    for (const segments of metric.value_paths) {
      if (!Array.isArray(segments) || !segments.length || segments.length > 12 ||
          segments.some(part => typeof part !== 'string' || !part.length || part.length > 200 ||
            ['__proto__', 'prototype', 'constructor'].includes(part) ||
            (part.includes('*') && (part[0] !== '*' || part.slice(1).includes('*'))))) {
        throw new Error('Invalid numeric field path.');
      }
      const key = JSON.stringify(segments);
      if (paths.has(key)) throw new Error('Duplicate numeric field path.');
      paths.add(key);
    }
    // A single wildcard path can sum e.g. every Minecraft *_one_cm field.
    // Multiple wildcard paths could overlap and silently double-count values.
    if (metric.value_paths.length > 1 && metric.value_paths.some(parts => parts.some(p => p.startsWith('*')))) {
      throw new Error('Use one wildcard path or a list of exact field paths.');
    }
  }

  const bulk = await inspect({action: 'read_many', path, pattern: args.pattern || '*.json',
    recursive: Boolean(args.recursive), max_files: maxFiles});
  const items = completeItems(bulk);
  if (items.length > maxFiles) throw new Error('Source exceeds the requested file limit.');
  let names = new Map();
  if (identityPath) {
    const slash = identityPath.lastIndexOf('/');
    const identity = completeItems(await inspect({action: 'read_many',
      path: identityPath.slice(0, slash) || '/', pattern: identityPath.slice(slash + 1),
      recursive: false, max_files: 1}));
    if (identity.length !== 1) throw new Error('Expected one complete identity map.');
    // Identity maps may be arrays (e.g. usercache.json) or objects.
    try { names = identityMapper(JSON.parse(identity[0].content)); }
    catch { throw new Error('Invalid JSON identity map.'); }
  }

  const rankings = metrics.map(metric => ({label: metric.label, unit: metric.unit,
    divisor: metric.divisor, value_paths: metric.value_paths, missing: 0, invalid: 0, rows: []}));
  const sourceIds = new Set();
  for (const item of items) {
    const id = String(item.relative_path || item.path || '').replace(/\.json$/i, '');
    if (!id || sourceIds.has(id)) throw new Error('Missing or duplicate source identity.');
    sourceIds.add(id);
    const document = parseItem(item);
    const basename = id.split('/').pop();
    const name = names.get(basename.toLowerCase()) || null;
    for (const [index, metric] of metrics.entries()) {
      const values = metric.value_paths.flatMap(parts => metricValues(document, parts));
      const ranking = rankings[index];
      // Missing values stay missing. Never silently manufacture zero scores.
      if (!values.length || (metric.value_paths.length > 1 && values.length !== metric.value_paths.length)) {
        ranking.missing++;
        continue;
      }
      if (values.some(value => typeof value !== 'number' || !Number.isFinite(value) ||
          (Number.isInteger(value) && !Number.isSafeInteger(value)))) {
        ranking.invalid++;
        continue;
      }
      const raw = values.reduce((sum, value) => sum + value, 0);
      const value = raw / metric.divisor;
      if (!Number.isFinite(value) || (Number.isInteger(raw) && !Number.isSafeInteger(raw))) {
        ranking.invalid++;
        continue;
      }
      ranking.rows.push({id, name, value});
    }
  }
  for (const ranking of rankings) {
    ranking.rows.sort((a, b) => b.value - a.value || a.id.localeCompare(b.id, 'en'));
    ranking.valid_records = ranking.rows.length;
    ranking.rows = ranking.rows.slice(0, limit).map((row, index) => ({rank: index + 1, ...row}));
  }
  return {source_complete: true, files_processed: items.length, read_at: new Date().toISOString(),
    timestamp_note: 'read_at is the read time, not a verified statistics generation date.',
    local_processing: true, path, pattern: args.pattern || '*.json', limit, rankings};
}
