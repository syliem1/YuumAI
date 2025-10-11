import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="bg-dark text-background p-4 flex justify-between items-center">
      <h1 className="text-xl font-semibold">My App</h1>
      <button className="bg-primary hover:bg-accent text-dark px-4 py-2 rounded-lg">
        Chat
      </button>
    </nav>
  );
}