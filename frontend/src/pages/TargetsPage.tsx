import { useState } from "react";
import { useTargets, useCreateTarget, useUpdateTarget } from "../api/targets";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import type { InstallTarget, InstallMode } from "../types";

function ModeEditor({ modes, onChange }: { modes: InstallMode[]; onChange: (m: InstallMode[]) => void }) {
  const [runtime, setRuntime] = useState("");
  const [actionType, setActionType] = useState("cmd");
  const [template, setTemplate] = useState("");

  const handleAdd = () => {
    if (!runtime.trim() || !template.trim()) return;
    onChange([...modes, { runtime: runtime.trim(), action_type: actionType, template: template.trim() }]);
    setRuntime("");
    setTemplate("");
  };

  return (
    <div className="space-y-2">
      {modes.map((m, i) => (
        <div key={i} className="flex items-start gap-2 rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <Badge color="blue">{m.runtime}</Badge>
              <Badge color="gray">{m.action_type}</Badge>
            </div>
            <code className="mt-1 block text-xs text-gray-600 break-all">{m.template}</code>
          </div>
          <button onClick={() => onChange(modes.filter((_, j) => j !== i))} className="text-xs text-gray-400 hover:text-red-500">x</button>
        </div>
      ))}
      <div className="space-y-1 rounded-md border border-dashed border-gray-300 p-2">
        <div className="flex gap-2">
          <input value={runtime} onChange={(e) => setRuntime(e.target.value)} placeholder="runtime (npx, uvx, docker)" className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs" />
          <select value={actionType} onChange={(e) => setActionType(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs">
            <option value="cmd">cmd</option>
            <option value="insert_in_file">insert_in_file</option>
            <option value="docker_run">docker_run</option>
          </select>
        </div>
        <input value={template} onChange={(e) => setTemplate(e.target.value)} placeholder="template: claude mcp add {name} -- npx {package}" className="w-full rounded border border-gray-300 px-2 py-1 text-xs font-mono" onKeyDown={(e) => { if (e.key === "Enter") handleAdd(); }} />
        <p className="text-xs text-gray-400">Placeholders: {"{name}"} {"{package}"} {"{runtime}"} {"{env_flags}"}</p>
        <Button size="sm" variant="secondary" onClick={handleAdd}>Add Mode</Button>
      </div>
    </div>
  );
}

function TargetCard({ target }: { target: InstallTarget }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(target.name);
  const [desc, setDesc] = useState(target.description || "");
  const [modes, setModes] = useState<InstallMode[]>(target.modes || []);
  const updateTarget = useUpdateTarget();

  const handleSave = () => {
    updateTarget.mutate({ id: target.id, name, description: desc, modes }, {
      onSuccess: () => setEditing(false),
    });
  };

  if (!editing) {
    return (
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <p className="font-medium">{target.name}</p>
            {target.description && <p className="text-sm text-gray-500 mt-1">{target.description}</p>}
          </div>
          <button onClick={() => setEditing(true)} className="text-xs text-gray-400 hover:text-gray-600">edit</button>
        </div>
        {target.modes && target.modes.length > 0 ? (
          <div className="mt-3 space-y-1">
            <p className="text-xs text-gray-400 font-medium">Compatible modes:</p>
            {target.modes.map((m, i) => (
              <div key={i} className="flex items-center gap-2">
                <Badge color="blue">{m.runtime}</Badge>
                <Badge color="gray">{m.action_type}</Badge>
                <code className="text-xs text-gray-500 truncate">{m.template}</code>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-yellow-600">No modes configured — using defaults</p>
        )}
      </Card>
    );
  }

  return (
    <Card>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Description</label>
          <input value={desc} onChange={(e) => setDesc(e.target.value)} className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Installation Modes</label>
          <ModeEditor modes={modes} onChange={setModes} />
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} loading={updateTarget.isPending}>Save</Button>
          <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
        </div>
      </div>
    </Card>
  );
}

export function TargetsPage() {
  const { data: targets } = useTargets();
  const createTarget = useCreateTarget();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  const handleCreate = () => {
    if (!name.trim()) return;
    createTarget.mutate({ name: name.trim(), description: desc.trim() || undefined });
    setName("");
    setDesc("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Install Targets</h1>
      <div className="grid grid-cols-1 gap-4">
        {targets?.map((t) => <TargetCard key={t.id} target={t} />)}
      </div>
      <Card title="Add Target">
        <div className="flex gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className="rounded-md border border-gray-300 px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Description</label>
            <input value={desc} onChange={(e) => setDesc(e.target.value)} className="rounded-md border border-gray-300 px-3 py-2 text-sm" />
          </div>
          <Button onClick={handleCreate} loading={createTarget.isPending}>Add</Button>
        </div>
      </Card>
    </div>
  );
}
