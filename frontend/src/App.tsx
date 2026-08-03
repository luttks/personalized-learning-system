import { Navigate, Route, Routes } from "react-router-dom";

import { GuestOnly, RequireAuth, RequireRole } from "./auth/RouteGuards";
import { AppShell } from "./components/AppShell";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { DashboardPage } from "./pages/DashboardPage";
import { CourseManagementPage } from "./pages/CourseManagementPage";
import { ExamWorkflowPage } from "./pages/ExamWorkflowPage";
import { LearningProfilePage } from "./pages/LearningProfilePage";
import { MasteryPage } from "./pages/MasteryPage";
import { OperationsPage } from "./pages/OperationsPage";
import { RoadmapPage } from "./pages/RoadmapPage";
import { StudentProfilePage } from "./pages/StudentProfilePage";
import { StudentCatalogPage } from "./pages/StudentCatalogPage";
import { UsersPage } from "./pages/UsersPage";

export default function App() {
  return (
    <Routes>
      <Route element={<GuestOnly />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="exam-workflow" element={<ExamWorkflowPage />} />

          <Route element={<RequireRole allowed={["student"]} />}>
            <Route path="catalog" element={<StudentCatalogPage />} />
            <Route path="student-profile" element={<StudentProfilePage />} />
            <Route path="learning-profile" element={<LearningProfilePage />} />
            <Route path="mastery" element={<MasteryPage />} />
            <Route path="roadmap" element={<RoadmapPage />} />
          </Route>

          <Route element={<RequireRole allowed={["admin"]} />}>
            <Route path="users" element={<UsersPage />} />
            <Route path="operations" element={<OperationsPage />} />
          </Route>

          <Route element={<RequireRole allowed={["teacher", "admin"]} />}>
            <Route path="courses" element={<CourseManagementPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
