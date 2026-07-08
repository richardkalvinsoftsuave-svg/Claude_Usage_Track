import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import UserDetailPage from './pages/UserDetailPage';
import TeamsPage from './pages/TeamsPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<UploadPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/dashboard/user/:name" element={<UserDetailPage />} />
          <Route path="/teams" element={<TeamsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
