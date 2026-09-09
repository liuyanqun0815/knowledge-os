import { FormEvent, useState } from "react";
import { NavLink } from "react-router-dom";
import { setAdminToken } from "../api/http";
import { KbSwitcher } from "./KbSwitcher";

const navItems = [
  { to: "/knowledge-bases", label: "知识库" },
  { to: "/sources", label: "文档" },
  { to: "/ask", label: "问答" },
  { to: "/claims", label: "Claim" },
  { to: "/quarantine", label: "隔离" },
];

export function TopNav() {
  const [token, setToken] = useState("");
  const [tokenSaved, setTokenSaved] = useState(false);

  function handleTokenSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminToken(token.trim());
    setToken("");
    setTokenSaved(true);
  }

  return (
    <header className="top-nav">
      <NavLink className="brand" to="/knowledge-bases">
        AKOS 管理后台
      </NavLink>
      <nav aria-label="主导航">
        {navItems.map((item) => (
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
