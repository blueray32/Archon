import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDeleteKnowledgeItem } from "../useCrawlQueries";

vi.mock("../../services/knowledgeBaseService", () => ({
  knowledgeBaseService: {
    deleteKnowledgeItem: vi.fn(),
  },
}));

vi.mock("../../contexts/ToastContext", () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));

function createWrapper(qc: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe("useDeleteKnowledgeItem", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("optimistically removes item and keeps on success", async () => {
    const { knowledgeBaseService } = await import(
      "../../services/knowledgeBaseService"
    );
    vi.mocked(knowledgeBaseService.deleteKnowledgeItem).mockResolvedValue(
      undefined as any,
    );

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    qc.setQueryData(["knowledge", "items"], {
      items: [
        { source_id: "a", metadata: {} },
        { source_id: "b", metadata: {} },
      ],
      total: 2,
    });

    const { result } = renderHook(() => useDeleteKnowledgeItem(), {
      wrapper: createWrapper(qc),
    });

    await result.current.mutateAsync("a");
    expect(qc.getQueryData(["knowledge", "items"]))
      .toMatchObject({ items: [{ source_id: "b" }], total: 1 });
  });

  it("rolls back on error", async () => {
    const { knowledgeBaseService } = await import(
      "../../services/knowledgeBaseService"
    );
    vi.mocked(knowledgeBaseService.deleteKnowledgeItem).mockRejectedValue(
      new Error("fail"),
    );

    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const initial = {
      items: [
        { source_id: "a", metadata: {} },
        { source_id: "b", metadata: {} },
      ],
      total: 2,
    };
    qc.setQueryData(["knowledge", "items"], initial);

    const { result } = renderHook(() => useDeleteKnowledgeItem(), {
      wrapper: createWrapper(qc),
    });

    await expect(result.current.mutateAsync("a")).rejects.toThrow("fail");
    expect(qc.getQueryData(["knowledge", "items"]))
      .toMatchObject(initial);
  });
});
