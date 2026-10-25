export const API_BASE = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/+$/, '');
export type Account = { email: string; business_id: string; csrf_token: string; onboarding_required: boolean };
let csrfToken = '';
export function setCsrfToken(value: string) { csrfToken = value; }

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function apiRequest<T>(url: string, payload?: unknown, signal?: AbortSignal, method: 'POST' | 'DELETE' = 'POST'): Promise<T> {
  const response = await fetch(url, { credentials: 'include', signal,
    ...(payload === undefined ? {} : { method,
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, body: JSON.stringify(payload) }),
  });
  if (!response.ok) {
    if (response.status === 401 && !url.includes('/auth/login') && !url.includes('/auth/signup')) {
      window.dispatchEvent(new Event('cashflow-session-expired'));
    }
    const result = await response.json().catch(() => ({}));
    const validationMessages = Array.isArray(result.detail)
      ? result.detail.flatMap((issue: unknown) => {
        if (!issue || typeof issue !== 'object' || !('msg' in issue) || typeof issue.msg !== 'string') return [];
        return [issue.msg];
      }).join(' ')
      : '';
    const message = typeof result.detail === 'string' ? result.detail : validationMessages;
    throw new ApiError(message || `Request failed (${response.status}). Check the entered values.`, response.status);
  }
  return response.status === 204 ? undefined as T : response.json();
}
