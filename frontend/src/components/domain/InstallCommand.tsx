import { useState } from "react";
import type { McpInstallation } from "../../types";
import { useTranslation } from "../../i18n";

interface InstallCommandProps {
  installation: McpInstallation;
  targetName?: string;
}

export function InstallCommand({ installation, targetName }: InstallCommandProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(installation.data);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-700">{targetName || installation.action_type}</span>
        <button onClick={copy} className="text-xs text-blue-600 hover:text-blue-700">
          {copied ? t("common.buttons.copied") : t("common.buttons.copy")}
        </button>
      </div>
      <pre className="text-sm font-mono text-gray-800 overflow-x-auto whitespace-pre-wrap">{installation.data}</pre>
    </div>
  );
}
