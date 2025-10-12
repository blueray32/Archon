// NOTE: ChatKit package not available in npm registry
// Re-enable when package becomes available: import '@openai/chatkit-js';

export default function Assistant(): JSX.Element {
  const workflowId = import.meta.env.VITE_CHATKIT_WORKFLOW_ID?.trim() ?? '';

  if (!workflowId) {
    return (
      <div className="px-6 py-12 text-center text-sm text-zinc-500 dark:text-zinc-400">
        ChatKit not configured.
      </div>
    );
  }

  return (
    <div className="px-6 py-6">
      <openai-chatkit
        session-endpoint="/api/chatkit/session"
        workflow-id={workflowId}
        theme="auto"
        uploads="disabled"
      />
    </div>
  );
}
