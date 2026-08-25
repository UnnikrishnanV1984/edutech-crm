import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { ApplyBranding } from "./branding/ApplyBranding";
import { ToastProvider } from "./components/ToastProvider";
import { ConfigurationsPage } from "./pages/ConfigurationsPage";
import { ContactDetailPage } from "./pages/ContactDetailPage";
import { ContactsListPage } from "./pages/ContactsListPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EscalationsPage } from "./pages/EscalationsPage";
import { FollowUpFlagsPage } from "./pages/FollowUpFlagsPage";
import { PipelinePage } from "./pages/PipelinePage";
import { TasksPage } from "./pages/TasksPage";
import { WorkflowRulesPage } from "./pages/WorkflowRulesPage";
import { Sidebar } from "./Sidebar";

function AppRoutes() {
  return (
    <div style={{ display: "flex", height: "100svh" }}>
      <ApplyBranding />
      <Sidebar />
      <main style={{ flex: 1, minWidth: 0, overflowY: "auto" }}>
        <Routes>
          <Route path="/" element={<Navigate to="/contacts" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/contacts" element={<ContactsListPage />} />
          <Route path="/contacts/:contactId" element={<ContactDetailPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/escalations" element={<EscalationsPage />} />
          <Route path="/follow-ups" element={<FollowUpFlagsPage />} />
          <Route path="/workflow-rules" element={<WorkflowRulesPage />} />
          <Route path="/configurations" element={<ConfigurationsPage />} />
          {/* Old standalone Admin routes — one Configurations shell with
              tabs replaces them (OPENFUNNEL_REBRAND_PLAN.md Phase 7b). */}
          <Route path="/sla-policies" element={<Navigate to="/configurations?tab=sla" replace />} />
          <Route
            path="/integrations"
            element={<Navigate to="/configurations?tab=integrations" replace />}
          />
          <Route
            path="/pipeline-config"
            element={<Navigate to="/configurations?tab=pipelines" replace />}
          />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}

export default App;
