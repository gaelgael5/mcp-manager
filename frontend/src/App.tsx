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
import { SkillsPage } from "./pages/SkillsPage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/services/:id" element={<ServiceDetailPage />} />
            <Route path="/targets" element={<TargetsPage />} />
            <Route path="/sync" element={<SyncPage />} />
            <Route path="/api-docs" element={<ApiDocsPage />} />
            <Route path="/api-keys" element={<ApiKeysPage />} />
            <Route path="/instances" element={<InstancesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/skills" element={<SkillsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
