import { Outlet, NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/services", label: "Services" },
  { to: "/targets", label: "Targets" },
  { to: "/sync", label: "Sync" },
  { to: "/api-docs", label: "API" },
];

export function MainLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="flex items-center gap-8">
          <span className="font-bold text-lg">MCP Manager</span>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `text-sm ${isActive ? "text-blue-600 font-medium" : "text-gray-600 hover:text-gray-900"}`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
