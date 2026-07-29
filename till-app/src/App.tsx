import { useState } from "react";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { CartProvider } from "./contexts/CartContext";
import LoginPage from "./pages/LoginPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import TillPage from "./pages/TillPage";
import TablesGridPage from "./pages/TablesGridPage";
import TableOrderPage from "./pages/TableOrderPage";
import type { AppMode } from "./components/AppHeader";

function MainApp() {
  const [mode, setMode] = useState<AppMode>("quick");
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);

  function handleModeChange(next: AppMode) {
    setSelectedTableId(null);
    setMode(next);
  }

  if (mode === "tables") {
    if (selectedTableId !== null) {
      return <TableOrderPage tableId={selectedTableId} onBack={() => setSelectedTableId(null)} />;
    }
    return (
      <TablesGridPage mode={mode} onModeChange={handleModeChange} onSelectTable={setSelectedTableId} />
    );
  }

  return (
    <CartProvider>
      <TillPage mode={mode} onModeChange={handleModeChange} />
    </CartProvider>
  );
}

function Gate() {
  const { user, mustChangePassword } = useAuth();

  if (!user) return <LoginPage />;
  if (mustChangePassword) return <ChangePasswordPage />;

  return <MainApp />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
