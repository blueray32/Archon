import './index.css';
import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { AgentProvider } from './agents/AgentContext';

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(
    <AgentProvider>
      <App />
    </AgentProvider>
  );
}
