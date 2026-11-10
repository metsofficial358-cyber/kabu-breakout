import type { ChartResponse, Filters, RefreshStatus, ScreenResponse } from "./types";
import { filtersToApiQuery } from "./query";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { cache: "no-store", ...init });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export function fetchScreen(f: Filters, signal?: AbortSignal): Promise<ScreenResponse> {
  const extra: Record<string, string> = { limit: "200" };
  if (f.view === "table") extra.with_spark = "true";
  return request(`/api/screen?${filtersToApiQuery(f, extra)}`, { signal });
}

const chartCache = new Map<string, Promise<ChartResponse>>();

export function fetchChart(code: string, runDate: string | null, days = 120): Promise<ChartResponse> {
  const key = `${code}|${runDate}|${days}`;
  let p = chartCache.get(key);
  if (!p) {
    const q = new URLSearchParams({ days: String(days) });
    if (runDate) q.set("run_date", runDate);
    p = request<ChartResponse>(`/api/stocks/${encodeURIComponent(code)}/chart?${q}`);
    p.catch(() => chartCache.delete(key));
    chartCache.set(key, p);
  }
  return p;
}

export function clearChartCache() {
  chartCache.clear();
}

export async function startRefresh(): Promise<{ run_id: number; started: boolean }> {
  const res = await fetch("/api/refresh", { method: "POST" });
  const body = await res.json().catch(() => ({}));
  if (res.status === 202) return { run_id: body.run_id, started: true };
  if (res.status === 409) return { run_id: body.run_id, started: false }; // 既に実行中
  throw new ApiError(res.status, body.detail ?? `HTTP ${res.status}`);
}

export function fetchRefreshStatus(): Promise<RefreshStatus> {
  return request("/api/refresh/status");
}
