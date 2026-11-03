/**
 * The only file that talks to the Django API.
 *
 *  - Keeps the JWT pair in localStorage (falls back to memory if storage is blocked).
 *  - Adds the access token to every request.
 *  - When the access token has expired (401), refreshes it ONCE (even if several
 *    requests fail at the same moment) and replays the request.
 *  - Turns every failure into an ApiError with a message a person can read.
 */

const BASE = (import.meta.env?.VITE_API_URL ?? "").replace(/\/$/, "");
const KEY = "fraudwatch.tokens";

let memory = null; // used when localStorage is unavailable
let onSessionLost = () => {};

export function setSessionLostHandler(fn) {
  onSessionLost = fn;
}

export function getTokens() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* storage blocked or corrupt: use memory */
  }
  return memory;
}

export function saveTokens(tokens) {
  memory = tokens;
  try {
    localStorage.setItem(KEY, JSON.stringify(tokens));
  } catch {
    /* keep the in-memory copy */
  }
}

export function clearTokens() {
  memory = null;
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing to do */
  }
}

export class ApiError extends Error {
  constructor(status, data, message) {
    super(message);
    this.status = status; // 0 means the server could not be reached
    this.data = data;
  }
}

/** Pick the most useful sentence out of a Django REST Framework error body. */
function messageFrom(status, data) {
  if (status === 0) return "Can't reach the server. Check that the backend is running.";
  if (status === 429) return "Too many attempts. Wait a minute and try again.";
  if (status >= 500) return "The server hit a problem. Try again in a moment.";
  if (data && typeof data === "object") {
    if (typeof data.detail === "string") return data.detail;
    const first = Object.values(data)[0];
    const text = Array.isArray(first) ? first[0] : first;
    if (typeof text === "string") return text;
    if (Array.isArray(data.non_field_errors)) return data.non_field_errors[0];
  }
  if (status === 403) return "You don't have permission to do that.";
  if (status === 404) return "That item no longer exists.";
  return "Something went wrong. Try again.";
}

function buildUrl(path, params) {
  const query = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, value);
  });
  const qs = query.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

async function send(path, { method = "GET", body, params, token }) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, null, messageFrom(0));
  }

  let data = null;
  if (response.status !== 204) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }
  if (!response.ok) throw new ApiError(response.status, data, messageFrom(response.status, data));
  return data;
}

// One refresh at a time: every request that fails together waits for the same one.
let refreshing = null;

function refreshAccessToken() {
  if (!refreshing) {
    const tokens = getTokens();
    refreshing = send("/api/auth/token/refresh/", {
      method: "POST",
      body: { refresh: tokens?.refresh },
    })
      .then((data) => {
        // Refresh-token rotation is on, so a new refresh token may come back too.
        saveTokens({ access: data.access, refresh: data.refresh ?? tokens.refresh });
        return data.access;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function request(path, options = {}) {
  const { auth = true, ...rest } = options;
  if (!auth) return send(path, rest);

  const tokens = getTokens();
  try {
    return await send(path, { ...rest, token: tokens?.access });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401 || !tokens?.refresh) throw error;
    try {
      const access = await refreshAccessToken();
      return await send(path, { ...rest, token: access });
    } catch (second) {
      if (second instanceof ApiError && second.status === 401) {
        clearTokens();
        onSessionLost();
        throw new ApiError(401, null, "Your session has ended. Sign in again.");
      }
      throw second;
    }
  }
}

/* ---- The endpoints the dashboard uses, in one place ---- */
export const api = {
  login: (email, password) =>
    request("/api/auth/login/", { method: "POST", body: { email, password }, auth: false }),
  logout: (refresh) => request("/api/auth/logout/", { method: "POST", body: { refresh } }),
  me: () => request("/api/auth/me/"),

  transactions: (params) => request("/api/transactions/", { params }),
  createTransaction: (body) => request("/api/transactions/", { method: "POST", body }),

  stats: () => request("/api/dashboard/stats/"),
  detections: (params) => request("/api/detections/", { params }),
  detection: (id) => request(`/api/detections/${id}/`),
  review: (id, body) => request(`/api/detections/${id}/review/`, { method: "POST", body }),

  settings: () => request("/api/settings/"),
  saveSettings: (body) => request("/api/settings/", { method: "PATCH", body }),
};
