import { ref } from 'vue'

/**
 * Lightweight dark-theme controller for Element Plus.
 *
 * Element Plus dark mode is toggled by adding the `dark` class on the root
 * <html> element (its dark css-vars are imported once in `main.ts`).
 * The user's choice is persisted in localStorage; on first load we fall back
 * to the OS `prefers-color-scheme` setting.
 *
 * Usage:
 *   import { initTheme, useTheme } from '@/utils/theme'
 *   initTheme()                       // call once at boot (main.ts)
 *   const { isDark, toggleTheme } = useTheme()  // in a component
 */

const STORAGE_KEY = 'erp-theme'

// Module-level singleton so every consumer shares the same reactive state.
const isDark = ref(false)

function applyTheme(dark: boolean): void {
  const root = document.documentElement
  if (dark) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
  isDark.value = dark
}

/** Apply the persisted (or OS-preferred) theme. Safe to call multiple times. */
export function initTheme(): void {
  let dark = false
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'dark' || saved === 'light') {
      dark = saved === 'dark'
    } else if (typeof window !== 'undefined' && window.matchMedia) {
      dark = window.matchMedia('(prefers-color-scheme: dark)').matches
    }
  } catch {
    // localStorage / matchMedia unavailable -> default to light, never crash.
    dark = false
  }
  applyTheme(dark)
}

/** Explicitly set the theme and persist the choice. */
export function setDark(dark: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, dark ? 'dark' : 'light')
  } catch {
    // ignore persistence failures (private mode, quota, ...)
  }
  applyTheme(dark)
}

/** Flip between light and dark. */
export function toggleTheme(): void {
  setDark(!isDark.value)
}

export function useTheme() {
  return { isDark, initTheme, setDark, toggleTheme }
}

export default useTheme
