import { useState } from "react";
import type { McpParameter } from "../../types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface ParametersBlockProps {
  parameters: McpParameter[];
  onDetect: () => void;
  onAdd: (p: { name: string; description: string; is_required: boolean; is_secret: boolean }) => void;
  onDelete: (id: string) => void;
  detecting: boolean;
  isAdmin?: boolean;
}

export function ParametersBlock({ parameters, onDetect, onAdd, onDelete, detecting, isAdmin = false }: ParametersBlockProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [required, setRequired] = useState(false);
  const [secret, setSecret] = useState(false);

  const handleAdd = () => {
    if (!name.trim()) return;
    onAdd({ name: name.trim(), description: desc.trim(), is_required: required, is_secret: secret });
    setName("");
    setDesc("");
    setRequired(false);
    setSecret(false);
    setAdding(false);
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h3 className="font-medium">Parameters</h3>
        <button onClick={() => setCollapsed(!collapsed)} className="text-xs text-gray-400 hover:text-gray-600">
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>
      {!collapsed && (
        <div className="p-4 space-y-3">
          {parameters.length > 0 ? (
            <div className="space-y-2">
              {parameters.map((p) => (
                <div key={p.id} className="flex items-start justify-between rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <code className="text-sm font-mono font-medium text-gray-800">{p.name}</code>
                      {p.is_required && <Badge color="red">required</Badge>}
                      {p.is_secret && <Badge color="yellow">secret</Badge>}
                      <Badge color="gray">{p.source}</Badge>
                    </div>
                    {p.description && (
                      <p className="mt-1 text-xs text-gray-500">{p.description}</p>
                    )}
                  </div>
                  {isAdmin && <button onClick={() => onDelete(p.id)} className="text-xs text-gray-400 hover:text-red-500 ml-2">x</button>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No parameters identified.</p>
          )}

          {isAdmin && adding ? (
            <div className="space-y-2 rounded-md border border-blue-200 bg-blue-50 p-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="VARIABLE_NAME"
                className="w-full rounded-md border border-gray-300 px-2 py-1 text-sm font-mono"
                autoFocus
              />
              <input
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Description"
                className="w-full rounded-md border border-gray-300 px-2 py-1 text-sm"
              />
              <div className="flex items-center gap-4 text-sm">
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
                  Required
                </label>
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={secret} onChange={(e) => setSecret(e.target.checked)} />
                  Secret
                </label>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={handleAdd}>Add</Button>
                <Button size="sm" variant="secondary" onClick={() => setAdding(false)}>Cancel</Button>
              </div>
            </div>
          ) : isAdmin ? (
            <div className="flex items-center gap-3 pt-1">
              <Button size="sm" onClick={onDetect} loading={detecting}>
                Detect Parameters
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
                Add Manually
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
