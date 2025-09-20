import React from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Filter } from 'lucide-react';
import { useAgentState } from '../../agents/AgentContext';

export const SourceFilterControl: React.FC<{ className?: string }> = ({ className }) => {
  const { selectedSourceFilter, setSelectedSourceFilter } = useAgentState();
  const [value, setValue] = React.useState<string>(selectedSourceFilter);
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [suggestions, setSuggestions] = React.useState<string[]>([]);

  React.useEffect(() => {
    setValue(selectedSourceFilter);
  }, [selectedSourceFilter]);

  // Fetch KB items and derive suggestion tokens (tags, source_ids, normalized titles)
  const fetchSuggestions = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/knowledge-items?per_page=100');
      if (!res.ok) throw new Error('failed');
      const data = await res.json();
      const items: any[] = data?.items || [];
      const set = new Set<string>();
      for (const it of items) {
        const sid = (it?.source_id || '').toString().trim();
        if (sid) set.add(sid);
        const title = (it?.title || '').toString().trim().toLowerCase();
        if (title) {
          // normalize simple tokens from title
          const t = title.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
          if (t) set.add(t);
        }
        const tags: string[] = Array.isArray(it?.metadata?.tags) ? it.metadata.tags : [];
        for (const tag of tags) {
          const tt = (tag || '').toString().trim();
          if (tt) set.add(tt);
        }
      }
      // Prefer common tokens up to 20
      const list = Array.from(set);
      // Sort to surface currently selected tokens first
      list.sort((a, b) => {
        const av = selectedSourceFilter?.includes(a) ? -1 : 0;
        const bv = selectedSourceFilter?.includes(b) ? -1 : 0;
        return av - bv || a.localeCompare(b);
      });
      setSuggestions(list.slice(0, 20));
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, [selectedSourceFilter]);

  React.useEffect(() => {
    if (open) fetchSuggestions();
  }, [open, fetchSuggestions]);

  const toggleToken = (token: string) => {
    const tokens = value ? value.split('|').filter(Boolean) : [];
    const has = tokens.includes(token);
    const next = has ? tokens.filter((t) => t !== token) : [...tokens, token];
    setValue(next.join('|'));
  };

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          className={
            className ??
            'px-2 py-1 rounded-md border text-xs flex items-center gap-1 bg-white/70 dark:bg-zinc-900/60 border-gray-200 dark:border-gray-700'
          }
          title={selectedSourceFilter ? `Sources: ${selectedSourceFilter}` : 'Set source filter'}
        >
          <Filter className="w-3.5 h-3.5" />
          <span>Sources</span>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={8}
          className="z-50 w-96 rounded-lg border border-gray-200 dark:border-gray-700 bg-white/95 dark:bg-zinc-900/95 shadow-xl p-3 backdrop-blur"
        >
          <div className="space-y-3 text-sm">
            <div>
              <div className="text-xs text-gray-600 dark:text-gray-300 mb-1">Regex or tokens separated by |</div>
              <input
                className="w-full text-sm px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-zinc-800 text-gray-800 dark:text-gray-100"
                placeholder="e.g. ai-agent-mastery|pydantic|docs"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>

            <div>
              <div className="text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">Suggestions</div>
              {loading ? (
                <div className="text-xs text-gray-500">Loading…</div>
              ) : suggestions.length === 0 ? (
                <div className="text-xs text-gray-500">No suggestions</div>
              ) : (
                <div className="grid grid-cols-2 gap-2 max-h-44 overflow-auto pr-1">
                  {suggestions.map((s) => {
                    const active = (value || '').split('|').filter(Boolean).includes(s);
                    return (
                      <label key={s} className={`flex items-center gap-2 text-xs ${active ? 'text-blue-700 dark:text-blue-400' : ''}`}>
                        <input
                          type="checkbox"
                          checked={active}
                          onChange={() => toggleToken(s)}
                          className="accent-blue-600"
                        />
                        <span className="truncate" title={s}>{s}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                className="text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-zinc-800"
                onClick={() => {
                  setValue('');
                  setSelectedSourceFilter('');
                }}
              >
                Clear
              </button>
              <button
                className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
                onClick={() => {
                  setSelectedSourceFilter(value.trim());
                  setOpen(false);
                }}
              >
                Apply
              </button>
            </div>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
};
