import { useState, useRef, useEffect } from "react";
import { useTranslation } from "../../i18n";
import { Button } from "../ui/Button";

interface GroupPickerProps {
  groups: { id: string; name: string }[];
  allGroups: { id: string; name: string }[];
  onAdd: (groupId: string) => void;
  onRemove: (groupId: string) => void;
  onCreate: (name: string) => void;
  loading?: boolean;
}

export function GroupPicker({ groups, allGroups, onAdd, onRemove, onCreate, loading }: GroupPickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
        setNewName("");
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  const associatedIds = new Set(groups.map((g) => g.id));
  const available = allGroups.filter((g) => !associatedIds.has(g.id));

  const handleCreate = () => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    onCreate(trimmed);
    setNewName("");
    setCreating(false);
    setOpen(false);
  };

  return (
    <div ref={wrapperRef} className="relative flex flex-wrap items-center gap-1.5 mt-2">
      {groups.map((g) => (
        <span key={g.id} className="inline-flex items-center gap-1 rounded-full bg-blue-100 text-blue-700 px-2.5 py-0.5 text-xs font-medium">
          {g.name}
          <button
            onClick={() => onRemove(g.id)}
            className="ml-0.5 text-blue-400 hover:text-blue-600"
            aria-label={`Remove ${g.name}`}
          >
            &times;
          </button>
        </span>
      ))}

      <Button
        size="sm"
        variant="secondary"
        onClick={() => setOpen(!open)}
        loading={loading}
        className="!px-2 !py-0.5 !text-xs"
      >
        {t("components.groupPicker.addGroupButton")}
      </Button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 w-56 rounded-md border border-gray-200 bg-white shadow-lg">
          {available.length > 0 && (
            <ul className="max-h-48 overflow-y-auto py-1">
              {available.map((g) => (
                <li key={g.id}>
                  <button
                    onClick={() => {
                      onAdd(g.id);
                      setOpen(false);
                    }}
                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100"
                  >
                    {g.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {available.length === 0 && !creating && (
            <p className="px-3 py-2 text-xs text-gray-400">{t("components.groupPicker.noGroupsAvailable")}</p>
          )}
          <div className="border-t border-gray-100">
            {creating ? (
              <div className="flex items-center gap-1 p-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreate();
                    if (e.key === "Escape") { setCreating(false); setNewName(""); }
                  }}
                  placeholder={t("components.groupPicker.groupNamePlaceholder")}
                  className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs focus:border-blue-500 focus:outline-none"
                  autoFocus
                />
                <Button size="sm" onClick={handleCreate} className="!px-2 !py-0.5 !text-xs">OK</Button>
              </div>
            ) : (
              <button
                onClick={() => setCreating(true)}
                className="w-full text-left px-3 py-2 text-xs text-blue-600 hover:bg-gray-50"
              >
                {t("components.groupPicker.createGroupButton")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
