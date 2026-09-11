"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

const NAV: [string, string][] = [
  ["/", "Overview"], ["/benchmark", "Leaderboard"], ["/theorems", "Theorems"], ["/retrieval", "Retrieval"],
  ["/repair", "Repair loop"], ["/errors", "Failure taxonomy"], ["/cost", "Cost"], ["/methods", "Methods"], ["/paper", "Paper"],
];

export function SideNav() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href.replace(/s$/, "")));
  return (
    <aside className="border-b border-line bg-paper-2 lg:sticky lg:top-0 lg:h-dvh lg:w-56 lg:shrink-0 lg:border-b-0 lg:border-r">
      <div className="flex items-center justify-between px-5 py-4 lg:block">
        <Link href="/" className="block">
          <span className="font-mono text-sm font-semibold tracking-tight">LeanGraph</span>
          <span className="mt-0.5 hidden text-xs text-ink-3 lg:block">verifier-graded LLM theorem proving</span>
        </Link>
        <div className="lg:mt-4"><ThemeToggle /></div>
      </div>
      <nav aria-label="Sections" className="flex gap-1 overflow-x-auto px-3 pb-3 lg:block lg:space-y-0.5 lg:px-3">
        {NAV.map(([href, label]) => (
          <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
            className={`block whitespace-nowrap rounded px-2.5 py-1.5 text-sm transition-colors ${
              active(href) ? "bg-accent-wash font-medium text-ink" : "text-ink-2 hover:bg-paper-3 hover:text-ink"}`}>
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
