import { useQueryClient } from "@tanstack/react-query";
import { usePolling } from "../../../ui/hooks";
import { useDatabaseMutation } from "../../../ui/hooks/useDatabaseMutation";
import { useToast } from "../../../ui/hooks/useToast";
import { projectKeys } from "../../hooks/useProjectQueries";
import { taskService } from "../services";
import type { CreateTaskRequest, Task, UpdateTaskRequest } from "../types";

// Query keys factory for tasks
export const taskKeys = {
  all: (projectId: string) => ["projects", projectId, "tasks"] as const,
};

// Fetch tasks for a specific project
export function useProjectTasks(projectId: string | undefined, enabled = true) {
  return usePolling<Task[]>({
    key: projectId ? taskKeys.all(projectId) : ["tasks-undefined"],
    fetcher: async () => {
      if (!projectId) throw new Error("No project ID");
      return taskService.getTasksByProject(projectId);
    },
    enabled: !!projectId && enabled,
    baseInterval: 5000, // 5s base interval for faster MCP updates
    refetchOnWindowFocus: true,
    staleTime: 10000,
  });
}

// Create task mutation with optimistic updates
export function useCreateTask() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useDatabaseMutation<Task, CreateTaskRequest>({
    mutationFn: (taskData) => taskService.createTask(taskData),
    optimisticUpdate: (qc, newTaskData) => {
      // Cancel any outgoing refetches for this project's tasks
      qc.cancelQueries({ queryKey: taskKeys.all(newTaskData.project_id) });
      // Snapshot the previous value
      const previousTasks = qc.getQueryData(
        taskKeys.all(newTaskData.project_id),
      );

      // Create optimistic task with temporary ID
      const tempId = `temp-${Date.now()}`;
      const optimisticTask: Task = {
        id: tempId, // Temporary ID until real one comes back
        ...newTaskData,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        // Ensure all required fields have defaults
        task_order: newTaskData.task_order ?? 100,
        status: newTaskData.status ?? "todo",
        assignee: newTaskData.assignee ?? "User",
      } as Task;

      // Optimistically add the new task
      qc.setQueryData(
        taskKeys.all(newTaskData.project_id),
        (old: Task[] | undefined) => {
          if (!old) return [optimisticTask];
          return [...old, optimisticTask];
        },
      );

      return () => {
        if (previousTasks) {
          qc.setQueryData(taskKeys.all(newTaskData.project_id), previousTasks);
        }
      };
    },
    onError: (error, variables) => {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      console.error("Failed to create task:", error, { variables });
      showToast(`Failed to create task: ${errorMessage}`, "error");
    },
    onSuccess: (data, variables) => {
      // Replace optimistic task with real one from server
      queryClient.setQueryData(
        taskKeys.all(variables.project_id),
        (old: Task[] | undefined) => {
          if (!old) return [data];
          // Replace only the specific temp task with real one
          return old
            .map((task) => (task.id?.startsWith?.("temp-") ? data : task))
            .filter(
              (task, index, self) =>
                // Remove any duplicates just in case
                index === self.findIndex((t) => t.id === task.id),
            );
        },
      );
      queryClient.invalidateQueries({ queryKey: projectKeys.taskCounts() });
      showToast("Task created successfully", "success");
    },
    onSettled: (_data, _error, variables) => {
      // Always refetch to ensure consistency after operation completes
      queryClient.invalidateQueries({
        queryKey: taskKeys.all(variables.project_id),
      });
    },
    // Dynamic cancel is scoped inside optimisticUpdate since project_id
    // is provided at mutate time.
  });
}

// Update task mutation with optimistic updates
export function useUpdateTask(projectId: string) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useDatabaseMutation<
    Task,
    { taskId: string; updates: UpdateTaskRequest },
    Error
  >({
    mutationFn: ({ taskId, updates }) =>
      taskService.updateTask(taskId, updates),
    optimisticUpdate: (qc, { taskId, updates }) => {
      // Snapshot the previous value
      const previousTasks = qc.getQueryData<Task[]>(taskKeys.all(projectId));

      // Optimistically update
      qc.setQueryData<Task[]>(taskKeys.all(projectId), (old) => {
        if (!old) return old;
        return old.map((task) =>
          task.id === taskId ? { ...task, ...updates } : task,
        );
      });

      return () => {
        if (previousTasks)
          qc.setQueryData(taskKeys.all(projectId), previousTasks);
      };
    },
    onError: (error, variables) => {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      console.error("Failed to update task:", error, { variables });
      showToast(`Failed to update task: ${errorMessage}`, "error");
      // Refetch on error to ensure consistency
      queryClient.invalidateQueries({ queryKey: taskKeys.all(projectId) });
      queryClient.invalidateQueries({ queryKey: projectKeys.taskCounts() });
    },
    onSuccess: (data, { updates }) => {
      // Merge server response to keep timestamps and computed fields in sync
      queryClient.setQueryData<Task[]>(taskKeys.all(projectId), (old) =>
        old ? old.map((t) => (t.id === data.id ? data : t)) : old,
      );
      // Only invalidate counts if status changed (which affects counts)
      if (updates.status) {
        queryClient.invalidateQueries({ queryKey: projectKeys.taskCounts() });
        // Show toast for significant status changes
        showToast(`Task moved to ${updates.status}`, "success");
      }
    },
    cancelQueryKeys: [taskKeys.all(projectId)],
  });
}

// Delete task mutation
export function useDeleteTask(projectId: string) {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useDatabaseMutation<void, string, Error>({
    mutationFn: (taskId: string) => taskService.deleteTask(taskId),
    optimisticUpdate: (qc, taskId) => {
      // Snapshot the previous value
      const previousTasks = qc.getQueryData<Task[]>(taskKeys.all(projectId));

      // Optimistically remove the task
      qc.setQueryData<Task[]>(taskKeys.all(projectId), (old) => {
        if (!old) return old;
        return old.filter((task) => task.id !== taskId);
      });

      return () => {
        if (previousTasks)
          qc.setQueryData(taskKeys.all(projectId), previousTasks);
      };
    },
    onError: (error, taskId) => {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      console.error("Failed to delete task:", error, { taskId });
      showToast(`Failed to delete task: ${errorMessage}`, "error");
    },
    onSuccess: () => {
      showToast("Task deleted successfully", "success");
    },
    onSettled: () => {
      // Always refetch counts after deletion
      queryClient.invalidateQueries({ queryKey: projectKeys.taskCounts() });
    },
    cancelQueryKeys: [taskKeys.all(projectId)],
  });
}
