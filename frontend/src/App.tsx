import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MainLayout } from "./layouts/MainLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { ServicesPage } from "./pages/ServicesPage";
import { ServiceDetailPage } from "./pages/ServiceDetailPage";
import { TargetsPage } from "./pages/TargetsPage";
import { SyncPage } from "./pages/SyncPage";
import { ApiDocsPage } from "./pages/ApiDocsPage";
import { ApiKeysPage } from "./pages/ApiKeysPage";
import { InstancesPage } from "./pages/InstancesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { GroupsPage } from "./pages/GroupsPage";
import { GroupDetailPage } from "./pages/GroupDetailPage";
import { ProfilePage } from "./pages/ProfilePage";
import LandingPage from "./pages/LandingPage";
import { useCurrentUser } from "./api/auth";
import { TranslationProvider, getDictionary } from "./i18n";

const queryClient = new QueryClient();

function AppRoutes() {
  const { data: user } = useCurrentUser();
  const lang = user?.language || "en";
  const dict = getDictionary(lang);

  return (
    <TranslationProvider value={dict}>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/services" element={<ServicesPage />} />
          <Route path="/services/:id" element={<ServiceDetailPage />} />
          <Route path="/targets" element={<TargetsPage />} />
          <Route path="/sync" element={<SyncPage />} />
          <Route path="/api-docs" element={<ApiDocsPage />} />
          <Route path="/api-keys" element={<ApiKeysPage />} />
          <Route path="/instances" element={<InstancesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/groups" element={<GroupsPage />} />
          <Route path="/groups/:id" element={<GroupDetailPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </TranslationProvider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
