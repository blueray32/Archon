import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePolling } from "../../ui/hooks";
import { useToast } from "../../ui/hooks/useToast";
import { projectService, taskService } from "../services";
import type {
  CreateProjectRequest,
  Project,
  UpdateProjectRequest,
} from "../types";
import { useProjectMutation } from "./useProjectMutation";

// Query keys factory for better organization
export const projectKeys = {
  all: ["projects"] as const,
  lists: () => [...projectKeys.all, "list"] as const,
  list: (filters?: unknown) => [...projectKeys.lists(), filters] as const,
  details: () => [...projectKeys.all, "detail"] as const,
  detail: (id: string) => [...projectKeys.details(), id] as const,
  tasks: (projectId: string) =>
    [...projectKeys.detail(projectId), "tasks"] as const,
  taskCounts: () => ["taskCounts"] as const,
  features: (projectId: string) =>
    [...projectKeys.detail(projectId), "features"] as const,
  documents: (projectId: string) =>
    [...projectKeys.detail(projectId), "documents"] as const,
};

// Fetch all projects with smart polling
export function useProjects() {
  return usePolling<Project[]>({
    key: projectKeys.lists(),
    fetcher: () => projectService.listProjects(),
    baseInterval: 20000, // 20s base interval
    refetchOnWindowFocus: true, // Refetch when tab gains focus (ETag makes this cheap)
    staleTime: 15000, // Consider data stale after 15 seconds
  });
}

// Fetch task counts for all projects
export function useTaskCounts() {
  return useQuery<
    Awaited<ReturnType<typeof taskService.getTaskCountsForAllProjects>>
  >({
    queryKey: projectKeys.taskCounts(),
    queryFn: () => taskService.getTaskCountsForAllProjects(),
    refetchInterval: false, // Don't poll, only refetch manually
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });
}

// Fetch project features
export function useProjectFeatures(projectId: string | undefined) {
  return useQuery({
    queryKey: projectId
      ? projectKeys.features(projectId)
      : ["features-undefined"],
    queryFn: () =>
      projectId
        ? projectService.getProjectFeatures(projectId)
        : Promise.reject("No project ID"),
    enabled: !!projectId,
    staleTime: 30000, // Cache for 30 seconds
  });
}

// Create project mutation with optimistic updates
export function useCreateProject() {
  const qc = useQueryClient();
  const { showToast } = useToast();

  return useProjectMutation<
    Awaited<ReturnType<typeof projectService.createProject>>,
    CreateProjectRequest
  >({
    mutationFn: (projectData) => projectService.createProject(projectData),
    optimisticUpdate: (queryClient, newProjectData) => {
      const previousProjects = queryClient.getQueryData<Project[]>(
        projectKeys.lists(),
      );
      const tempId = `temp-${Date.now()}`;
      const optimisticProject: Project = {
        id: tempId,
        title: newProjectData.title,
        description: newProjectData.description,
        github_repo: newProjectData.github_repo,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        prd: undefined,
        features: [],
        data: undefined,
        docs: [],
        pinned: false,
      };
      queryClient.setQueryData(
        projectKeys.lists(),
        (old: Project[] | undefined) => {
          if (!old) return [optimisticProject];
          return [optimisticProject, ...old];
        },
      );
      return () => {
        if (previousProjects) {
          queryClient.setQueryData(projectKeys.lists(), previousProjects);
        }
      };
    },
    onError: (error, variables) => {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      console.error("Failed to create project:", error, { variables });
      showToast(`Failed to create project: ${errorMessage}`, "error");
    },
    onSuccess: (response, _variables, _context) => {
      const newProject = response.project;
      qc.setQueryData(projectKeys.lists(), (old: Project[] | undefined) => {
        if (!old) return [newProject];
        return old
          .map((project) =>
            project.id?.startsWith?.("temp-") ? newProject : project,
          )
          .filter(
            (project, index, self) =>
              index === self.findIndex((p) => p.id === project.id),
          );
      });
      showToast("Project created successfully!", "success");
    },
  });
}

// Update project mutation (for pinning, etc.)
export function useUpdateProject() {
  const { showToast } = useToast();

  return useProjectMutation<
    Project,
    { projectId: string; updates: UpdateProjectRequest }
  >({
    mutationFn: ({ projectId, updates }) =>
      projectService.updateProject(projectId, updates),
    optimisticUpdate: (qc, { projectId, updates }) => {
      const previous = qc.getQueryData<Project[]>(projectKeys.lists());
      qc.setQueryData(projectKeys.lists(), (old: Project[] | undefined) => {
        if (!old) return old;
        if (updates.pinned === true) {
          return old.map((p) => ({ ...p, pinned: p.id === projectId }));
        }
        return old.map((p) => (p.id === projectId ? { ...p, ...updates } : p));
      });
      return () => {
        if (previous) qc.setQueryData(projectKeys.lists(), previous);
      };
    },
    onSuccess: (data, variables) => {
      if (variables.updates.pinned !== undefined) {
        const message = variables.updates.pinned
          ? `Pinned "${data.title}" as default project`
          : `Removed "${data.title}" from default selection`;
        showToast(message, "info");
      }
    },
  });
}

// Delete project mutation with optimistic updates
export function useDeleteProject() {
  const qc = useQueryClient();
  const { showToast } = useToast();

  return useProjectMutation<void, string>({
    mutationFn: (projectId) => projectService.deleteProject(projectId),
    optimisticUpdate: (queryClient, projectId) => {
      const previous = queryClient.getQueryData<Project[]>(projectKeys.lists());
      queryClient.setQueryData(
        projectKeys.lists(),
        (old: Project[] | undefined) => {
          if (!old) return old;
          return old.filter((project) => project.id !== projectId);
        },
      );
      return () => {
        if (previous) queryClient.setQueryData(projectKeys.lists(), previous);
      };
    },
    onSuccess: (_, projectId) => {
      qc.removeQueries({
        queryKey: projectKeys.detail(projectId),
        exact: false,
      });
      showToast("Project deleted successfully", "success");
    },
  });
}
