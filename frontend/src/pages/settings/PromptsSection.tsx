import { useState, useEffect } from "react";
import { useLanguages } from "../../api/languages";
import {
  usePromptList,
  usePrompt,
  useUpdatePrompt,
  type PromptKind,
} from "../../api/prompts";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";

const KINDS: { value: PromptKind; label: string }[] = [
  { value: "summarize", label: "MCP service summary" },
  { value: "skill_summary", label: "Skill summary" },
  { value: "source_summary", label: "Skill source summary" },
];

export function PromptsSection() {
  const { data: languages = [] } = useLanguages();
  const { data: list = [] } = usePromptList();
  const [kind, setKind] = useState<PromptKind>("summarize");
  const [lang, setLang] = useState<string>("en");
  const { data: prompt } = usePrompt(kind, lang);
  const update = useUpdatePrompt();
  const [draft, setDraft] = useState<string>("");

  useEffect(() => {
    if (prompt) setDraft(prompt.content);
  }, [prompt]);

  const availableLanguages = languages.filter((l) =>
    list.some((p) => p.language === l.code && p.kind === kind && p.exists),
  );

  const hasPlaceholder = draft.includes("{content}");

  return (
    <Card title="Prompts">
      <div className="space-y-3">
        <div className="flex flex-wrap gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gray-600">Kind:</span>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as PromptKind)}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            >
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gray-600">Language:</span>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1 text-sm"
            >
              {availableLanguages.length === 0 && (
                <option value="">(no prompt file)</option>
              )}
              {availableLanguages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </option>
              ))}
            </select>
          </label>
        </div>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={18}
          className="w-full rounded border border-gray-200 bg-white p-3 font-mono text-xs"
          spellCheck={false}
        />
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="primary"
            onClick={() => update.mutate({ kind, language: lang, content: draft })}
            loading={update.isPending}
            disabled={!hasPlaceholder || !lang}
          >
            Save
          </Button>
          {!hasPlaceholder && (
            <span className="text-xs text-red-600">
              The template must contain the {"{content}"} placeholder.
            </span>
          )}
          {update.isSuccess && (
            <span className="text-xs text-green-600">Saved</span>
          )}
          {update.isError && (
            <span className="text-xs text-red-600">
              {(update.error as Error)?.message ?? "Save failed"}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500">
          Prompts are written to <code>backend/prompts/&lt;language&gt;/&lt;kind&gt;.md</code>.
          Changes take effect on the next summary generation.
        </p>
      </div>
    </Card>
  );
}
