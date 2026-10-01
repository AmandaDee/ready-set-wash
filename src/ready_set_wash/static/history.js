const KEY = 'ready-set-wash:history:v1';

export function readHistory(storage = localStorage) {
  try {
    const rows = JSON.parse(storage.getItem(KEY) || '[]');
    return Array.isArray(rows) ? rows.filter(row => row && Number.isFinite(row.costPence) && typeof row.start === 'string' && Number.isFinite(Date.parse(row.start)) && typeof row.end === 'string' && Number.isFinite(Date.parse(row.end))).slice(0, 20) : [];
  } catch {
    return [];
  }
}

export function savePlan(plan, storage = localStorage) {
  try {
    storage.setItem(KEY, JSON.stringify([plan, ...readHistory(storage)].slice(0, 20)));
  } catch {
  }
}

export function clearHistory(storage = localStorage) {
  try {
    storage.removeItem(KEY);
  } catch {
  }
}
