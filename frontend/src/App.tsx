import { Navigate, Route, Routes } from "react-router-dom";

import { GuestOnly, RequireAuth, RequireRole } from "./auth/RouteGuards";
import { AppShell } from "./components/AppShell";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { DashboardPage } from "./pages/DashboardPage";
import { CourseManagementPage } from "./pages/CourseManagementPage";
import { PersonalizedLearningPage } from "./pages/PersonalizedLearningPage";
import { RoadmapPage } from "./pages/RoadmapPage";
import { StudentProfilePage } from "./pages/StudentProfilePage";
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

          <Route element={<RequireRole allowed={["student"]} />}>
            <Route path="student-profile" element={<StudentProfilePage />} />
            <Route path="personalized/onboarding" element={<PersonalizedLearningPage mode="onboarding" />} />
            <Route path="personalized/post-exam" element={<PersonalizedLearningPage mode="post_exam" />} />
            <Route path="roadmap" element={<RoadmapPage />} />
          </Route>

          <Route element={<RequireRole allowed={["admin"]} />}>
            <Route path="users" element={<UsersPage />} />
          </Route>

          <Route element={<RequireRole allowed={["student", "admin"]} />}>
            <Route path="courses" element={<CourseManagementPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
