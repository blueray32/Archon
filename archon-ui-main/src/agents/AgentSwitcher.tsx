import React from "react";
import { useAgentState } from "./AgentContext";

export const AgentSwitcher: React.FC<{ className?: string; label?: string }> = ({ className, label = "Agent" }) => {
  const { agents, selectedAgentId, setSelectedAgentId } = useAgentState();
  const disabled = agents.length === 0;

  return (
    <div className={className ?? "flex items-center gap-2"}>
      <span className="text-sm text-gray-500">{label}</span>
      <select
        className="border rounded-md px-2 py-1 text-sm bg-white dark:bg-zinc-900 text-gray-900 dark:text-gray-100"
        disabled={disabled}
        aria-label="Select active agent"
        value={selectedAgentId}
        onChange={(e) => setSelectedAgentId(e.target.value)}
      >
        {disabled ? (
          <option>No agents</option>
        ) : (
          agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.label}
            </option>
          ))
        )}
      </select>
    </div>
  );
};

