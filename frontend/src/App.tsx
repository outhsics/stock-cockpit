import { Navigate, Route, Routes } from "react-router-dom";
import { isLoggedIn } from "./lib/api";
import AppLayout from "./layouts/AppLayout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Portfolio from "./pages/Portfolio";
import Briefing from "./pages/Briefing";
import News from "./pages/News";
import Chat from "./pages/Chat";
import Research from "./pages/Research";
import Congress from "./pages/Congress";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <AppLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="briefing" element={<Briefing />} />
        <Route path="chat" element={<Chat />} />
        <Route path="research" element={<Research />} />
        <Route path="news" element={<News />} />
        <Route path="congress" element={<Congress />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
