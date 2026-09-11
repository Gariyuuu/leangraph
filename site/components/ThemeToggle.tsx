"use client";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  if (dark === null) return <span className="h-8 w-8" aria-hidden />;
  const flip = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("theme", next ? "dark" : "light"); } catch {}
    setDark(next);
  };
  return (
    <button onClick={flip} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="rounded border border-line px-2 py-1 text-xs text-ink-2 transition-colors hover:bg-paper-3">
      {dark ? "Light" : "Dark"}
    </button>
  );
}
