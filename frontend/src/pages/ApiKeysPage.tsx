import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface ApiKeyInfo {
  id: string;
  name: string;
  key_prefix: string;
  owner_email: string;
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
  raw_key?: string;
}

function useApiKeys() {
  return useQuery({
    queryKey: ["api-keys"],
    queryFn: () => apiFetch<ApiKeyInfo[]>("/api-keys"),
  });
}

function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string }) =>
      apiFetch<ApiKeyInfo>("/api-keys", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}

function useRevokeApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ status: string }>(`/api-keys/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}

export function ApiKeysPage() {
  const { data: user } = useCurrentUser();
  const { data: keys } = useApiKeys();
  const createKey = useCreateApiKey();
  const revokeKey = useRevokeApiKey();
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState<string | null>(null);

  if (!user?.is_admin) {
    return <p className="text-gray-500">Admin access required.</p>;
  }

  const handleCreate = () => {
    if (!name.trim()) return;
    createKey.mutate({ name: name.trim() }, {
      onSuccess: (data) => {
        setNewKey(data.raw_key || null);
        setName("");
      },
    });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">API Keys</h1>

      {newKey && (
        <div className="rounded-md border border-green-300 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-800 mb-2">New API key created — copy it now, it won't be shown again:</p>
          <code className="block text-sm font-mono bg-white border rounded p-2 break-all select-all">{newKey}</code>
          <button onClick={() => { navigator.clipboard.writeText(newKey); }} className="mt-2 text-xs text-green-700 hover:text-green-900">Copy to clipboard</button>
        </div>
      )}

      <div className="space-y-3">
        {keys?.map((k) => (
          <Card key={k.id}>
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{k.name}</span>
                  <Badge color={k.is_active ? "green" : "red"}>{k.is_active ? "active" : "revoked"}</Badge>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  <code>{k.key_prefix}</code> — {k.owner_email} — {new Date(k.created_at).toLocaleDateString()}
                </div>
              </div>
              {k.is_active && (
                <Button size="sm" variant="danger" onClick={() => revokeKey.mutate(k.id)}>Revoke</Button>
              )}
            </div>
          </Card>
        ))}
        {keys?.length === 0 && <p className="text-sm text-gray-500">No API keys yet.</p>}
      </div>

      <Card title="Create API Key">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Key name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. claude-code-agent"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
            />
          </div>
          <Button onClick={handleCreate} loading={createKey.isPending}>Create</Button>
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Usage: <code>curl -H "X-API-Key: mcp_xxx" https://mcp.yoops.org/api/v1/search?q=playwright</code>
        </p>
      </Card>
    </div>
  );
}
