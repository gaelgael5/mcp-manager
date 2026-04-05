import { useState } from "react";
import Markdown from "react-markdown";
import type { McpSummary } from "../../types";
import { Tabs } from "../ui/Tabs";

export function SummaryView({ summaries }: { summaries: McpSummary[] }) {
  const [culture, setCulture] = useState("en");
  const [collapsed, setCollapsed] = useState(false);
  const tabs = summaries.map((s) => ({ key: s.culture, label: s.culture.toUpperCase() }));
  const active = summaries.find((s) => s.culture === culture);

  if (summaries.length === 0) return <p className="text-sm text-gray-500">No summaries available.</p>;

  return (
    <div>
      <div className="flex items-center justify-between">
        <Tabs tabs={tabs} active={culture} onChange={setCulture} />
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>
      {!collapsed && (
        <div className="mt-3 prose prose-sm prose-gray max-w-none">
          <Markdown>{active?.summary || "Select a language."}</Markdown>
        </div>
      )}
    </div>
  );
}
