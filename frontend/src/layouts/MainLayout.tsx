import { useEffect } from "react";
import { Outlet, NavLink, useSearchParams, Link } from "react-router-dom";
import { useCurrentUser, setToken, clearToken } from "../api/auth";
import { useTranslation } from "../i18n";

const publicLinks = [
  { to: "/", labelKey: "navigation.home" },
  { to: "/dashboard", labelKey: "navigation.dashboard" },
  { to: "/services", labelKey: "navigation.services" },
  { to: "/skills-catalog", labelKey: "navigation.skills" },
  { to: "/groups", labelKey: "navigation.groups" },
  { to: "/targets", labelKey: "navigation.targets" },
  { to: "/api-docs", labelKey: "navigation.api" },
];

const adminLinks = [
  { to: "/sync", labelKey: "navigation.sync" },
  { to: "/skills", labelKey: "navigation.skillSources" },
  { to: "/api-keys", labelKey: "navigation.apiKeys" },
  { to: "/instances", labelKey: "navigation.community" },
  { to: "/settings", labelKey: "navigation.settings" },
];

export function MainLayout() {
  const { data: user } = useCurrentUser();
  const { t } = useTranslation();
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
            <span className="font-bold text-lg">{t("common.appName")}</span>
            {publicLinks.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `text-sm ${isActive ? "text-blue-600 font-medium" : "text-gray-600 hover:text-gray-900"}`
                }
              >
                {t(l.labelKey)}
              </NavLink>
            ))}
            {user?.is_admin && adminLinks.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `text-sm ${isActive ? "text-blue-600 font-medium" : "text-gray-600 hover:text-gray-900"}`
                }
              >
                {t(l.labelKey)}
              </NavLink>
            ))}
          </div>
          <div className="flex items-center gap-3">
            {user?.authenticated ? (
              <>
                <Link to="/profile" className="flex items-center gap-2 hover:opacity-80">
                  <img src={user.avatar_url || user.picture || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name || "?")}&size=28&background=random`} alt="" className="w-7 h-7 rounded-full" />
                  <span className="text-sm text-gray-600">{user.pseudo || user.name}</span>
                </Link>
                {user.is_admin && <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{t("common.status.admin")}</span>}
                <button onClick={handleLogout} className="text-xs text-gray-400 hover:text-gray-600">{t("common.buttons.logout")}</button>
              </>
            ) : (
              <button onClick={handleLogin} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                {t("common.buttons.loginGoogle")}
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
