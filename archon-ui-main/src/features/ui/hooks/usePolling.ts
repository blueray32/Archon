import { type QueryKey, type UseQueryOptions, type UseQueryResult, useQuery } from "@tanstack/react-query";
import { useSmartPolling } from "./useSmartPolling";

/**
 * Generic polling hook that pairs TanStack Query with smart interval control.
 *
 * - Respects tab visibility and focus via `useSmartPolling` to reduce noise
 * - Plays nicely with ETag-aware services (e.g., callAPIWithETag) when the provided
 *   `fetcher` uses those services under the hood
 */
export type UsePollingOptions<TData, TError = unknown> = {
  key: QueryKey;
  fetcher: () => Promise<TData>;
  baseInterval?: number; // ms; default 10s
  enabled?: boolean;
  staleTime?: number; // ms
  refetchOnWindowFocus?: boolean; // default true
  select?: UseQueryOptions<TData, TError, TData>["select"];
  initialData?: TData;
};

export function usePolling<TData, TError = unknown>(
  options: UsePollingOptions<TData, TError>,
): UseQueryResult<TData, TError> {
  const {
    key,
    fetcher,
    baseInterval = 10000,
    enabled = true,
    staleTime,
    refetchOnWindowFocus = true,
    select,
    initialData,
  } = options;

  const { refetchInterval } = useSmartPolling(baseInterval);

  return useQuery<TData, TError>({
    queryKey: key,
    queryFn: fetcher,
    enabled,
    refetchInterval,
    refetchOnWindowFocus,
    staleTime,
    select,
    initialData,
  });
}
