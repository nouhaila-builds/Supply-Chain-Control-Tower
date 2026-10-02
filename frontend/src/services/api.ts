import type { Filters } from "../types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function toParams(filters: Partial<Filters>, extra?: Record<string, string | string[] | undefined>): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  if (extra) {
    for (const [key, value] of Object.entries(extra)) {
      if (!value) continue;
      if (Array.isArray(value)) value.forEach((item) => params.append(key, item));
      else params.set(key, value);
    }
  }
  return params;
}

export async function getJson<T>(path: string, filters?: Partial<Filters>, extra?: Record<string, string | string[] | undefined>): Promise<T> {
  const params = toParams(filters ?? {}, extra);
  const query = params.toString();
  const response = await fetch(`/api${path}${query ? `?${query}` : ""}`);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : "Request failed");
  }
  return response.json() as Promise<T>;
}
