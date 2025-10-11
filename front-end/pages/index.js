export default function Home() {
  return (
    <section className="flex flex-col items-center justify-center h-[80vh] text-center">
      <div className="min-h-screen flex flex-col justify-center items-center bg-background">
        <h1 className="text-4xl text-dark font-bold">Welcome!</h1>
        <p className="text-accent mt-4">This is your AI assistant interface.</p>
      </div>
    </section>
  );
}
