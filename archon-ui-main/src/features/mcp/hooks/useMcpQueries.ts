import { useQuery } from "@tanstack/react-query";
import { usePolling } from "../../ui/hooks";
import { mcpApi } from "../services";

// Query keys factory
export const mcpKeys = {
  all: ["mcp"] as const,
  status: () => [...mcpKeys.all, "status"] as const,
  config: () => [...mcpKeys.all, "config"] as const,
  sessions: () => [...mcpKeys.all, "sessions"] as const,
  clients: () => [...mcpKeys.all, "clients"] as const,
};

export function useMcpStatus() {
  return usePolling({
    key: mcpKeys.status(),
    fetcher: () => mcpApi.getStatus(),
    baseInterval: 5000,
    refetchOnWindowFocus: false,
    staleTime: 3000,
  });
}

export function useMcpConfig() {
  return useQuery({
    queryKey: mcpKeys.config(),
    queryFn: () => mcpApi.getConfig(),
    staleTime: Infinity, // Config rarely changes
    throwOnError: true,
  });
}

export function useMcpClients() {
  return usePolling({
    key: mcpKeys.clients(),
    fetcher: () => mcpApi.getClients(),
    baseInterval: 10000,
    refetchOnWindowFocus: false,
    staleTime: 8000,
  });
}

export function useMcpSessionInfo() {
  return usePolling({
    key: mcpKeys.sessions(),
    fetcher: () => mcpApi.getSessionInfo(),
    baseInterval: 10000,
    refetchOnWindowFocus: false,
    staleTime: 8000,
  });
}
