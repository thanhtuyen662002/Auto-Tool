export default function ResultsSkeleton() {
  return (
    <div className="grid gap-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {[0, 1, 2, 3, 4].map((item) => (
          <div className="glass-card h-28 animate-pulse bg-white/5" key={item} />
        ))}
      </div>
      <div className="glass-card h-20 animate-pulse bg-white/5" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2, 3, 4, 5].map((item) => (
          <div className="glass-card h-80 animate-pulse bg-white/5" key={item} />
        ))}
      </div>
    </div>
  );
}
