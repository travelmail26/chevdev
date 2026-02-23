import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, buildUrl } from "@shared/routes";
import { type Thread } from "@shared/schema";
import { getCanonicalUserHeader } from "@/lib/canonical-user";

export function useThreads() {
  return useQuery({
    queryKey: [api.threads.list.path],
    queryFn: async () => {
      const res = await fetch(api.threads.list.path, {
        headers: {
          ...getCanonicalUserHeader(),
        },
      });
      if (!res.ok) throw new Error("Failed to fetch threads");
      return api.threads.list.responses[200].parse(await res.json());
    },
  });
}

export function useThread(id: number | null) {
  return useQuery({
    queryKey: [api.threads.get.path, id],
    enabled: !!id,
    queryFn: async () => {
      if (!id) throw new Error("Thread ID required");
      const url = buildUrl(api.threads.get.path, { id });
      const res = await fetch(url, {
        headers: {
          ...getCanonicalUserHeader(),
        },
      });
      if (res.status === 404) return null;
      if (!res.ok) throw new Error("Failed to fetch thread");
      return api.threads.get.responses[200].parse(await res.json());
    },
  });
}

export function useCreateThread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (title?: string) => {
      const res = await fetch(api.threads.create.path, {
        method: api.threads.create.method,
        headers: {
          "Content-Type": "application/json",
          ...getCanonicalUserHeader(),
        },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error("Failed to create thread");
      return api.threads.create.responses[201].parse(await res.json());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.threads.list.path] });
    },
  });
}
