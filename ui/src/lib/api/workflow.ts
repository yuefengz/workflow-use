import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkflowMetadata } from "../../types/workflow-layout.types";

const API_BASE = "http://localhost:8000";

export function useWorkflows() {
  return useQuery({
    queryKey: ["workflows"],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/api/workflows?_=${Date.now()}`);
      if (!response.ok) {
        throw new Error("Failed to fetch workflows");
      }
      const data = await response.json();
      return data.workflows as string[];
    },
  });
}

export function useWorkflow(name: string | null) {
  return useQuery({
    queryKey: ["workflow", name],
    queryFn: async () => {
      if (!name) return null;
      const response = await fetch(
        `${API_BASE}/api/workflows/${name}?_=${Date.now()}`
      );
      if (!response.ok) {
        throw new Error("Failed to fetch workflow");
      }
      return response.json();
    },
    enabled: !!name,
  });
}

export function useUpdateWorkflowMetadata() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      name,
      metadata,
    }: {
      name: string;
      metadata: WorkflowMetadata;
    }) => {
      const response = await fetch(
        `${API_BASE}/api/workflows/update-metadata`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name, metadata }),
        }
      );
      if (!response.ok) {
        throw new Error("Failed to update workflow metadata");
      }
    },
    onSuccess: (_, { name }) => {
      queryClient.invalidateQueries({ queryKey: ["workflow", name] });
    },
  });
}
