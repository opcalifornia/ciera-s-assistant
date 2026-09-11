import { Navigate, Route, Routes } from "react-router-dom";
import { getAccessToken } from "./lib/api";
import Login from "./pages/Login";
import Today from "./pages/Today";

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!getAccessToken()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/today"
        element={
          <RequireAuth>
            <Today />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/today" replace />} />
    </Routes>
  );
}
