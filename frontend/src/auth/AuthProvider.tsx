import Keycloak from "keycloak-js";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { config } from "../config";
import { AuthContext } from "./context";

// Module-level singleton — must be created exactly once per page load;
// keycloak-js throws if init() runs twice on the same instance.
const keycloak = new Keycloak({
  url: config.keycloakUrl,
  realm: config.keycloakRealm,
  clientId: config.keycloakClientId,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState<string | undefined>(undefined);
  const [ready, setReady] = useState(false);
  // React 19 StrictMode double-invokes effects in dev; guard against
  // calling keycloak.init() twice on the same instance.
  const initStarted = useRef(false);

  useEffect(() => {
    if (initStarted.current) {
      return;
    }
    initStarted.current = true;

    keycloak.onTokenExpired = () => {
      keycloak
        .updateToken(30)
        .then(() => setToken(keycloak.token))
        .catch(() => keycloak.login());
    };

    keycloak
      .init({ onLoad: "login-required", pkceMethod: "S256" })
      .then((isAuthenticated) => {
        setAuthenticated(isAuthenticated);
        setToken(keycloak.token);
      })
      .finally(() => setReady(true));
  }, []);

  if (!ready) {
    return <p>Loading…</p>;
  }

  return (
    <AuthContext.Provider
      value={{ authenticated, token, logout: () => void keycloak.logout() }}
    >
      {children}
    </AuthContext.Provider>
  );
}
