export type Agent = {
  id: string;
  label: string;
  description?: string;
  command?: string; // optional: backend route/command
  model?: string; // optional: model hint
};

export const AGENTS: Agent[] = [
  { id: "profesora-maria", label: "Profesora María", description: "Spanish tutor agent" },
  { id: "reviewer", label: "Reviewer", description: "Code & doc reviewer" },
  { id: "researcher", label: "Researcher", description: "R&D context gatherer" },
];

