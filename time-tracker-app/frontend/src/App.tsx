import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell/AppShell";
import { TodayPage } from "./pages/Today/TodayPage";
import { WeekPage } from "./pages/Week/WeekPage";
import { MonthPage } from "./pages/Month/MonthPage";
import { ReportsPage } from "./pages/Reports/ReportsPage";

export function App(): ReactElement {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/today" replace />} />
        <Route path="/today" element={<TodayPage />} />
        <Route path="/week" element={<WeekPage />} />
        <Route path="/month" element={<MonthPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Routes>
    </AppShell>
  );
}
