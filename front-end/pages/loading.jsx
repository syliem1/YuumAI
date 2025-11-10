export default function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[url('/images/classroom-background.png')] bg-cover bg-center">
      <div className="text-center">
        {/* Spinner */}
        <div className="relative w-24 h-24 mx-auto mb-8">
          <div className="absolute inset-0 border-4 border-sky-200 border-t-sky-400 rounded-full animate-spin"></div>
        </div>
        
        {/* Loading text */}
        <h2 className="text-2xl font-semibold text-white mb-2">Loading</h2>
        <p className="text-amber-100">Please wait...</p>
        
        
        {/* <div className="flex justify-center gap-2 mt-4">
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
          <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></div>
        </div> */}
      </div>
    </div>
  );
}