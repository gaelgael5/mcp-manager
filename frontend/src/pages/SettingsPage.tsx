import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { LanguagesSection } from "./settings/LanguagesSection";
import { PromptsSection } from "./settings/PromptsSection";

interface LLMProvider {
  id: number;
  type: string;
  image?: string;
  args: Record<string, string>;
}

type ConcurrencyMap = Record<string, Record<string, number>>;

interface LLMConfig {
  llm: LLMProvider[];
  concurrency?: ConcurrencyMap;
}

const CONCURRENCY_PIPELINES: { key: string; label: string }[] = [
  { key: "mcp", label: "MCP" },
  { key: "skill_sources", label: "Skill Sources" },
  { key: "skills", label: "Skills" },
];

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

interface DockerImageStatusInfo {
  image_name: string;
  tag: string;
  image_ref: string;
  exists: boolean;
}

interface BuildState {
  status: string;
  logs: string;
  image_ref: string;
}

function DockerImageStatus({ imageName }: { imageName: string | undefined }) {
  const [showLogs, setShowLogs] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data: status } = useQuery({
    queryKey: ["settings", "docker-image-status", imageName],
    queryFn: () => apiFetch<DockerImageStatusInfo>(`/settings/docker-image-status/${imageName}`),
    enabled: !!imageName,
    refetchInterval: 5000,
  });

  const { data: buildState } = useQuery({
    queryKey: ["settings", "docker-build-status", imageName],
    queryFn: () => apiFetch<BuildState>(`/settings/docker-build-status/${imageName}`),
    enabled: !!imageName && showLogs,
    refetchInterval: showLogs ? 2000 : false,
  });

  const qc = useQueryClient();
  const build = useMutation({
    mutationFn: () => apiFetch<BuildState>(`/settings/docker-build/${imageName}`, { method: "POST" }),
    onSuccess: () => {
      setShowLogs(true);
      setTimeout(() => qc.invalidateQueries({ queryKey: ["settings", "docker-image-status"] }), 3000);
    },
  });

  const building = buildState?.status === "building";

  if (!imageName || !status) return null;

  return (
    <>
      <div className="flex items-center gap-2">
        <Badge color={status.exists ? "green" : "red"}>
          {status.exists ? status.image_ref : "not built"}
        </Badge>
        <Button size="sm" variant="secondary" onClick={() => { build.mutate(); }} loading={build.isPending || building}>
          {status.exists ? "Rebuild" : "Build"}
        </Button>
        {buildState && buildState.status !== "idle" && (
          <button onClick={() => setShowLogs(true)} className="text-xs text-blue-600 hover:underline">
            logs
          </button>
        )}
      </div>

      {showLogs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg shadow-xl w-[700px] max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <div className="flex items-center gap-2">
                <span className="font-medium">Build Logs</span>
                <Badge color={building ? "yellow" : buildState?.status === "done" ? "green" : buildState?.status === "error" ? "red" : "gray"}>
                  {buildState?.status || "idle"}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(buildState?.logs || "");
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className="text-xs text-blue-600 hover:text-blue-700 px-2 py-1 border rounded"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
                <button onClick={() => setShowLogs(false)} className="text-gray-400 hover:text-gray-600 text-lg px-2">
                  &times;
                </button>
              </div>
            </div>
            <pre className="flex-1 overflow-auto p-4 text-xs font-mono bg-gray-900 text-green-400 whitespace-pre-wrap">
              {buildState?.logs || "No logs yet..."}
              {building && <span className="animate-pulse">_</span>}
            </pre>
          </div>
        </div>
      )}
    </>
  );
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
  const [argsText, setArgsText] = useState(JSON.stringify(provider.args, null, 2));
  const [argsValid, setArgsValid] = useState(true);

  // Sync argsText when provider.args changes externally (type change, image change, reset)
  useEffect(() => {
    setArgsText(JSON.stringify(provider.args, null, 2));
    setArgsValid(true);
  }, [JSON.stringify(provider.args)]);

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
              <div className="flex items-center gap-2">
                <select
                  value={provider.image || ""}
                  onChange={(e) => handleImageChange(e.target.value)}
                  className="flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
                >
                  {dockerImages?.map((img) => (
                    <option key={img.name} value={img.name}>{img.name}</option>
                  ))}
                </select>
                <DockerImageStatus imageName={provider.image} />
              </div>
            </div>
          )}
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs text-gray-500">Args (JSON)</label>
            <button
              onClick={() => {
                const img = dockerImages?.find((i) => i.name === provider.image);
                if (img) {
                  onChange({ ...provider, args: { ...img.default_args } });
                } else if (provider.type === "ollama") {
                  onChange({ ...provider, args: { url: "http://192.168.10.80:11434", model: "llama3.1:8b" } });
                }
              }}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              reset
            </button>
          </div>
          <textarea
            value={argsText}
            onChange={(e) => {
              setArgsText(e.target.value);
              try {
                const parsed = JSON.parse(e.target.value);
                onChange({ ...provider, args: parsed });
                setArgsValid(true);
              } catch {
                setArgsValid(false);
              }
            }}
            className={`w-full rounded border px-2 py-1 text-xs font-mono h-20 ${argsValid ? "border-gray-300" : "border-red-400 bg-red-50"}`}
          />
          {!argsValid && <p className="text-xs text-red-500 mt-1">Invalid JSON</p>}
        </div>
      </div>
    </Card>
  );
}

interface EnvKey {
  name: string;
  default: string;
  current: string;
  pattern: string;
}

function useEnvKeys() {
  return useQuery({
    queryKey: ["settings", "env-keys"],
    queryFn: () => apiFetch<EnvKey[]>("/settings/env-keys"),
  });
}

function useDockerRunCmd(imageName: string | undefined, providerId: number) {
  return useQuery({
    queryKey: ["settings", "docker-run-cmd", imageName, providerId],
    queryFn: () => apiFetch<{ cmd: string }>(`/settings/docker-run-cmd/${imageName}?provider_id=${providerId}`),
    enabled: !!imageName,
  });
}

function EnvKeysBlock() {
  const { data: envKeys } = useEnvKeys();
  const [localKeys, setLocalKeys] = useState<Record<string, string>>({});
  const [initialized, setInitialized] = useState(false);
  const qc = useQueryClient();

  useEffect(() => {
    if (envKeys && !initialized) {
      const kv: Record<string, string> = {};
      envKeys.forEach((k) => { kv[k.name] = k.current; });
      setLocalKeys(kv);
      setInitialized(true);
    }
  }, [envKeys, initialized]);

  const saveKeys = useMutation({
    mutationFn: (keys: Record<string, string>) =>
      apiFetch<{ status: string }>("/settings/env-keys", {
        method: "PUT",
        body: JSON.stringify({ keys }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings", "env-keys"] });
      qc.invalidateQueries({ queryKey: ["settings", "docker-run-cmd"] });
    },
  });

  if (!envKeys || envKeys.length === 0) return null;

  return (
    <Card title="Environment Keys" collapsible>
      <div className="space-y-3">
        {envKeys.map((k) => (
          <div key={k.name} className="flex items-center gap-2">
            <label className="w-48 text-xs font-mono text-gray-600 truncate">{k.name}</label>
            <input
              type={k.name.includes("KEY") || k.name.includes("SECRET") ? "password" : "text"}
              value={localKeys[k.name] || ""}
              onChange={(e) => setLocalKeys({ ...localKeys, [k.name]: e.target.value })}
              className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs font-mono"
              placeholder={k.pattern}
            />
            <button
              onClick={() => setLocalKeys({ ...localKeys, [k.name]: k.default })}
              className="text-xs text-gray-400 hover:text-gray-600"
              title={`Reset to default: ${k.default || "(empty)"}`}
            >
              reset
            </button>
          </div>
        ))}
        <Button size="sm" onClick={() => saveKeys.mutate(localKeys)} loading={saveKeys.isPending}>
          {saveKeys.isSuccess ? "Saved!" : "Save Keys"}
        </Button>
      </div>
    </Card>
  );
}

interface AuthFile {
  key: string;
  label: string;
  path: string;
  exists: boolean;
  content: string;
}

function AuthFilesBlock() {
  const { data: authFiles } = useQuery({
    queryKey: ["settings", "auth-files"],
    queryFn: () => apiFetch<AuthFile[]>("/settings/auth-files"),
  });
  const [localContent, setLocalContent] = useState<Record<string, string>>({});
  const [initialized, setInitialized] = useState(false);
  const qc = useQueryClient();

  useEffect(() => {
    if (authFiles && !initialized) {
      const kv: Record<string, string> = {};
      authFiles.forEach((f) => { kv[f.key] = f.content; });
      setLocalContent(kv);
      setInitialized(true);
    }
  }, [authFiles, initialized]);

  const save = useMutation({
    mutationFn: (args: { key: string; content: string }) =>
      apiFetch<{ status: string; message?: string }>("/settings/auth-files", {
        method: "PUT",
        body: JSON.stringify(args),
      }),
    onSuccess: (data) => {
      if (data.status === "error") {
        alert(data.message);
      }
      qc.invalidateQueries({ queryKey: ["settings", "auth-files"] });
    },
  });

  if (!authFiles || authFiles.length === 0) return null;

  return (
    <Card title="Auth Files" collapsible>
      <div className="space-y-4">
        {authFiles.map((f) => (
          <div key={f.key}>
            <div className="flex items-center gap-2 mb-1">
              <label className="text-xs font-mono text-gray-600">{f.label}</label>
              <Badge color={f.exists ? "green" : "red"}>{f.exists ? f.path : "missing"}</Badge>
            </div>
            <textarea
              value={localContent[f.key] || ""}
              onChange={(e) => setLocalContent({ ...localContent, [f.key]: e.target.value })}
              className="w-full rounded border border-gray-300 px-2 py-1 text-xs font-mono h-32"
              placeholder={`Paste ${f.label} content here...`}
            />
            <Button
              size="sm"
              className="mt-1"
              onClick={() => save.mutate({ key: f.key, content: localContent[f.key] || "" })}
              loading={save.isPending}
            >
              {save.isSuccess && save.variables?.key === f.key ? "Saved!" : `Save ${f.label}`}
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}

interface ApiTokenInfo {
  id: string;
  domain: string;
  token_prefix: string;
  rate_limit_per_min: number;
  created_at: string | null;
}

function ApiTokensBlock() {
  const { data: tokens } = useQuery({
    queryKey: ["settings", "api-tokens"],
    queryFn: () => apiFetch<ApiTokenInfo[]>("/settings/api-tokens"),
  });
  const qc = useQueryClient();
  const [domain, setDomain] = useState("github.com");
  const [token, setToken] = useState("");
  const [rateLimit, setRateLimit] = useState(60);

  const addToken = useMutation({
    mutationFn: (body: { domain: string; token: string; rate_limit_per_min: number }) =>
      apiFetch<{ status: string }>("/settings/api-tokens", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      setToken("");
      qc.invalidateQueries({ queryKey: ["settings", "api-tokens"] });
    },
  });

  const deleteToken = useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ status: string }>(`/settings/api-tokens/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "api-tokens"] }),
  });

  return (
    <Card title="API Tokens (Rate-Limited Pool)" collapsible>
      <div className="space-y-3">
        {tokens && tokens.length > 0 && (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-1 pr-2">Domain</th>
                <th className="py-1 pr-2">Token</th>
                <th className="py-1 pr-2">Rate/min</th>
                <th className="py-1"></th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} className="border-b border-gray-100">
                  <td className="py-1 pr-2 font-mono">{t.domain}</td>
                  <td className="py-1 pr-2 font-mono text-gray-400">{t.token_prefix}</td>
                  <td className="py-1 pr-2">{t.rate_limit_per_min}</td>
                  <td className="py-1">
                    <button
                      onClick={() => deleteToken.mutate(t.id)}
                      className="text-red-400 hover:text-red-600"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex gap-2 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Domain</label>
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1 text-xs font-mono w-36"
              placeholder="github.com"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-0.5">Token</label>
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="w-full rounded border border-gray-300 px-2 py-1 text-xs font-mono"
              placeholder="ghp_..."
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">Rate/min</label>
            <input
              type="number"
              value={rateLimit}
              onChange={(e) => setRateLimit(parseInt(e.target.value) || 60)}
              className="rounded border border-gray-300 px-2 py-1 text-xs w-16"
            />
          </div>
          <Button
            size="sm"
            onClick={() => addToken.mutate({ domain, token, rate_limit_per_min: rateLimit })}
            loading={addToken.isPending}
            disabled={!token.trim()}
          >
            Add
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ConcurrencyBlock({
  localConfig,
  setLocalConfig,
}: {
  localConfig: LLMConfig;
  setLocalConfig: (c: LLMConfig) => void;
}) {
  const dockerProviders = localConfig.llm.filter((p) => p.type === "docker");
  const concurrency: ConcurrencyMap = localConfig.concurrency || {};

  const getCount = (pipeline: string, providerId: number): number => {
    return concurrency[pipeline]?.[String(providerId)] ?? 1;
  };

  const setCount = (pipeline: string, providerId: number, count: number) => {
    const next: ConcurrencyMap = { ...concurrency };
    next[pipeline] = { ...(next[pipeline] || {}) };
    next[pipeline][String(providerId)] = Math.max(0, count);
    setLocalConfig({ ...localConfig, concurrency: next });
  };

  return (
    <Card title="Concurrency" collapsible>
      {dockerProviders.length === 0 ? (
        <p className="text-sm text-gray-500">
          No docker providers configured. Add one in LLM Providers below to enable per-pipeline concurrency.
        </p>
      ) : (
        <div className="space-y-5">
          {CONCURRENCY_PIPELINES.map((p) => (
            <div key={p.key}>
              <div className="text-sm font-medium mb-2">{p.label}</div>
              <div className="space-y-2">
                {dockerProviders.map((dp) => (
                  <div key={dp.id} className="flex items-center gap-3">
                    <Badge color="purple">{dp.image || "docker"}</Badge>
                    <span className="text-xs text-gray-500">Provider #{dp.id}</span>
                    <input
                      type="number"
                      min={0}
                      max={20}
                      value={getCount(p.key, dp.id)}
                      onChange={(e) => setCount(p.key, dp.id, parseInt(e.target.value) || 0)}
                      className="w-20 rounded border border-gray-300 px-2 py-1 text-sm"
                    />
                    <span className="text-xs text-gray-400">instances</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function DockerRunPreview({ imageName, providerId }: { imageName: string | undefined; providerId: number }) {
  const { data } = useDockerRunCmd(imageName, providerId);
  if (!imageName || !data?.cmd) return null;
  return (
    <div className="mt-2">
      <label className="block text-xs text-gray-500 mb-1">Launch command</label>
      <pre className="text-xs font-mono bg-gray-50 border rounded p-2 overflow-x-auto whitespace-pre-wrap">{data.cmd}</pre>
    </div>
  );
}

export function SettingsPage() {
  const { data: user } = useCurrentUser();
  const { data: config } = useLLMConfig();
  const saveConfig = useSaveLLMConfig();

  const [localConfig, setLocalConfig] = useState<LLMConfig | null>(null);

  useEffect(() => {
    if (config && !localConfig) {
      setLocalConfig({ llm: config.llm, concurrency: config.concurrency });
    }
  }, [config, localConfig]);

  if (!user?.is_admin) {
    return <p className="text-gray-500">Admin access required.</p>;
  }

  if (!localConfig) {
    return <p className="text-gray-500">Loading...</p>;
  }

  const handleSave = () => {
    if (!localConfig) return;
    saveConfig.mutate(localConfig, {
      onSuccess: () => alert("Config saved!"),
      onError: (err) => alert(`Save failed: ${err}`),
    });
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

      <LanguagesSection />

      <PromptsSection />

      <EnvKeysBlock />

      <AuthFilesBlock />

      <ApiTokensBlock />

      <ConcurrencyBlock localConfig={localConfig} setLocalConfig={setLocalConfig} />

      <Card title="LLM Providers" collapsible>
        <div className="space-y-3">
          {localConfig.llm.map((p, i) => (
            <div key={p.id}>
              <ProviderEditor
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
              {p.type === "docker" && <DockerRunPreview imageName={p.image} providerId={p.id} />}
            </div>
          ))}
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={addProvider}>Add Provider</Button>
            <TestLLMButton />
          </div>
        </div>
      </Card>
    </div>
  );
}

interface TestResult {
  id: number;
  type: string;
  status: string;
  response?: string;
  message?: string;
  elapsed_seconds?: number;
}

function TestLLMButton() {
  const [results, setResults] = useState<TestResult[] | null>(null);
  const test = useMutation({
    mutationFn: () => apiFetch<{ results: TestResult[] }>("/settings/llm-test", { method: "POST" }),
    onSuccess: (data) => setResults(data.results),
  });

  return (
    <>
      <Button size="sm" onClick={() => test.mutate()} loading={test.isPending}>
        Test Providers
      </Button>
      {results && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg shadow-xl w-[500px] max-h-[60vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="font-medium">LLM Provider Tests</span>
              <button onClick={() => setResults(null)} className="text-gray-400 hover:text-gray-600 text-lg px-2">&times;</button>
            </div>
            <div className="p-4 space-y-3 overflow-auto">
              {results.map((r) => (
                <div key={r.id} className="rounded border p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge color={r.type === "ollama" ? "blue" : "purple"}>{r.type}</Badge>
                    <span className="text-sm font-medium">Provider #{r.id}</span>
                    <Badge color={r.status === "ok" ? "green" : "red"}>{r.status}</Badge>
                    {r.elapsed_seconds != null && <span className="text-xs text-gray-400">{r.elapsed_seconds}s</span>}
                  </div>
                  {r.response && <pre className="text-xs font-mono text-gray-600 mt-1">{r.response}</pre>}
                  {r.message && <pre className="text-xs font-mono text-red-500 mt-1">{r.message}</pre>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
