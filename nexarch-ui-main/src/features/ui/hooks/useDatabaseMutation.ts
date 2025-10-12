import type { QueryKey } from "@tanstack/react-query";
import {
  type UseMutationOptions,
  type UseMutationResult,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { invalidateETagCache } from "../../projects/shared/apiWithEtag";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type InvalidateEndpoint = {
  endpoint: string;
  method?: HttpMethod;
};

type BaseOptions<TData, TVariables, TError, TContext> = Omit<
  UseMutationOptions<
    TData,
    TError,
    TVariables,
    { rollback?: () => void } & TContext
  >,
  "mutationFn"
>;

export type UseDatabaseMutationOptions<
  TData,
  TVariables,
  TError = unknown,
  TContext = unknown,
> = BaseOptions<TData, TVariables, TError, TContext> & {
  mutationFn: (variables: TVariables) => Promise<TData>;
  invalidateEndpoints?: InvalidateEndpoint[];
  invalidateQueryKeys?: QueryKey[];
  /**
   * Limits which queries are cancelled before an optimistic update.
   * - Defaults to `invalidateQueryKeys` when provided.
   * - If empty or undefined, no global cancellation is performed.
   */
  cancelQueryKeys?: QueryKey[];
  optimisticUpdate?: (
    qc: ReturnType<typeof useQueryClient>,
    variables: TVariables,
  ) => (() => void) | undefined;
};

/**
 * Generic mutation hook with optional optimistic updates and ETag-aware invalidation.
 * - Never overwrites caller-provided success/error handlers; composes them.
 */
export function useDatabaseMutation<
  TData,
  TVariables,
  TError = unknown,
  TContext = unknown,
>(
  options: UseDatabaseMutationOptions<TData, TVariables, TError, TContext>,
): UseMutationResult<
  TData,
  TError,
  TVariables,
  { rollback?: () => void } & TContext
> {
  const {
    mutationFn,
    invalidateEndpoints = [],
    invalidateQueryKeys = [],
    optimisticUpdate,
    onMutate,
    onError,
    onSettled,
    ...rest
  } = options;

  const qc = useQueryClient();

  return useMutation<
    TData,
    TError,
    TVariables,
    { rollback?: () => void } & TContext
  >({
    mutationFn,
    async onMutate(variables) {
      // Scope cancellations to avoid aborting unrelated polling queries.
      // Prefer explicitly provided cancelQueryKeys; otherwise, use
      // invalidateQueryKeys; if none, skip cancellation.
      const scopedKeys = options.cancelQueryKeys ?? invalidateQueryKeys ?? [];
      if (scopedKeys.length > 0) {
        await Promise.all(
          scopedKeys.map((key) =>
            qc.cancelQueries({ queryKey: key }).catch(() => undefined),
          ),
        );
      }
      const rollback = optimisticUpdate?.(qc, variables);
      const ctx = (await onMutate?.(variables)) as TContext | undefined;
      // Guard against undefined context; only spread when present
      return (ctx
        ? { rollback, ...(ctx as object) }
        : { rollback }) as { rollback?: () => void } & TContext;
    },
    onError(error, variables, context) {
      if (context?.rollback) {
        try {
          context.rollback();
        } catch {}
      }
      onError?.(error, variables, context);
    },
    async onSettled(data, error, variables, context) {
      // ETag cache invalidation
      for (const { endpoint, method } of invalidateEndpoints) {
        try {
          invalidateETagCache(endpoint, method ?? "GET");
        } catch (e) {
          if (
            typeof import.meta !== "undefined" &&
            import.meta.env?.MODE !== "production"
          ) {
            // eslint-disable-next-line no-console
            console.warn("[useDatabaseMutation] ETag invalidation failed", {
              endpoint,
              method,
              error: e,
            });
          }
        }
      }
      // Query invalidation
      for (const key of invalidateQueryKeys) {
        try {
          await qc.invalidateQueries({ queryKey: key });
        } catch (e) {
          if (
            typeof import.meta !== "undefined" &&
            import.meta.env?.MODE !== "production"
          ) {
            // eslint-disable-next-line no-console
            console.warn("[useDatabaseMutation] Query invalidation failed", {
              key,
              error: e,
            });
          }
        }
      }
      await onSettled?.(data, error, variables, context);
    },
    ...rest,
  });
}
