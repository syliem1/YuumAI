import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="flex items-center justify-between bg-dark p-4 text-background">
      <h1 className="text-xl font-semibold">####</h1>
      <Link href="/theme-preview" className="text-background hover:underline">
        <button className="rounded-lg bg-primary px-4 py-2 text-dark hover:bg-accent">
          Button
        </button>
      </Link>
    </nav>
  );
}
