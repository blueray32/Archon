import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Database } from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { backfillEmbeddings, getEmbeddingsHealth, type EmbeddingsBackfillRequest } from '../services/api';
import { useToast } from '../features/ui/hooks/useToast';

export function EmbeddingsPage() {
  const { data, isLoading, refetch, isFetching, error } = useQuery({
    queryKey: ['embeddings-health'],
    queryFn: getEmbeddingsHealth,
    refetchOnWindowFocus: true,
  });

  const [form, setForm] = useState<EmbeddingsBackfillRequest>({
    tables: 'all',
    batch_size: 100,
    limit: 500,
    dry_run: true,
    source_id: '',
  });

  // Load saved preferences on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem('embeddings_backfill_prefs');
      if (raw) {
        const parsed = JSON.parse(raw);
        setForm((f) => ({ ...f, ...parsed }));
      }
    } catch {}
  }, []);

  // Persist preferences whenever form changes
  useEffect(() => {
    try {
      localStorage.setItem('embeddings_backfill_prefs', JSON.stringify(form));
    } catch {}
  }, [form]);

  const { showToast } = useToast();

  const mutation = useMutation({
    mutationFn: (body: EmbeddingsBackfillRequest) => backfillEmbeddings(body),
    onSuccess: async (res) => {
      await refetch();
      // Build a compact summary toast
      try {
        const parts: string[] = [];
        const sum = res?.summary || {} as Record<string, any>;
        Object.keys(sum).forEach((k) => {
          const s = sum[k];
          if (s && typeof s === 'object') {
            parts.push(`${k}: +${s.updated ?? 0} upd, ${s.failed_count ?? 0} err`);
          }
        });
        const msg = parts.length ? `Backfill ${form.dry_run ? 'dry-run' : 'completed'} (${res?.duration_seconds ?? 0}s) — ${parts.join(' | ')}` : 'Backfill completed';
        showToast(msg, 'success');
      } catch {
        showToast('Backfill completed', 'success');
      }
    },
    onError: (err: any) => {
      const msg = (err && err.message) ? err.message : 'Backfill failed';
      showToast(msg, 'error');
    }
  });

  const totalMissing = useMemo(() => data?.summary?.missing ?? 0, [data]);

  return (
    <MainLayout>
      <div className="max-w-5xl mx-auto w-full px-4 py-6">
        <div className="flex items-center gap-3 mb-6">
          <Database className="h-6 w-6 text-blue-500" />
          <h1 className="text-xl font-semibold">Embeddings Maintenance</h1>
        </div>

        {/* Health */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
            <div className="text-sm text-zinc-500">Crawled Pages</div>
            {isLoading ? (
              <div className="mt-2 text-zinc-400">Loading…</div>
            ) : error ? (
              <div className="mt-2 text-red-500">Failed to load</div>
            ) : (
              <div className="mt-2">
                <div className="text-2xl font-semibold">{data?.pages.total ?? 0}</div>
                <div className="text-xs text-zinc-500">Total</div>
                <div className="mt-1 text-yellow-600 dark:text-yellow-400">Missing: {data?.pages.missing ?? 0}</div>
              </div>
            )}
          </div>
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
            <div className="text-sm text-zinc-500">Code Examples</div>
            {isLoading ? (
              <div className="mt-2 text-zinc-400">Loading…</div>
            ) : error ? (
              <div className="mt-2 text-red-500">Failed to load</div>
            ) : (
              <div className="mt-2">
                <div className="text-2xl font-semibold">{data?.code_examples.total ?? 0}</div>
                <div className="text-xs text-zinc-500">Total</div>
                <div className="mt-1 text-yellow-600 dark:text-yellow-400">Missing: {data?.code_examples.missing ?? 0}</div>
              </div>
            )}
          </div>
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
            <div className="text-sm text-zinc-500">Summary</div>
            {isLoading ? (
              <div className="mt-2 text-zinc-400">Loading…</div>
            ) : error ? (
              <div className="mt-2 text-red-500">Failed to load</div>
            ) : (
              <div className="mt-2">
                <div className="text-2xl font-semibold">{data?.summary.total ?? 0}</div>
                <div className="text-xs text-zinc-500">Total rows</div>
                <div className="mt-1 text-emerald-600 dark:text-emerald-400">With Embedding: {data?.summary.with_embedding ?? 0}</div>
              </div>
            )}
          </div>
        </div>

        {/* Backfill Form */}
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Backfill Missing Embeddings</h2>
            <button
              className="text-sm px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              Refresh
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Tables</label>
              <select
                className="w-full rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                value={Array.isArray(form.tables) ? 'custom' : form.tables ?? 'all'}
                onChange={(e) => {
                  const v = e.target.value as 'all' | 'pages' | 'code_examples' | 'custom';
                  if (v === 'custom') {
                    setForm((f) => ({ ...f, tables: ['pages', 'code_examples'] }));
                  } else if (v === 'all') {
                    setForm((f) => ({ ...f, tables: 'all' }));
                  } else {
                    setForm((f) => ({ ...f, tables: [v] as Array<'pages'|'code_examples'> }));
                  }
                }}
              >
                <option value="all">All</option>
                <option value="pages">Pages only</option>
                <option value="code_examples">Code examples only</option>
                <option value="custom">Custom (both)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Source ID (optional)</label>
              <input
                className="w-full rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                placeholder="c0ffee..."
                value={form.source_id ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, source_id: e.target.value }))}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Batch Size</label>
              <input
                type="number"
                className="w-full rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                min={1}
                max={1000}
                value={form.batch_size ?? 100}
                onChange={(e) => setForm((f) => ({ ...f, batch_size: Number(e.target.value) }))}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Limit</label>
              <input
                type="number"
                className="w-full rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                min={1}
                max={10000}
                value={form.limit ?? 500}
                onChange={(e) => setForm((f) => ({ ...f, limit: Number(e.target.value) }))}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="dry-run"
                type="checkbox"
                className="h-4 w-4"
                checked={form.dry_run ?? true}
                onChange={(e) => setForm((f) => ({ ...f, dry_run: e.target.checked }))}
              />
              <label htmlFor="dry-run" className="text-sm">Dry run</label>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
              onClick={() => {
                if (!form.dry_run) {
                  const scope = Array.isArray(form.tables) ? form.tables.join(',') : (form.tables || 'all');
                  const ok = window.confirm(`Run live backfill for: ${scope}? This will write embeddings to the database.`);
                  if (!ok) return;
                }
                mutation.mutate(form);
              }}
              disabled={mutation.isPending || (totalMissing === 0 && !form.source_id)}
            >
              {mutation.isPending ? 'Running…' : form.dry_run ? 'Dry Run Backfill' : 'Run Backfill'}
            </button>
            {mutation.isSuccess && (
              <div className="text-sm text-emerald-600">Done in {mutation.data?.duration_seconds ?? 0}s</div>
            )}
            {mutation.isError && (
              <div className="text-sm text-red-500">Backfill failed</div>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

export default EmbeddingsPage;
