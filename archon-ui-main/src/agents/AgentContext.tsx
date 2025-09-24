import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { AGENTS, type Agent } from "./registry";

type AgentState = {
  agents: Agent[];
  selectedAgentId: string;
  setSelectedAgentId: (id: string) => void;
  selectedAgent: Agent;
};

const AgentCtx = createContext<AgentState | null>(null);

const DEFAULT_ID = AGENTS[0]?.id ?? "profesora-maria";
const KEY = "archon.selectedAgentId";

export const AgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(() => {
    try {
      return localStorage.getItem(KEY) ?? DEFAULT_ID;
    } catch {
      return DEFAULT_ID;
    }
  });


  useEffect(() => {
    try {
      localStorage.setItem(KEY, selectedAgentId);
    } catch {}
  }, [selectedAgentId]);


  const selectedAgent = useMemo(
    () => AGENTS.find(a => a.id === selectedAgentId) ?? AGENTS[0] ?? { id: DEFAULT_ID, label: "Default" },
    [selectedAgentId]
  );

  const value = useMemo<AgentState>(
    () => ({
      agents: AGENTS,
      selectedAgentId,
      setSelectedAgentId,
      selectedAgent,
    }),
    [selectedAgentId, selectedAgent]
  );

  return <AgentCtx.Provider value={value}>{children}</AgentCtx.Provider>;
};

export const useAgentState = (): AgentState => {
  const ctx = useContext(AgentCtx);
  if (!ctx) throw new Error("useAgentState must be used within AgentProvider");
  return ctx;
};
