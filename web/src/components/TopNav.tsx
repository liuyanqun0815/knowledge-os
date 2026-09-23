import { FormEvent, useState } from "react";
import { NavLink } from "react-router-dom";
import { setAdminToken } from "../api/http";
import { useKb } from "../app/KbContext";
import { KbSwitcher } from "./KbSwitcher";

const navItems = [
  { to: "/knowledge-bases", label: "知识库", requiresGraph: false },
  { to: "/sources", label: "文档", requiresGraph: false },
  { to: "/ask", label: "问答", requiresGraph: false },
  { to: "/wiki", label: "Wiki", requiresGraph: false },
  { to: "/claims", label: "Claim", requiresGraph: false },
  { to: "/graph", label: "图谱", requiresGraph: true },
  { to: "/quarantine", label: "隔离", requiresGraph: false },
] as const;

export function TopNav() {
  const { graphEnabled } = useKb();
  const [token, setToken] = useState("");
  const [tokenSaved, setTokenSaved] = useState(false);

  function handleTokenSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminToken(token.trim());
    setToken("");
    setTokenSaved(true);
  }

  const visibleNav = navItems.filter((item) => !item.requiresGraph || graphEnabled === true);

  return (
    <header className="top-nav">
      <NavLink className="brand" to="/knowledge-bases">
        AKOS 管理后台
      </NavLink>
      <nav aria-label="主导航">
        {visibleNav.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? "active" : undefined)}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="top-nav-actions">
        <KbSwitcher />
        <details className="token-settings">
          <summary>设置</summary>
          <form onSubmit={handleTokenSubmit}>
            <label htmlFor="admin-token">管理员令牌</label>
            <input
              id="admin-token"
              type="password"
              value={token}
              onChange={(event) => {
                setToken(event.target.value);
                setTokenSaved(false);
              }}
              placeholder="输入令牌"
            />
            <button type="submit">保存</button>
            {tokenSaved ? <span role="status">已保存</span> : null}
          </form>
        </details>
      </div>
    </header>
  );
}
