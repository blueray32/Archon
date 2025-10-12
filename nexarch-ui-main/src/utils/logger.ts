/* eslint-disable no-console */
// Lightweight logger wrapper for beta: routes logs through console
// Use this to avoid eslint no-console noise across the app.

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const envLevel = (import.meta?.env?.VITE_LOG_LEVEL as LogLevel | undefined) || 'info';
const levelRank: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };

function enabled(level: LogLevel): boolean {
  return levelRank[level] >= levelRank[envLevel];
}

export const logger = {
  debug: (...args: unknown[]) => { if (enabled('debug')) console.debug(...args); },
  info: (...args: unknown[]) => { if (enabled('info')) console.info(...args); },
  warn: (...args: unknown[]) => { if (enabled('warn')) console.warn(...args); },
  error: (...args: unknown[]) => { if (enabled('error')) console.error(...args); },
};

