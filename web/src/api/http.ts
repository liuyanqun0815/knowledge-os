const ADMIN_TOKEN_KEY = "akos_admin_token";

function mergeHeaders(init?: HeadersInit): Record<string, string> {
  const headers: Record<string, string> = {};
  if (!init) {
    return headers;
  }
  if (init instanceof Headers) {
    init.forEach((value, key) => {
      headers[key] = value;
    });
    return headers;
  }
  if (Array.isArray(init)) {
    for (const [key, value] of init) {
      headers[key] = value;
    }
    return headers;
  }
  return { ...init };
}

export function getAdminToken(): string | null {
  const stored = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (stored) {
    return stored;
  }
  const envToken = import.meta.env.VITE_ADMIN_API_TOKEN;
  return envToken || null;
}

export function setAdminToken(token: string): void {
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = mergeHeaders(init.headers);
  const token = getAdminToken();
  if (token) {
    headers["X-Admin-Token"] = token;
  }

  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status}: ${body}`);
  }
  return response;
}
