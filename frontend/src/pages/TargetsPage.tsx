import { useState } from "react";
import { useTargets, useCreateTarget } from "../api/targets";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";

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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {targets?.map((t) => (
          <Card key={t.id}>
            <p className="font-medium">{t.name}</p>
            {t.description && <p className="text-sm text-gray-500 mt-1">{t.description}</p>}
          </Card>
        ))}
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
