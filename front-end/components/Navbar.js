import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="bg-dark text-background p-4 flex justify-between items-center">
      <h1 className="text-xl font-semibold">####</h1>
      <Link href="/theme-preview" className="text-background hover:underline">
        <button className="bg-primary hover:bg-accent text-dark px-4 py-2 rounded-lg">
          Button
        </button>
      </Link>
    </nav>
  );
}