import { useState } from 'react';
import { McpViewWithBoundary } from '../features/mcp';

export const MCPPage = () => {
  const [initResult, setInitResult] = useState<string>('');
  const [infoResult, setInfoResult] = useState<string>('');

  const initSession = async () => {
    try {
      const res = await fetch('/api/mcp/session/init', { method: 'POST' });
      const txt = await res.text();
      setInitResult(txt);
    } catch (e: any) {
      setInitResult(e?.message || 'Failed to init session');
    }
  };

  const getInfo = async () => {
    try {
      const res = await fetch('/api/mcp/session/info');
      const txt = await res.text();
      setInfoResult(txt);
    } catch (e: any) {
      setInfoResult(e?.message || 'Failed to get session info');
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Quick MCP Session Tools */}
      <div className="mx-4 mt-4 rounded-xl border border-zinc-200 dark:border-zinc-800/50 p-4 bg-white/60 dark:bg-zinc-900/40 backdrop-blur">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">MCP Session Helpers</h2>
          <div className="flex items-center gap-2">
            <button className="px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500" onClick={initSession}>Init Session</nbutton>
            <button className="px-3 py-1.5 rounded-lg bg-zinc-800 text-white hover:bg-zinc-700" onClick={getInfo}>Session Info</button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div>
            <div className="text-zinc-500 mb-1">Init Response</div>
            <pre className="p-2 rounded bg-zinc-100 dark:bg-zinc-900 overflow-auto max-h-48 whitespace-pre-wrap">{initResult || '—'}</pre>
          </div>
          <div>
            <div className="text-zinc-500 mb-1">Session Info</div>
            <pre className="p-2 rounded bg-zinc-100 dark:bg-zinc-900 overflow-auto max-h-48 whitespace-pre-wrap">{infoResult || '—'}</pre>
          </div>
        </div>
      </div>

      {/* Existing MCP view */}
      <McpViewWithBoundary />
    </div>
  );
};
