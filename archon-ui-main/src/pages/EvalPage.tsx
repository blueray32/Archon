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
  const [results, setResults] = useState<Record<string, RAGEvalResponse>>({});

  // Load persisted
  useEffect(() => {
    try {
      const savedQ = localStorage.getItem('rag_eval_queries');
      const savedK = localStorage.getItem('rag_eval_k');
      if (savedQ) setQueriesText(savedQ);
      if (savedK) setK(Number(savedK) || 10);
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

  const onRun = async () => {
    if (queries.length === 0) {
      showToast('Add at least one query', 'warning');
      return;
    }
    setRunning(true);
    const out: Record<string, RAGEvalResponse> = {};
    try {
      for (const q of queries) {
        try {
          const data = await callRAG(q, k);
          out[q] = data;
        } catch (e: any) {
          out[q] = { query: q, results: [], match_count: k } as RAGEvalResponse;
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
            </div>
          </div>
        </div>

        {Object.keys(results).length > 0 && (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
            <h2 className="text-lg font-medium mb-3">Results</h2>
            <div className="space-y-6">
              {queries.map((q) => {
                const r = results[q];
                const items = (r?.results || []) as RAGEvalResult[];
                return (
                  <div key={q}>
                    <div className="text-sm font-medium mb-2">Query: <span className="text-zinc-600 dark:text-zinc-300">{q}</span></div>
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

