import { useQuery } from "@tanstack/react-query";
import { projectService } from "../../services";
import type { ProjectDocument } from "../types";

// Query keys
const documentKeys = {
  all: (projectId: string) => ["projects", projectId, "documents"] as const,
};

/**
 * Get documents from project's docs JSONB field
 * Read-only - no mutations
 */
export function useProjectDocuments(projectId: string | undefined) {
  return useQuery({
    queryKey: projectId ? documentKeys.all(projectId) : ["documents-undefined"],
    queryFn: async () => {
      if (!projectId) return [];
      const project = await projectService.getProject(projectId);
      const raw = (project.docs || []) as unknown[];
      // Filter invalid documents to avoid UI crashes; log details for debugging
      const valid: ProjectDocument[] = [];
      const dropped: { index: number; reason: string }[] = [];
      raw.forEach((doc, idx) => {
        if (doc === null || doc === undefined || typeof doc !== "object") {
          dropped.push({ index: idx, reason: "non-object document" });
          return;
        }
        const maybeId = (doc as Record<string, unknown>).id;
        if (typeof maybeId !== "string" || maybeId.length === 0) {
          dropped.push({ index: idx, reason: "missing or non-string id" });
          return;
        }
        valid.push(doc as ProjectDocument);
      });
      if (dropped.length > 0) {
        // Detailed logging to aid debugging in beta without crashing the UI
        console.error(`Dropped ${dropped.length} invalid document(s) from project ${projectId}`, {
          dropped,
          total: raw.length,
        });
      }
      return valid;
    },
    enabled: !!projectId,
  });
}
