// An explicitly empty URL uses the website's own origin in the hosted build.
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export const getToken = () => sessionStorage.getItem("pulse-token");
export function setToken(token) {
  if (token) sessionStorage.setItem("pulse-token", token);
  else sessionStorage.removeItem("pulse-token");
}
export async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 40000);
  try {
    const response = await fetch(BASE + path, {
      ...options,
      signal: options.signal || controller.signal,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(getToken() ? { Authorization: "Bearer " + getToken() } : {}),
        ...options.headers,
      },
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      setToken(null);
      window.dispatchEvent(new Event("pulse-session-expired"));
    }
    if (!response.ok) {
      const error = new Error(
        typeof data.detail === "string"
          ? data.detail
          : "The request could not be completed.",
      );
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error(
        "This is taking longer than expected. Your assessment may already be saved; check your report before retrying.",
      );
    if (error instanceof TypeError)
      throw new Error(
        "Cannot reach AI Pulse. Check that the API is running and try again.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
