/**
 * actor-store — tiny localStorage shim that remembers the operator's
 * name across browser sessions so the DecisionDialog can pre-fill it.
 *
 * Ships pre-auth: every verb-button asks "who is making this decision?"
 * and the answer should persist between actions in the same session.
 * When real auth lands the server-side user becomes the source of
 * truth and this becomes a no-op.
 */
const STORAGE_KEY = "ruflo.actor.name";

export function getStoredActor(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function setStoredActor(name: string): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = (name || "").trim().slice(0, 128);
    if (trimmed) {
      window.localStorage.setItem(STORAGE_KEY, trimmed);
    }
  } catch {
    /* ignore quota / private mode errors */
  }
}
