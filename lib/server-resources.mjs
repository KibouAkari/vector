function measurement(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}

export function normalizeContainerResources(payload, sampledAt) {
  if (!payload || !Array.isArray(payload.containers)) {
    return {available: false, sampledAt: null, containers: [], runningCount: null};
  }
  const containers = payload.containers.filter(row =>
    row && typeof row.name === 'string' && row.name.trim()
  ).map(row => ({
    id: typeof row.id === 'string' ? row.id : row.name,
    name: row.name,
    cpuPercent: measurement(row.cpu_percent),
    memoryBytes: measurement(row.memory_usage_bytes),
    memoryLimitBytes: measurement(row.memory_limit_bytes),
    memoryPercent: measurement(row.memory_percent),
    pids: measurement(row.pids),
    networkIO: typeof row.network_io === 'string' ? row.network_io : null,
    blockIO: typeof row.block_io === 'string' ? row.block_io : null
  }));
  return {
    available: true, sampledAt, sample: 'one-shot', containers,
    runningCount: measurement(payload.running_count) ?? containers.length
  };
}

export function resourceBytes(value) {
  if (measurement(value) === null) return 'Unavailable';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) { amount /= 1024; unit++; }
  return `${amount.toLocaleString('en', {maximumFractionDigits: unit ? 2 : 0})} ${units[unit]}`;
}

export function resourcePercent(value) {
  return measurement(value) === null ? 'Unavailable' : `${value.toLocaleString('en', {maximumFractionDigits: 2})}%`;
}

export function sortedContainers(containers = [], sort = 'memory', query = '') {
  const field = sort === 'cpu' ? 'cpuPercent' : 'memoryBytes';
  const needle = query.trim().toLocaleLowerCase();
  return containers.filter(row => row.name.toLocaleLowerCase().includes(needle)).sort((a, b) => {
    if (sort === 'name') return a.name.localeCompare(b.name, 'en', {numeric:true});
    const av = measurement(a[field]);
    const bv = measurement(b[field]);
    if (av === null || bv === null) {
      if (av === bv) return a.name.localeCompare(b.name);
      return av === null ? 1 : -1;
    }
    return bv - av || a.name.localeCompare(b.name);
  });
}

export function topContainers(containers, metric) {
  const field = metric === 'cpu' ? 'cpuPercent' : 'memoryBytes';
  return sortedContainers(containers, metric).filter(row => measurement(row[field]) !== null).slice(0, 5);
}
