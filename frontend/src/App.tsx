import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import { Calculator, History, Settings, Zap } from 'lucide-react';
import Home from './pages/Home';
import HistoryPage from './pages/History';
import SettingsPage from './pages/Settings';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center">
                  <Zap className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-lg font-bold text-gray-900">Math Agent</h1>
                  <p className="text-xs text-gray-500">数学智能体推理系统 v2.0</p>
                </div>
              </div>

              <nav className="flex items-center gap-1">
                <NavLink
                  to="/"
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`
                  }
                >
                  <Calculator className="w-4 h-4" />
                  求解
                </NavLink>
                <NavLink
                  to="/history"
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`
                  }
                >
                  <History className="w-4 h-4" />
                  历史
                </NavLink>
                <NavLink
                  to="/settings"
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`
                  }
                >
                  <Settings className="w-4 h-4" />
                  设置
                </NavLink>
              </nav>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-gray-200 py-4">
          <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
            Math Agent System v2.0 · Powered by Intern-S1 · Multi-Agent Pipeline
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;