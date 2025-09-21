import { useEffect, useMemo, useState } from 'react';
import { BarChart2, Play } from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { useToast } from '../features/ui/hooks/useToast';

type RAGEvalResult = {
  id?: string | number;
  content?: string;
  similarity?: number;
  similarity_score?: number;
  score?: number;
  metadata?: Record<string, any> | null;
};

type RAGEvalResponse = {
  results?: RAGEvalResult[];
  query: string;
  match_count?: number;
};

async function callRAG(query: string, k: number): Promise<RAGEvalResponse> {
  const res = await fetch('/api/rag/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, match_count: k }),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      msg = data?.error || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export function EvalPage() {
  const { showToast } = useToast();
  const [queriesText, setQueriesText] = useState('test\nembedding model\npydantic test model');
  const [k, setK] = useState<number>(10);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<Record<string, { resp: RAGEvalResponse; durationMs: number; avgSim?: number; topSources?: Record<string, number> }>>({});
  const [presets, setPresets] = useState<Record<string, string>>({});
  const [presetName, setPresetName] = useState('');
  const [lastResults, setLastResults] = useState<Record<string, { resp: RAGEvalResponse; durationMs: number; avgSim?: number; topSources?: Record<string, number> }>>({});
  const [compareToLast, setCompareToLast] = useState(false);

  // Load persisted
  useEffect(() => {
    try {
      const savedQ = localStorage.getItem('rag_eval_queries');
      const savedK = localStorage.getItem('rag_eval_k');
      if (savedQ) setQueriesText(savedQ);
      if (savedK) setK(Number(savedK) || 10);
      const savedPresets = localStorage.getItem('rag_eval_presets');
      if (savedPresets) setPresets(JSON.parse(savedPresets));
      const savedLast = localStorage.getItem('rag_eval_last_results');
      if (savedLast) setLastResults(JSON.parse(savedLast));
    } catch {}
  }, []);

  // Persist
  useEffect(() => {
    try { localStorage.setItem('rag_eval_queries', queriesText); } catch {}
  }, [queriesText]);
  useEffect(() => {
    try { localStorage.setItem('rag_eval_k', String(k)); } catch {}
  }, [k]);

  const queries = useMemo(() => queriesText.split('\n').map(q => q.trim()).filter(Boolean), [queriesText]);

  const summary = useMemo(() => {
    const keys = Object.keys(results);
    if (keys.length === 0) return null;
    const sims = keys
      .map((k) => results[k]?.avgSim)
      .filter((v): v is number => typeof v === 'number');
    const min = sims.length ? Math.min(...sims) : undefined;
    const max = sims.length ? Math.max(...sims) : undefined;
    const avg = sims.length ? sims.reduce((a, b) => a + b, 0) / sims.length : undefined;
    const totalMs = keys.reduce((acc, k) => acc + (results[k]?.durationMs || 0), 0);
    return { count: keys.length, min, max, avg, totalMs };
  }, [results]);

  const onRun = async () => {
    if (queries.length === 0) {
      showToast('Add at least one query', 'warning');
      return;
    }
    setRunning(true);
    const out: Record<string, { resp: RAGEvalResponse; durationMs: number; avgSim?: number; topSources?: Record<string, number> }> = {};
    try {
      if (Object.keys(results).length > 0) {
        setLastResults(results);
        try { localStorage.setItem('rag_eval_last_results', JSON.stringify(results)); } catch {}
      }
      for (const q of queries) {
        try {
          const t0 = performance.now();
          const data = await callRAG(q, k);
          const t1 = performance.now();
          const items = (data?.results || []) as RAGEvalResult[];
          const sims = items
            .map(it => (typeof it.similarity === 'number' ? it.similarity : (typeof it.similarity_score === 'number' ? it.similarity_score : (typeof it.score === 'number' ? it.score : undefined))))
            .filter((v): v is number => typeof v === 'number');
          const avgSim = sims.length ? sims.reduce((a, b) => a + b, 0) / sims.length : undefined;
          const topSources: Record<string, number> = {};
          items.forEach(it => {
            const src = (it?.metadata?.source_id as string) || '';
            if (src) topSources[src] = (topSources[src] || 0) + 1;
          });
          out[q] = { resp: data, durationMs: t1 - t0, avgSim, topSources };
        } catch (e: any) {
          out[q] = { resp: { query: q, results: [], match_count: k }, durationMs: 0 };
          showToast(`RAG failed for "${q}": ${e?.message || e}`, 'error');
        }
      }
      setResults(out);
      showToast('Evaluation complete', 'success');
    } finally {
      setRunning(false);
    }
  };

  return (
    <MainLayout>
      <div className="max-w-6xl mx-auto w-full px-4 py-6">
        <div className="flex items-center gap-3 mb-6">
          <BarChart2 className="h-6 w-6 text-blue-500" />
          <h1 className="text-xl font-semibold">RAG Evaluation</h1>
        </div>

        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur mb-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Queries (one per line)</label>
              <textarea
                className="w-full h-32 rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                value={queriesText}
                onChange={(e) => setQueriesText(e.target.value)}
              />
              <div className="mt-1 text-[10px] text-zinc-500">Stored in localStorage for convenience.</div>
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Top K</label>
              <input
                type="number"
                min={1}
                max={50}
                className="w-28 rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                value={k}
                onChange={(e) => setK(Number(e.target.value) || 10)}
              />
              <div className="mt-4">
                <button
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50"
                  onClick={onRun}
                  disabled={running}
                  title="Execute evaluation for all queries"
                >
                  <Play className="w-4 h-4" />
                  {running ? 'Running…' : 'Run'}
                </button>
              </div>
              <div className="mt-6 flex items-center gap-2 flex-wrap">
                <input
                  className="w-48 rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                  placeholder="Preset name"
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  title="Save current queries as a preset"
                />
                <button
                  className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30"
                  onClick={() => {
                    if (!presetName.trim()) { showToast('Enter a preset name', 'warning'); return; }
                    const next = { ...presets, [presetName.trim()]: queriesText };
                    setPresets(next);
                    try { localStorage.setItem('rag_eval_presets', JSON.stringify(next)); } catch {}
                    showToast('Preset saved', 'success');
                  }}
                >Save</button>
                {Object.keys(presets).length > 0 && (
                  <select
                    className="rounded-lg bg-white/70 dark:bg-zinc-950/40 border border-zinc-200 dark:border-zinc-800 px-3 py-2"
                    onChange={(e) => {
                      const key = e.target.value;
                      if (key && presets[key]) setQueriesText(presets[key]);
                    }}
                    defaultValue=""
                    title="Load preset"
                  >
                    <option value="" disabled>Load preset…</option>
                    {Object.keys(presets).map(name => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                )}
                {Object.keys(presets).length > 0 && (
                  <button
                    className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30"
                    onClick={() => {
                      if (!presetName.trim() || !presets[presetName.trim()]) { showToast('Select a saved preset name to delete', 'warning'); return; }
                      const next = { ...presets };
                      delete next[presetName.trim()];
                      setPresets(next);
                      try { localStorage.setItem('rag_eval_presets', JSON.stringify(next)); } catch {}
                      showToast('Preset deleted', 'success');
                    }}
                  >Delete</button>
                )}
                {Object.keys(results).length > 0 && (
                  <button
                    className="ml-2 px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30"
                    onClick={() => {
                      try {
                        const payload = JSON.stringify(results, null, 2);
                        navigator.clipboard.writeText(payload);
                        showToast('Results copied to clipboard', 'success');
                      } catch (e: any) {
                        showToast(e?.message || 'Failed to copy', 'error');
                      }
                    }}
                    title="Copy JSON of results to clipboard"
                  >Copy JSON</button>
                )}
                <label className="ml-2 inline-flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300">
                  <input type="checkbox" checked={compareToLast} onChange={(e) => setCompareToLast(e.target.checked)} />
                  Compare to last run
                </label>
                {Object.keys(lastResults).length > 0 && (
                  <>
                    <button
                      className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30"
                      onClick={() => {
                        setLastResults(results);
                        try { localStorage.setItem('rag_eval_last_results', JSON.stringify(results)); } catch {}
                        showToast('Baseline updated to current results', 'success');
                      }}
                    >Set Baseline</button>
                    <button
                      className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30"
                      onClick={() => {
                        setLastResults({});
                        try { localStorage.removeItem('rag_eval_last_results'); } catch {}
                        showToast('Baseline cleared', 'success');
                      }}
                    >Clear Baseline</button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {summary && (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur mb-4">
            <h2 className="text-lg font-medium mb-2">Summary</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              <div>
                <div className="text-zinc-500 text-xs">Queries</div>
                <div className="font-medium">{summary.count}</div>
              </div>
              <div>
                <div className="text-zinc-500 text-xs">Avg sim</div>
                <div className="font-medium">{summary.avg !== undefined ? summary.avg.toFixed(3) : '—'}</div>
              </div>
              <div>
                <div className="text-zinc-500 text-xs">Min sim</div>
                <div className="font-medium">{summary.min !== undefined ? summary.min.toFixed(3) : '—'}</div>
              </div>
              <div>
                <div className="text-zinc-500 text-xs">Max sim</div>
                <div className="font-medium">{summary.max !== undefined ? summary.max.toFixed(3) : '—'}</div>
              </div>
              <div>
                <div className="text-zinc-500 text-xs">Total time</div>
                <div className="font-medium">{Math.round(summary.totalMs)} ms</div>
              </div>
            </div>
          </div>
        )}

        {Object.keys(results).length > 0 && (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
            <h2 className="text-lg font-medium mb-3">Results</h2>
            <div className="space-y-6">
              {queries.map((q) => {
                const entry = results[q];
                const prev = lastResults[q];
                const items = (entry?.resp?.results || []) as RAGEvalResult[];
                return (
                  <div key={q}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm font-medium">Query: <span className="text-zinc-600 dark:text-zinc-300">{q}</span></div>
                      <div className="text-xs text-zinc-500">
                        {entry?.avgSim !== undefined && <span className="mr-3">avg sim: {entry.avgSim.toFixed(3)}</span>}
                        {entry?.durationMs !== undefined && <span>time: {Math.round(entry.durationMs)} ms</span>}
                        {compareToLast && prev?.avgSim !== undefined && entry?.avgSim !== undefined && (
                          <span className={`ml-3 ${entry.avgSim - (prev.avgSim||0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            Δ { (entry.avgSim - (prev.avgSim||0)).toFixed(3) }
                          </span>
                        )}
                      </div>
                    </div>
                    {items.length === 0 ? (
                      <div className="text-sm text-zinc-500">No results.</div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {items.map((it, idx) => {
                          const sim = (typeof it.similarity === 'number') ? it.similarity : (typeof it.similarity_score === 'number') ? it.similarity_score : (typeof it.score === 'number') ? it.score : undefined;
                          const snippet = (it.content || '').slice(0, 160);
                          const src = it?.metadata?.source_id || (it as any)?.source || '';
                          return (
                            <div key={idx} className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3 bg-white/70 dark:bg-zinc-950/40">
                              <div className="text-xs text-zinc-500 mb-1">#{idx + 1} {src && <span>• {src}</span>}</div>
                              {sim !== undefined && (
                                <div className="text-xs text-emerald-600 dark:text-emerald-400 mb-1">sim: {sim.toFixed(3)}</div>
                              )}
                              <div className="text-sm whitespace-pre-wrap">{snippet}{snippet.length === 160 ? '…' : ''}</div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {compareToLast && prev?.topSources && entry?.topSources && (
                      <div className="mt-2 text-xs text-zinc-500">
                        Sources Δ:{' '}
                        {Object.keys({ ...(entry.topSources || {}), ...(prev.topSources || {}) })
                          .map((s) => s)
                          .sort()
                          .slice(0, 8)
                          .map((s, i) => {
                            const cur = (entry.topSources || {})[s] || 0;
                            const old = (prev.topSources || {})[s] || 0;
                            const diff = cur - old;
                            if (!diff) return null;
                            return (
                              <span key={s} className={diff > 0 ? 'text-emerald-600' : 'text-red-600'}>
                                {i > 0 ? ' • ' : ''}{s}:{diff > 0 ? `+${diff}` : diff}
                              </span>
                            );
                          })
                        }
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </MainLayout>
  );
}

export default EvalPage;
