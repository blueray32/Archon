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

// Fetch PRP personas from API
async function fetchPersonas(): Promise<Agent[]> {
  try {
    const response = await fetch('/api/agent-chat/personas');
    const data = await response.json();

    if (data.success && Array.isArray(data.personas)) {
      return data.personas.map((p: any) => ({
        id: p.name,
        label: p.display_name,
        description: p.description,
        model: 'prp', // All personas use PRP agent
      }));
    }
  } catch (error) {
    console.error('Failed to fetch personas:', error);
  }
  return [];
}

export const AgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [personas, setPersonas] = useState<Agent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>(() => {
    try {
      return localStorage.getItem(KEY) ?? DEFAULT_ID;
    } catch {
      return DEFAULT_ID;
    }
  });

  // Fetch personas on mount
  useEffect(() => {
    fetchPersonas().then(setPersonas);
  }, []);

  // Combine static agents with dynamic personas
  const allAgents = useMemo(() => {
    // Filter out the generic "prp" agent since we have specific personas now
    const staticAgents = AGENTS.filter(a => a.id !== 'prp');
    return [...personas, ...staticAgents];
  }, [personas]);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, selectedAgentId);
    } catch {
      // non-critical: ignore storage write failures (e.g., private mode)
      void 0;
    }
  }, [selectedAgentId]);


  const selectedAgent = useMemo(
    () => allAgents.find(a => a.id === selectedAgentId) ?? allAgents[0] ?? { id: DEFAULT_ID, label: "Default" },
    [selectedAgentId, allAgents]
  );

  const value = useMemo<AgentState>(
    () => ({
      agents: allAgents,
      selectedAgentId,
      setSelectedAgentId,
      selectedAgent,
    }),
    [allAgents, selectedAgentId, selectedAgent]
  );

  return <AgentCtx.Provider value={value}>{children}</AgentCtx.Provider>;
};

export const useAgentState = (): AgentState => {
  const ctx = useContext(AgentCtx);
  if (!ctx) throw new Error("useAgentState must be used within AgentProvider");
  return ctx;
};
