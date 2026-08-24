import { useMe } from "../useMe";
import { AdminDashboard } from "./AdminDashboard";
import { ManagerDashboard } from "./ManagerDashboard";
import { StaffDashboard } from "./StaffDashboard";

export function DashboardPage() {
  const { me } = useMe();
  if (!me) return null;
  if (me.user.role === "admin") return <AdminDashboard />;
  if (me.user.role === "manager") return <ManagerDashboard />;
  return <StaffDashboard />;
}
