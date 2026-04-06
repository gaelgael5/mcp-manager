import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface Instance {
  id: string;
  name: string;
  url: string;
  has_api_key: boolean;
  is_active: boolean;
  last_sync: string | null;
  last_sync_count: number;
  created_at: string;
}

function useInstances() {
  return useQuery({
    queryKey: ["instances"],
    queryFn: () => apiFetch<Instance[]>("/instances"),
  });
}

export function InstancesPage() {
  const { data: user } = useCurrentUser();
  const isAdmin = user?.is_admin === true;
  const { data: instances } = useInstances();
  const qc = useQueryClient();

  const createInstance = useMutation({
    mutationFn: (body: { name: string; url: string; api_key?: string }) =>
      apiFetch<Instance>("/instances", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instances"] }),
  });

  const deleteInstance = useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ status: string }>(`/instances/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instances"] }),
  });

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");

  const handleCreate = () => {
    if (!name.trim() || !url.trim()) return;
    createInstance.mutate({
      name: name.trim(),
      url: url.trim(),
      api_key: apiKey.trim() || undefined,
    });
    setName("");
    setUrl("");
    setApiKey("");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">MCP Manager Instances</h1>
        <p className="text-sm text-gray-500 mt-1">Connect to other MCP Manager instances to sync their catalog.</p>
      </div>

      <div className="space-y-3">
        {instances?.map((inst) => (
          <Card key={inst.id}>
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{inst.name}</span>
                  <Badge color={inst.is_active ? "green" : "red"}>{inst.is_active ? "active" : "inactive"}</Badge>
                  {inst.has_api_key && <Badge color="blue">API key</Badge>}
                </div>
                <a href={inst.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">{inst.url}</a>
                <div className="mt-1 text-xs text-gray-400">
                  {inst.last_sync ? `Last sync: ${new Date(inst.last_sync).toLocaleString()} (${inst.last_sync_count} services)` : "Never synced"}
                </div>
              </div>
              {isAdmin && (
                <Button size="sm" variant="danger" onClick={() => deleteInstance.mutate(inst.id)}>Remove</Button>
              )}
            </div>
          </Card>
        ))}
        {instances?.length === 0 && <p className="text-sm text-gray-500">No instances configured. Add one to start federating.</p>}
      </div>

      {isAdmin && (
        <Card title="Add Instance">
          <div className="space-y-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-1">Name</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="MCP Community Hub" className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-1">URL</label>
                <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://mcp.other-org.com" className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">API Key (optional)</label>
              <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="mcp_xxx..." className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono" />
            </div>
            <Button onClick={handleCreate} loading={createInstance.isPending}>Add Instance</Button>
          </div>
        </Card>
      )}
    </div>
  );
}
