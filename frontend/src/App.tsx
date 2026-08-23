import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthProvider";
import { ToastProvider } from "./components/ToastProvider";
import { ContactDetailPage } from "./pages/ContactDetailPage";
import { ContactsListPage } from "./pages/ContactsListPage";
import { PipelinePage } from "./pages/PipelinePage";
import { TasksPage } from "./pages/TasksPage";
import { Nav } from "./Nav";

function AppRoutes() {
  return (
    <>
      <Nav />
      <main style={{ flex: 1, minHeight: 0 }}>
        <Routes>
          <Route path="/" element={<Navigate to="/contacts" replace />} />
          <Route path="/contacts" element={<ContactsListPage />} />
          <Route path="/contacts/:contactId" element={<ContactDetailPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/tasks" element={<TasksPage />} />
        </Routes>
      </main>
    </>
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
