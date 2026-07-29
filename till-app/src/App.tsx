import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { CartProvider } from "./contexts/CartContext";
import LoginPage from "./pages/LoginPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import TillPage from "./pages/TillPage";

function Gate() {
  const { user, mustChangePassword } = useAuth();

  if (!user) return <LoginPage />;
  if (mustChangePassword) return <ChangePasswordPage />;

  return (
    <CartProvider>
      <TillPage />
    </CartProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
