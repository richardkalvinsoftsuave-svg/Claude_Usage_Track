import { NavLink, Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-6">
              <span className="font-bold text-lg text-blue-700">
                Claude Usage Tracker
              </span>
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive
                      ? 'text-blue-600 border-b-2 border-blue-600 pb-[13px]'
                      : 'text-gray-600 hover:text-gray-900 pb-[13px]'
                  }`
                }
              >
                Upload
              </NavLink>
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive
                      ? 'text-blue-600 border-b-2 border-blue-600 pb-[13px]'
                      : 'text-gray-600 hover:text-gray-900 pb-[13px]'
                  }`
                }
              >
                Dashboard
              </NavLink>
              <NavLink
                to="/teams"
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors ${
                    isActive
                      ? 'text-blue-600 border-b-2 border-blue-600 pb-[13px]'
                      : 'text-gray-600 hover:text-gray-900 pb-[13px]'
                  }`
                }
              >
                Teams
              </NavLink>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
