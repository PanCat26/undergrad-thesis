export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface ApiErrorBody {
  error: { code: string; message: string; detail?: unknown };
}

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: unknown;

  constructor(status: number, code: string, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
}

export async function apiRequest<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, token, signal } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "Cannot reach the server. Please try again.");
  }

  if (response.status === 204) return undefined as T;

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (!response.ok) {
    const errorBody = payload as ApiErrorBody | null;
    throw new ApiError(
      response.status,
      errorBody?.error?.code ?? "error",
      errorBody?.error?.message ?? "Something went wrong",
      errorBody?.error?.detail
    );
  }

  return payload as T;
}

interface ValidationDetail {
  loc?: (string | number)[];
  msg?: string;
}

/**
 * Turns an error into a user-facing message. For 422 validation errors it
 * surfaces the specific field reasons (e.g. password too short) instead of the
 * generic "Request validation failed".
 */
export function getErrorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof ApiError) {
    if (err.code === "validation_error" && Array.isArray(err.detail)) {
      const messages = (err.detail as ValidationDetail[])
        .map((item) => {
          const field = item.loc?.filter((part) => part !== "body").pop();
          return item.msg ? (field ? `${field}: ${item.msg}` : item.msg) : null;
        })
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
    return err.message;
  }
  return fallback;
}
