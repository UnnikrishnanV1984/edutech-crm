import { useSearchParams } from "react-router-dom";

import { EmptyState } from "../components/EmptyState";
import { useMe } from "../useMe";
import { BrandingTab } from "./BrandingTab";
import { IntegrationsPage } from "./IntegrationsPage";
import { PipelineConfigPage } from "./PipelineConfigPage";
import { SlaPoliciesPage } from "./SlaPoliciesPage";
import { UsersRolesTab } from "./UsersRolesTab";

const TABS = [
  { value: "sla", label: "SLA" },
  { value: "integrations", label: "Integrations" },
  { value: "pipelines", label: "Pipelines" },
  { value: "branding", label: "Branding" },
  { value: "users", label: "Users & roles" },
] as const;

type Tab = (typeof TABS)[number]["value"];

export function ConfigurationsPage() {
  const { me } = useMe();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get("tab") as Tab | null) ?? "sla";

  if (me && me.user.role !== "admin") {
    return (
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "var(--space-6)" }}>
        <EmptyState headline="Admins only" />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 24 }}>
      <h1 style={{ margin: "0 0 4px" }}>Configurations</h1>
      <div style={{ fontSize: "var(--text-sm)", color: "var(--text-muted)", marginBottom: 16 }}>
        Admin only
      </div>

      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid var(--border)", marginBottom: 20 }}>
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            onClick={() => setSearchParams({ tab: tab.value })}
            style={{
              padding: "8px 14px",
              border: "none",
              background: "none",
              cursor: "pointer",
              fontSize: "var(--text-sm)",
              fontWeight: activeTab === tab.value ? "var(--weight-semibold)" : "var(--weight-normal)",
              color: activeTab === tab.value ? "var(--text-h)" : "var(--text-muted)",
              borderBottom: activeTab === tab.value ? "2px solid var(--accent)" : "2px solid transparent",
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "sla" && <SlaPoliciesPage />}
      {activeTab === "integrations" && <IntegrationsPage />}
      {activeTab === "pipelines" && <PipelineConfigPage />}
      {activeTab === "branding" && <BrandingTab />}
      {activeTab === "users" && <UsersRolesTab />}
    </div>
  );
}
