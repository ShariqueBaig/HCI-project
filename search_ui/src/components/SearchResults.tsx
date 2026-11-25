/** Loading placeholder shown while retrieval + Stage A + Stage B run. */
export function ResultsSkeleton() {
  const bar = (w: string) => (
    <div className="h-3 animate-pulse rounded" style={{ width: w, background: 'var(--aura-faint)' }} />
  );
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Searching">
      <div className="flex flex-col gap-2 rounded-xl border p-5" style={{ borderColor: 'var(--aura-border)', background: 'var(--aura-surface)' }}>
        {bar('92%')}
        {bar('70%')}
      </div>
      <div className="flex flex-col gap-3">
        {bar('85%')}
        {bar('78%')}
        {bar('60%')}
      </div>
    </div>
  );
}
