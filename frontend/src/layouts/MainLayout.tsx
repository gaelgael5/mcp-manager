import { useEffect } from "react";
import { Outlet, NavLink, useSearchParams } from "react-router-dom";
import { useCurrentUser, setToken, clearToken } from "../api/auth";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/services", label: "Services" },
  { to: "/targets", label: "Targets" },
  { to: "/sync", label: "Sync" },
  { to: "/api-docs", label: "API" },
];

export function MainLayout() {
  const { data: user } = useCurrentUser();
  const [searchParams, setSearchParams] = useSearchParams();

  // Capture token from OAuth callback redirect
  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      setToken(token);
      searchParams.delete("token");
      setSearchParams(searchParams, { replace: true });
      window.location.reload();
    }
  }, [searchParams, setSearchParams]);

  const handleLogin = () => {
    window.location.href = "/api/v1/auth/login";
  };

  const handleLogout = () => {
    clearToken();
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3">
        <div className="flex items-center justify-between">
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
            {user?.is_admin && (
              <NavLink to="/api-keys" className={({ isActive }) => `text-sm ${isActive ? "text-blue-600 font-medium" : "text-gray-600 hover:text-gray-900"}`}>
                Keys
              </NavLink>
            )}
          </div>
          <div className="flex items-center gap-3">
            {user?.authenticated ? (
              <>
                {user.picture && <img src={user.picture} alt="" className="w-7 h-7 rounded-full" />}
                <span className="text-sm text-gray-600">{user.name}</span>
                {user.is_admin && <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">admin</span>}
                <button onClick={handleLogout} className="text-xs text-gray-400 hover:text-gray-600">Logout</button>
              </>
            ) : (
              <button onClick={handleLogin} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                Login with Google
              </button>
            )}
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
