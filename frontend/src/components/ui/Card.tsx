import { useState } from "react";

interface CardProps {
  children: React.ReactNode;
  title?: React.ReactNode;
  className?: string;
  collapsible?: boolean;
}

export function Card({ children, title, className = "", collapsible = false }: CardProps) {
  const [collapsed, setCollapsed] = useState(true);

  if (collapsible && title) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-white shadow-sm ${className}`}>
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          aria-expanded={!collapsed}
          className="flex w-full items-center justify-between border-b border-gray-200 px-4 py-3 font-medium text-left hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-t-lg"
          style={collapsed ? { borderBottomWidth: 0 } : undefined}
        >
          <span>{title}</span>
          <span className="text-gray-400 text-sm">{collapsed ? "▸" : "▾"}</span>
        </button>
        {!collapsed && <div className="p-4">{children}</div>}
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-gray-200 bg-white shadow-sm ${className}`}>
      {title && <div className="border-b border-gray-200 px-4 py-3 font-medium">{title}</div>}
      <div className="p-4">{children}</div>
    </div>
  );
}
