const API_URL = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail?.message ?? "The request could not be completed.", response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export function query(values: Record<string, string | number>): string {
  return new URLSearchParams(Object.entries(values).map(([key, value]) => [key, String(value)])).toString();
}
