import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { AGENTS, type Agent } from "./registry";

type AgentState = {
  agents: Agent[];
  selectedAgentId: string;
  setSelectedAgentId: (id: string) => void;
  selectedAgent: Agent;
  selectedSourceFilter: string;
  setSelectedSourceFilter: (s: string) => void;
  kbOnly: boolean;
  setKbOnly: (v: boolean) => void;
};

const AgentCtx = createContext<AgentState | null>(null);

const DEFAULT_ID = AGENTS[0]?.id ?? "profesora-maria";
const KEY = "archon.selectedAgentId";
const SOURCE_KEY = "archon.sourceFilter";
const KB_ONLY_KEY = "archon.kbOnly";

export const AgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(() => {
    try {
      return localStorage.getItem(KEY) ?? DEFAULT_ID;
    } catch {
      return DEFAULT_ID;
    }
  });

  const [selectedSourceFilter, setSelectedSourceFilter] = useState<string>(() => {
    try {
      return localStorage.getItem(SOURCE_KEY) ?? "";
    } catch {
      return "";
    }
  });

  const [kbOnly, setKbOnly] = useState<boolean>(() => {
    try {
      return localStorage.getItem(KB_ONLY_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(KEY, selectedAgentId);
    } catch {}
  }, [selectedAgentId]);

  useEffect(() => {
    try {
      localStorage.setItem(SOURCE_KEY, selectedSourceFilter);
    } catch {}
  }, [selectedSourceFilter]);

  useEffect(() => {
    try {
      localStorage.setItem(KB_ONLY_KEY, String(kbOnly));
    } catch {}
  }, [kbOnly]);

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
      selectedSourceFilter,
      setSelectedSourceFilter,
      kbOnly,
      setKbOnly,
    }),
    [selectedAgentId, selectedAgent, selectedSourceFilter, kbOnly]
  );

  return <AgentCtx.Provider value={value}>{children}</AgentCtx.Provider>;
};

export const useAgentState = (): AgentState => {
  const ctx = useContext(AgentCtx);
  if (!ctx) throw new Error("useAgentState must be used within AgentProvider");
  return ctx;
};
