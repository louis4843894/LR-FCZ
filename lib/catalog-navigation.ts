export type CatalogQuery = Record<string, string | string[] | undefined>;

export function catalogParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    for (const part of Array.isArray(value) ? value : [value]) {
      if (part !== undefined && part !== "") params.append(key, part);
    }
  }
  return params;
}

export function catalogHref(path: string, query: CatalogQuery, change: CatalogQuery = {}): string {
  const params = catalogParams({ ...query, ...change });
  return `${path}${params.size ? `?${params}` : ""}`;
}

// Removing one repeated filter must keep the other selected effects and reset pagination.
export function removeCatalogFilter(query: CatalogQuery, key: string, value?: string): CatalogQuery {
  const result: CatalogQuery = { ...query, page: undefined };
  if (value === undefined) delete result[key];
  else {
    const current = result[key];
    result[key] = (Array.isArray(current) ? current : current === undefined ? [] : [current]).filter(part => part !== value);
  }
  return result;
}

export function catalogPageNumbers(page: number, pages: number): (number | "gap")[] {
  const kept = new Set([1, pages]);
  for (let n = Math.max(1, page - 1); n <= Math.min(pages, page + 1); n++) kept.add(n);
  const result: (number | "gap")[] = [];
  let previous = 0;
  for (const n of [...kept].sort((a, b) => a - b)) {
    if (n - previous === 2) result.push(n - 1);
    else if (n - previous > 2) result.push("gap");
    result.push(n);
    previous = n;
  }
  return result;
}
