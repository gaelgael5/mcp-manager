import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  usePreferenceGroup,
  useUpdateGroup,
  useDeleteGroup,
  useRemoveServiceFromGroup,
  useRemoveSkillFromGroup,
} from "../api/preference-groups";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

export function GroupDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: group, isLoading } = usePreferenceGroup(id!);
  const updateGroup = useUpdateGroup(id!);
  const deleteGroup = useDeleteGroup();
  const removeService = useRemoveServiceFromGroup();
  const removeSkill = useRemoveSkillFromGroup();

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");

  if (isLoading) {
    return <p className="text-gray-500">Chargement...</p>;
  }

  if (!group) {
    return <p className="text-gray-500">Groupe introuvable.</p>;
  }

  const isOwner = group.is_owner;

  const handleStartEdit = () => {
    if (!isOwner) return;
    setEditName(group.name);
    setEditing(true);
  };

  const handleSaveName = () => {
    const trimmed = editName.trim();
    if (!trimmed || trimmed === group.name) {
      setEditing(false);
      return;
    }
    updateGroup.mutate({ name: trimmed }, {
      onSuccess: () => setEditing(false),
    });
  };

  const handleTogglePublic = () => {
    updateGroup.mutate({ is_public: !group.is_public });
  };

  const handleDeleteGroup = () => {
    if (window.confirm(`Supprimer le groupe "${group.name}" ?`)) {
      deleteGroup.mutate(group.id, {
        onSuccess: () => navigate("/groups"),
      });
    }
  };

  return (
    <div>
      <Link to="/groups" className="text-sm text-blue-600 hover:text-blue-700 mb-4 inline-block">
        &larr; Retour aux groupes
      </Link>

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          {editing ? (
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="border border-gray-300 rounded-md px-3 py-2 text-xl font-bold focus:outline-none focus:ring-2 focus:ring-blue-400"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveName();
                  if (e.key === "Escape") setEditing(false);
                }}
              />
              <Button size="sm" onClick={handleSaveName} loading={updateGroup.isPending}>
                Enregistrer
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
                Annuler
              </Button>
            </div>
          ) : (
            <h1
              className={`text-2xl font-bold ${isOwner ? "cursor-pointer hover:text-blue-600 transition-colors" : ""}`}
              onClick={handleStartEdit}
              title={isOwner ? "Cliquer pour modifier" : undefined}
            >
              {group.name}
            </h1>
          )}
          <Badge color={group.is_public ? "green" : "gray"}>{group.is_public ? "public" : "prive"}</Badge>
          {!isOwner && group.owner_pseudo && (
            <span className="text-sm text-gray-400">par {group.owner_pseudo}</span>
          )}
        </div>
        {group.description && (
          <p className="text-gray-500 mt-1">{group.description}</p>
        )}
        {isOwner && (
          <button
            onClick={handleTogglePublic}
            className="text-xs text-blue-600 hover:underline mt-2"
          >
            {group.is_public ? "Rendre prive" : "Rendre public"}
          </button>
        )}
      </div>

      <div className="space-y-6">
        <Card title="MCP Services">
          {group.services.length === 0 ? (
            <p className="text-sm text-gray-400">Aucun service dans ce groupe.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {group.services.map((svc) => (
                <li key={svc.id} className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Link
                      to={`/services/${svc.id}`}
                      className="text-sm font-medium text-blue-600 hover:underline truncate"
                    >
                      {svc.name}
                    </Link>
                    <Badge color="blue">{svc.source_type}</Badge>
                    {svc.category && <Badge color="gray">{svc.category}</Badge>}
                  </div>
                  {isOwner && (
                    <button
                      onClick={() => removeService.mutate({ groupId: group.id, serviceId: svc.id })}
                      className="text-gray-400 hover:text-red-600 text-lg leading-none ml-2 flex-shrink-0"
                      title="Retirer du groupe"
                    >
                      &times;
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Skills">
          {group.skills.length === 0 ? (
            <p className="text-sm text-gray-400">Aucun skill dans ce groupe.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {group.skills.map((skill) => (
                <li key={skill.id} className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Link
                      to={`/skills-catalog/${skill.id}`}
                      className="text-sm font-medium text-blue-600 hover:underline truncate"
                    >
                      {skill.name}
                    </Link>
                    <Badge color="purple">{skill.target_type}</Badge>
                    {skill.category && <Badge color="gray">{skill.category}</Badge>}
                  </div>
                  {isOwner && (
                    <button
                      onClick={() => removeSkill.mutate({ groupId: group.id, skillId: skill.id })}
                      className="text-gray-400 hover:text-red-600 text-lg leading-none ml-2 flex-shrink-0"
                      title="Retirer du groupe"
                    >
                      &times;
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {isOwner && (
        <div className="mt-8">
          <Button variant="danger" onClick={handleDeleteGroup} loading={deleteGroup.isPending}>
            Supprimer ce groupe
          </Button>
        </div>
      )}
    </div>
  );
}
