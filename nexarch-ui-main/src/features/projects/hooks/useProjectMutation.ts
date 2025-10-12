import type { QueryKey, UseMutationOptions } from "@tanstack/react-query";
import {
  type InvalidateEndpoint,
  useDatabaseMutation,
} from "../../ui/hooks/useDatabaseMutation";
import { projectKeys } from "./useProjectQueries";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type UseProjectMutationArgs<TData, TVariables, TError = unknown> = {
  mutationFn: (variables: TVariables) => Promise<TData>;
  projectId?: string;
  extraInvalidateEndpoints?: { endpoint: string; method?: HttpMethod }[];
  extraInvalidateQueryKeys?: QueryKey[];
  optimisticUpdate?: Parameters<
    typeof useDatabaseMutation<TData, TVariables, TError>
  >[0]["optimisticUpdate"];
  onError?: UseMutationOptions<TData, TError, TVariables, unknown>["onError"];
  onSuccess?: UseMutationOptions<
    TData,
    TError,
    TVariables,
    unknown
  >["onSuccess"];
  onSettled?: UseMutationOptions<
    TData,
    TError,
    TVariables,
    unknown
  >["onSettled"];
  onMutate?: UseMutationOptions<TData, TError, TVariables, unknown>["onMutate"];
};

/**
 * Project-scoped mutation hook that defaults to invalidating common project endpoints
 * and project-related TanStack Query keys. Supports optimistic updates with rollback.
 */
export function useProjectMutation<TData, TVariables, TError = unknown>(
  args: UseProjectMutationArgs<TData, TVariables, TError>,
) {
  const {
    mutationFn,
    projectId,
    extraInvalidateEndpoints = [],
    extraInvalidateQueryKeys = [],
    optimisticUpdate,
    onError,
    onSuccess,
    onSettled,
    onMutate,
  } = args;

  const defaults: InvalidateEndpoint[] = [
    { endpoint: "/api/projects", method: "GET" },
  ];
  if (projectId) {
    defaults.push(
      { endpoint: `/api/projects/${projectId}`, method: "GET" },
      { endpoint: `/api/projects/${projectId}/tasks`, method: "GET" },
    );
  }

  const invalidateQueryKeys: QueryKey[] = [projectKeys.lists()];
  if (projectId) {
    invalidateQueryKeys.push(
      projectKeys.detail(projectId),
      projectKeys.tasks(projectId),
    );
  }

  return useDatabaseMutation<TData, TVariables, TError>({
    mutationFn,
    optimisticUpdate,
    invalidateEndpoints: [...defaults, ...extraInvalidateEndpoints],
    invalidateQueryKeys: [...invalidateQueryKeys, ...extraInvalidateQueryKeys],
    cancelQueryKeys: [...invalidateQueryKeys, ...extraInvalidateQueryKeys],
    onError,
    onSuccess,
    onSettled,
    onMutate,
  });
}
