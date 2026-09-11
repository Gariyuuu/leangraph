export function Footer() {
  return (
    <footer className="border-t border-line px-5 py-6 text-xs text-ink-3 sm:px-10">
      <div className="mx-auto max-w-content">
        A proof is counted only when a fresh Lean process accepts it under the pinned toolchain, with no
        <code className="mx-1 font-mono">sorry</code>, no non-standard axioms and no banned premise. Every number on this site is
        read from the frozen result files; none is typed in by hand.
      </div>
    </footer>
  );
}
