import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import type React from "react";
import { describe, expect, it } from "vitest";
import { useDatabaseMutation } from "../useDatabaseMutation";

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return { Wrapper, qc };
}

describe("useDatabaseMutation", () => {
  it("applies optimistic update and rolls back on error", async () => {
    const { Wrapper, qc } = createWrapper();

    qc.setQueryData(["k"], [1]);

    const { result } = renderHook(
      () =>
        useDatabaseMutation<number, number>({
          mutationFn: async () => {
            throw new Error("boom");
          },
          optimisticUpdate: (client, value) => {
            const prev = client.getQueryData<number[]>(["k"]);
            client.setQueryData(["k"], [...(prev ?? []), value]);
            return () => client.setQueryData(["k"], prev);
          },
        }),
      { wrapper: Wrapper },
    );

    await expect(result.current.mutateAsync(2)).rejects.toThrow("boom");
    expect(qc.getQueryData(["k"])).toEqual([1]);
  });

  it("keeps optimistic update on success", async () => {
    const { Wrapper, qc } = createWrapper();
    qc.setQueryData(["k"], [1]);

    const { result } = renderHook(
      () =>
        useDatabaseMutation<number, number>({
          mutationFn: async (v) => v,
          optimisticUpdate: (client, value) => {
            const prev = client.getQueryData<number[]>(["k"]);
            client.setQueryData(["k"], [...(prev ?? []), value]);
            return () => client.setQueryData(["k"], prev);
          },
        }),
      { wrapper: Wrapper },
    );

    await result.current.mutateAsync(3);
    expect(qc.getQueryData(["k"])).toEqual([1, 3]);
  });

  it("scopes cancellations to provided keys only", async () => {
    const { Wrapper, qc } = createWrapper();

    // Spy on cancelQueries to ensure it's not called globally
    const spy = vi.spyOn(qc, "cancelQueries");

    const { result } = renderHook(
      () =>
        useDatabaseMutation<number, number>({
          mutationFn: async (v) => v,
          // Set explicit cancel scope
          cancelQueryKeys: [["only-this"]],
          invalidateQueryKeys: [["only-this"]],
        }),
      { wrapper: Wrapper },
    );

    await result.current.mutateAsync(1);

    // Expect cancel called with the scoped key, and not with no-arg global cancel
    expect(spy).toHaveBeenCalled();
    const calledWithGlobal = spy.mock.calls.some(
      (args) => args.length === 0 || args[0] == null,
    );
    expect(calledWithGlobal).toBe(false);
    const calledWithScoped = spy.mock.calls.some(
      (args) =>
        !!args[0] &&
        typeof args[0] === "object" &&
        JSON.stringify(args[0]).includes("only-this"),
    );
    expect(calledWithScoped).toBe(true);
  });
});
