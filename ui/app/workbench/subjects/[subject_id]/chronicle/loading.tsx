export default function Loading() {
  return (
    <div className="space-y-8">
      <div className="animate-pulse space-y-2">
        <div className="h-4 w-32 rounded bg-gray-200" />
        <div className="h-8 w-64 rounded bg-gray-200" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 animate-pulse rounded border border-gray-200 bg-gray-100" />
        ))}
      </div>
    </div>
  );
}
