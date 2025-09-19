export type Agent = {
  id: string;
  label: string;
  description?: string;
  command?: string; // optional: backend route/command
  model?: string; // optional: model hint
};

export const AGENTS: Agent[] = [
  { id: "profesora-maria", label: "Profesora María", description: "Spanish tutor agent" },
  { id: "pydantic-ai", label: "Pydantic AI", description: "Expert on Pydantic AI & Pydantic docs (llmstxt)" },
  { id: "researcher", label: "Researcher", description: "R&D context gatherer" },
];

// Map UI agent ids to backend agent_type identifiers
const AGENT_TYPE_MAP: Record<string, string> = {
  'profesora-maria': 'spanish_tutor',
  'pydantic-ai': 'pydantic_ai',
  'reviewer': 'rag',
  'researcher': 'rag',
};

export function getAgentTypeFor(agentId: string | undefined | null): string {
  if (!agentId) return AGENT_TYPE_MAP['profesora-maria'];
  return AGENT_TYPE_MAP[agentId] ?? AGENT_TYPE_MAP['profesora-maria'];
}
