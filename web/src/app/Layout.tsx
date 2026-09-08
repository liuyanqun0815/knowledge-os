import { Outlet } from "react-router-dom";
import { TopNav } from "../components/TopNav";

export function Layout() {
  return (
    <div className="app-shell">
      <TopNav />
      <main className="page-content">
        <Outlet />
      </main>
    </div>
  );
}
