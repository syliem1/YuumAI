import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="bg-white shadow-md py-4 px-8 flex justify-between items-center">
      <h1 className="text-2xl font-semibold text-blue-600">MyApp</h1>
      <div className="space-x-6">
        <Link href="/" className="hover:text-blue-600">Home</Link>
        <Link href="/chat" className="hover:text-blue-600">Chatbot</Link>
      </div>
    </nav>
  );
}
