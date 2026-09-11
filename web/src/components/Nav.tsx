import { NavLink } from "react-router-dom";
import { clearTokens } from "../lib/api";

const links = [
  { to: "/today", label: "Today" },
  { to: "/inbox", label: "Inbox" },
  { to: "/brand-brain", label: "Brand Brain" },
];

export default function Nav() {
  return (
    <div className="mb-8 flex items-center justify-between border-b border-black/10 pb-4 dark:border-white/10">
      <div className="flex items-center gap-1">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-black/[0.05] text-ink dark:bg-white/10 dark:text-ink-dark"
                  : "text-muted hover:text-ink dark:text-muted-dark dark:hover:text-ink-dark"
              }`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </div>
      <button
        onClick={() => {
          clearTokens();
          window.location.href = "/login";
        }}
        className="text-sm text-muted hover:text-ink dark:text-muted-dark"
      >
        Sign out
      </button>
    </div>
  );
}
