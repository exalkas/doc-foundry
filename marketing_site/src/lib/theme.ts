/**
 * Theme utilities for dark mode toggle
 */

export type Theme = "light" | "dark";

const THEME_STORAGE_KEY = "theme";

/**
 * Get current theme from localStorage or system preference
 */
export function getTheme(): Theme {
  if (typeof window === "undefined") {
    return "light";
  }

  const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
  if (stored === "light" || stored === "dark") {
    return stored;
  }

  // Check system preference
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }

  return "light";
}

/**
 * Set theme and update DOM
 */
export function setTheme(theme: Theme): void {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.setItem(THEME_STORAGE_KEY, theme);
  const html = document.documentElement;

  if (theme === "dark") {
    html.classList.add("dark");
  } else {
    html.classList.remove("dark");
  }
}

/**
 * Toggle between light and dark theme
 */
export function toggleTheme(): Theme {
  const current = getTheme();
  const newTheme: Theme = current === "dark" ? "light" : "dark";
  setTheme(newTheme);
  return newTheme;
}

/**
 * Initialize theme on page load
 */
export function initTheme(): void {
  if (typeof window === "undefined") {
    return;
  }

  const theme = getTheme();
  setTheme(theme);
}
