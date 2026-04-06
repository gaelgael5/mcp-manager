import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface LLMProvider {
  id: number;
  type: string;
  image?: string;
  args: Record<string, string>;
}

interface LLMConfig {
  workers: number;
  claude_rate_limit_per_second: number;
  llm: LLMProvider[];
}

function useLLMConfig() {
  return useQuery({
    queryKey: ["settings", "llm"],
    queryFn: () => apiFetch<LLMConfig>("/settings/llm"),
  });
}

function useSaveLLMConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (config: LLMConfig) =>
      apiFetch<{ status: string }>("/settings/llm", {
        method: "PUT",
        body: JSON.stringify({ config }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "llm"] }),
  });
}

interface DockerImage {
  name: string;
  default_args: Record<string, string>;
}

function useDockerImages() {
  return useQuery({
    queryKey: ["settings", "docker-images"],
    queryFn: () => apiFetch<DockerImage[]>("/settings/docker-images"),
  });
}

function ProviderEditor({ provider, onChange, onDelete }: {
  provider: LLMProvider;
  onChange: (p: LLMProvider) => void;
  onDelete: () => void;
}) {
  const { data: dockerImages } = useDockerImages();

  const handleTypeChange = (newType: string) => {
    if (newType === "ollama") {
      onChange({ ...provider, type: "ollama", image: undefined, args: { url: "http://192.168.10.80:11434", model: "llama3.1:8b" } });
    } else {
      // Default to first docker image
      const firstImage = dockerImages?.[0];
      onChange({
        ...provider,
        type: "docker",
        image: firstImage?.name || "claude",
        args: firstImage?.default_args || {},
      });
    }
  };

  const handleImageChange = (imageName: string) => {
    const img = dockerImages?.find((i) => i.name === imageName);
    onChange({
      ...provider,
      image: imageName,
      args: img?.default_args || provider.args,
    });
  };

  return (
    <Card>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge color={provider.type === "ollama" ? "blue" : "purple"}>{provider.type}</Badge>
            <span className="text-sm font-medium">Provider #{provider.id}</span>
            {provider.image && <Badge color="gray">{provider.image}</Badge>}
          </div>
          <button onClick={onDelete} className="text-xs text-red-400 hover:text-red-600">Remove</button>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Type</label>
            <select
              value={provider.type}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
            >
              <option value="ollama">ollama</option>
              <option value="docker">docker</option>
            </select>
          </div>
          {provider.type === "docker" && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Image</label>
              <select
                value={provider.image || ""}
                onChange={(e) => handleImageChange(e.target.value)}
                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
              >
                {dockerImages?.map((img) => (
                  <option key={img.name} value={img.name}>{img.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Args (JSON)</label>
          <textarea
            value={JSON.stringify(provider.args, null, 2)}
            onChange={(e) => {
              try {
                onChange({ ...provider, args: JSON.parse(e.target.value) });
              } catch { /* ignore invalid JSON while typing */ }
            }}
            className="w-full rounded border border-gray-300 px-2 py-1 text-xs font-mono h-20"
          />
        </div>
      </div>
    </Card>
  );
}

export function SettingsPage() {
  const { data: user } = useCurrentUser();
  const { data: config } = useLLMConfig();
  const saveConfig = useSaveLLMConfig();

  const [localConfig, setLocalConfig] = useState<LLMConfig | null>(null);

  useEffect(() => {
    if (config && !localConfig) {
      setLocalConfig(config);
    }
  }, [config, localConfig]);

  if (!user?.is_admin) {
    return <p className="text-gray-500">Admin access required.</p>;
  }

  if (!localConfig) {
    return <p className="text-gray-500">Loading...</p>;
  }

  const handleSave = () => {
    saveConfig.mutate(localConfig);
  };

  const addProvider = () => {
    const maxId = Math.max(0, ...localConfig.llm.map((p) => p.id));
    setLocalConfig({
      ...localConfig,
      llm: [...localConfig.llm, { id: maxId + 1, type: "ollama", args: { url: "http://localhost:11434", model: "llama3.1:8b" } }],
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <Button onClick={handleSave} loading={saveConfig.isPending}>
          {saveConfig.isSuccess ? "Saved!" : "Save"}
        </Button>
      </div>

      <Card title="General">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Workers</label>
            <input
              type="number"
              min={1}
              max={10}
              value={localConfig.workers}
              onChange={(e) => setLocalConfig({ ...localConfig, workers: parseInt(e.target.value) || 1 })}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Claude rate limit (req/s)</label>
            <input
              type="number"
              min={0.1}
              max={10}
              step={0.1}
              value={localConfig.claude_rate_limit_per_second}
              onChange={(e) => setLocalConfig({ ...localConfig, claude_rate_limit_per_second: parseFloat(e.target.value) || 1 })}
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
      </Card>

      <div className="space-y-3">
        <h2 className="text-lg font-medium">LLM Providers</h2>
        {localConfig.llm.map((p, i) => (
          <ProviderEditor
            key={p.id}
            provider={p}
            onChange={(updated) => {
              const llm = [...localConfig.llm];
              llm[i] = updated;
              setLocalConfig({ ...localConfig, llm });
            }}
            onDelete={() => {
              setLocalConfig({ ...localConfig, llm: localConfig.llm.filter((_, j) => j !== i) });
            }}
          />
        ))}
        <Button variant="secondary" size="sm" onClick={addProvider}>Add Provider</Button>
      </div>
    </div>
  );
}
