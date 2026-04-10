import { useLanguages, useUpdateLanguage } from "../../api/languages";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

export function LanguagesSection() {
  const { data: languages = [] } = useLanguages();
  const updateLang = useUpdateLanguage();

  return (
    <Card title="Languages">
      <div className="space-y-2">
        {languages.map((lang) => (
          <div
            key={lang.code}
            className="flex items-center justify-between rounded border border-gray-100 bg-gray-50 px-3 py-2"
          >
            <div className="flex items-center gap-3">
              <code className="text-xs text-gray-500 w-8">{lang.code}</code>
              <span className="text-sm">{lang.name}</span>
              {lang.is_active && <Badge color="green">active</Badge>}
            </div>
            <Button
              size="sm"
              variant={lang.is_active ? "secondary" : "primary"}
              onClick={() =>
                updateLang.mutate({
                  code: lang.code,
                  patch: { is_active: !lang.is_active },
                })
              }
              loading={updateLang.isPending}
            >
              {lang.is_active ? "Deactivate" : "Activate"}
            </Button>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-500">
        Activating a language requires the three prompt files
        (<code>summarize</code>, <code>skill_summary</code>, <code>source_summary</code>) to exist
        under <code>backend/prompts/&lt;code&gt;/</code>.
      </p>
      {updateLang.isError && (
        <p className="mt-2 text-xs text-red-600">
          {(updateLang.error as Error)?.message ?? "Failed to update language"}
        </p>
      )}
    </Card>
  );
}
