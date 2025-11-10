import Link from "next/link";

export default function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen text-center bg-[url('/images/classroom-background.png')] bg-cover bg-center">
        
        <h2 className="text-2xl bg-dark font-semibold text-white mb-2 p-3 rounded-2xl">An error has occured, please check the player name and tagline and try again</h2>  
        <Link href="/" className=" bg-dark/80 text-white border-white cursor-pointer  rounded-2xl p-3 text-xl mt-2"> Back to Home </Link>
    </div>
  );
}