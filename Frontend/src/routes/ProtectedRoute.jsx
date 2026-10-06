import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import FeedbackPanel from "../components/FeedbackPanel";

function ProtectedRoute() {
  const { status, authError, retryAuth } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <main className="grid min-h-screen place-items-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
      </main>
    );
  }

  if (status === "error") {
    return (
      <main className="mx-auto grid min-h-screen max-w-xl place-items-center px-4">
        <FeedbackPanel
          title="Couldn’t connect to your workspace"
          description={authError}
          tone="error"
          action={
            <button
              type="button"
              onClick={retryAuth}
              className="inline-flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Try again
            </button>
          }
        />
      </main>
    );
  }

  if (status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
