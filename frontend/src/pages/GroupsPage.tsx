import { useState } from "react";
import { Link } from "react-router-dom";
import { usePreferenceGroups, useCreateGroup, useDeleteGroup } from "../api/preference-groups";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

export function GroupsPage() {
  const { data: user } = useCurrentUser();
  const { data: groups, isLoading } = usePreferenceGroups();
  const createGroup = useCreateGroup();
  const deleteGroup = useDeleteGroup();
  const [name, setName] = useState("");

  if (!user?.authenticated) {
    return (
      <div className="text-center py-16 text-gray-500">
        Connectez-vous pour acceder aux groupes.
      </div>
    );
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    createGroup.mutate({ name: trimmed }, {
      onSuccess: () => setName(""),
    });
  };

  const handleDelete = (e: React.MouseEvent, groupId: string, groupName: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Supprimer le groupe "${groupName}" ?`)) {
      deleteGroup.mutate(groupId);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Groups</h1>

      <form onSubmit={handleCreate} className="flex items-center gap-3 mb-8">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nom du groupe"
          className="border border-gray-300 rounded-md px-3 py-2 text-sm flex-1 max-w-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <Button type="submit" size="sm" loading={createGroup.isPending}>
          Creer
        </Button>
      </form>

      {isLoading && <p className="text-gray-500">Chargement...</p>}

      {!isLoading && (!groups || groups.length === 0) && (
        <p className="text-gray-500">Aucun groupe. Creez votre premier groupe ci-dessus.</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {groups?.map((group) => (
          <Link key={group.id} to={`/groups/${group.id}`} className="block">
            <Card className="hover:shadow-md transition-shadow h-full">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">{group.name}</h3>
                  {group.description && (
                    <p className="text-sm text-gray-500 mt-1 line-clamp-2">{group.description}</p>
                  )}
                  {!group.is_owner && group.owner_pseudo && (
                    <p className="text-xs text-gray-400 mt-1">par {group.owner_pseudo}</p>
                  )}
                </div>
                {group.is_owner && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={(e) => handleDelete(e, group.id, group.name)}
                    loading={deleteGroup.isPending}
                  >
                    Supprimer
                  </Button>
                )}
              </div>
              <div className="flex gap-2 mt-3">
                <Badge color={group.is_public ? "green" : "gray"}>{group.is_public ? "public" : "prive"}</Badge>
                <Badge color="blue">{group.service_count} service{group.service_count !== 1 ? "s" : ""}</Badge>
                <Badge color="purple">{group.skill_count} skill{group.skill_count !== 1 ? "s" : ""}</Badge>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
