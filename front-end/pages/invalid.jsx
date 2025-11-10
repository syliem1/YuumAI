export default function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[url('/images/classroom-background.png')] bg-cover bg-center">
      <div className="text-center">
        
        {/* Loading text */}
        <div class="bg-white p-8">
            <h2 className="text-2xl font-semibold text-slate-800 mb-2">The Player You Entered is Invalid </h2>
        </div>      
        
      </div>
    </div>
  );
}