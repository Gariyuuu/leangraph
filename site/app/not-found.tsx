import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-20">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="mt-2 text-ink-2">
        No page or theorem with that address. <Link className="text-accent underline" href="/theorems">Browse the theorems</Link>.
      </p>
    </div>
  );
}
