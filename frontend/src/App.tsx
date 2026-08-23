import { AuthProvider } from "./auth/AuthProvider";
import { MeShell } from "./MeShell";

function App() {
  return (
    <AuthProvider>
      <MeShell />
    </AuthProvider>
  );
}

export default App;
