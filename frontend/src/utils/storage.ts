// Browser storage throws when a private window, a browser policy or a full quota blocks it.
// The property access itself can throw, so each call stays inside the guard.
function guarded(open: () => Storage) {
  return {
    get(key: string) {
      try { return open().getItem(key) } catch { return null }
    },
    set(key: string, value: string) {
      try { open().setItem(key, value) } catch { /* Preferences fall back to their defaults. */ }
    },
    remove(key: string) {
      try { open().removeItem(key) } catch { /* Nothing to clear without storage. */ }
    },
  }
}
export const localStore = guarded(() => window.localStorage)
export const sessionStore = guarded(() => window.sessionStorage)
