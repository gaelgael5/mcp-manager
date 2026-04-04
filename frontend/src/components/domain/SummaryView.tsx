import { useState } from "react";
import type { McpSummary } from "../../types";
import { Tabs } from "../ui/Tabs";

export function SummaryView({ summaries }: { summaries: McpSummary[] }) {
  const [culture, setCulture] = useState("en");
  const tabs = summaries.map((s) => ({ key: s.culture, label: s.culture.toUpperCase() }));
  const active = summaries.find((s) => s.culture === culture);

  if (summaries.length === 0) return <p className="text-sm text-gray-500">No summaries available.</p>;

  return (
    <div>
      <Tabs tabs={tabs} active={culture} onChange={setCulture} />
      <div className="mt-3 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
        {active?.summary || "Select a language."}
      </div>
    </div>
  );
}
