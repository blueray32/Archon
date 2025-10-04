useDatabaseMutation helper

- cancelQueryKeys: Limits which queries are cancelled during onMutate.
  - Defaults to invalidateQueryKeys when provided.
  - If neither is set, no cancellation occurs.

- Recommended usage:
  - For known query scopes (e.g., projectId available in the hook): pass cancelQueryKeys to avoid global cancels.
  - For dynamic scopes known only at mutate time (e.g., createTask where project_id comes from variables): perform a scoped qc.cancelQueries inside optimisticUpdate.

- Example (project-scoped):
  useDatabaseMutation({
    mutationFn,
    invalidateQueryKeys: [projectKeys.lists(), projectKeys.detail(id)],
    cancelQueryKeys: [projectKeys.lists(), projectKeys.detail(id)],
  })

- Example (dynamic scope in optimisticUpdate):
  useDatabaseMutation({
    mutationFn,
    optimisticUpdate: (qc, vars) => {
      qc.cancelQueries({ queryKey: taskKeys.all(vars.project_id) })
      // ...apply optimistic changes
    },
  })
