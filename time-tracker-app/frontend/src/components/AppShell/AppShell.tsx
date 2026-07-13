import type { ReactElement, ReactNode } from "react";
import { NavLink } from "react-router-dom";
import styles from "./AppShell.module.css";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  disabled?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/today", label: "Today", icon: "⏱" },
  { to: "/week", label: "Week", icon: "📅" },
  { to: "/month", label: "Month", icon: "🗓" },
  { to: "/reports", label: "Reports", icon: "📊", disabled: true },
  { to: "/settings", label: "Settings", icon: "⚙", disabled: true },
];

interface AppShellProps {
  children: ReactNode;
}

/** Persistent left nav rail + centered content column (`design/DESIGN_SYSTEM.md` §2). Reports and
 * Settings are disabled placeholders reserved for later phases. */
export function AppShell({ children }: AppShellProps): ReactElement {
  return (
    <div className={styles.shell}>
      <nav className={styles.navRail} aria-label="Primary">
        {NAV_ITEMS.map((item) =>
          item.disabled ? (
            <span key={item.to} className={styles.navItemDisabled} aria-disabled="true">
              <span className={styles.icon} aria-hidden="true">
                {item.icon}
              </span>
              <span className={styles.label}>{item.label}</span>
            </span>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `${styles.navItem} ${isActive ? styles.navItemActive : ""}`}
            >
              <span className={styles.icon} aria-hidden="true">
                {item.icon}
              </span>
              <span className={styles.label}>{item.label}</span>
            </NavLink>
          ),
        )}
      </nav>
      <main className={styles.content}>
        <div className={styles.contentInner}>{children}</div>
      </main>
    </div>
  );
}
