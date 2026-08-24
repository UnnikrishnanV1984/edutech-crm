import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { ToastProvider } from "./components/ToastProvider";
import { ContactDetailPage } from "./pages/ContactDetailPage";
import { ContactsListPage } from "./pages/ContactsListPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EscalationsPage } from "./pages/EscalationsPage";
import { FollowUpFlagsPage } from "./pages/FollowUpFlagsPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { PipelineConfigPage } from "./pages/PipelineConfigPage";
import { PipelinePage } from "./pages/PipelinePage";
import { SlaPoliciesPage } from "./pages/SlaPoliciesPage";
import { TasksPage } from "./pages/TasksPage";
import { WorkflowRulesPage } from "./pages/WorkflowRulesPage";
import { Sidebar } from "./Sidebar";

function AppRoutes() {
  return (
    <div style={{ display: "flex", height: "100svh" }}>
      <Sidebar />
      <main style={{ flex: 1, minWidth: 0, overflowY: "auto" }}>
        <Routes>
          <Route path="/" element={<Navigate to="/contacts" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/contacts" element={<ContactsListPage />} />
          <Route path="/contacts/:contactId" element={<ContactDetailPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/escalations" element={<EscalationsPage />} />
          <Route path="/follow-ups" element={<FollowUpFlagsPage />} />
          <Route path="/sla-policies" element={<SlaPoliciesPage />} />
          <Route path="/pipeline-config" element={<PipelineConfigPage />} />
          <Route path="/workflow-rules" element={<WorkflowRulesPage />} />
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
