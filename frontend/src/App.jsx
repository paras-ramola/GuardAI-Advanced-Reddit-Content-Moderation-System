import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Analyzer  from './pages/Analyzer.jsx'
import Predict   from './pages/Predict.jsx'

const NAV = [
  { to: '/',         icon: '📊', label: 'Dashboard'      },
  { to: '/analyze',  icon: '🔍', label: 'Live Analyzer'  },
  { to: '/predict',  icon: '⚡', label: 'Quick Predict'  },
]

export default function App() {
  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <nav className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">🛡️</div>
          <span className="logo-text">GuardAI</span>
        </div>

        <div className="sidebar-label">Navigation</div>
        {NAV.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{icon}</span>
            {label}
          </NavLink>
        ))}

        <div className="sidebar-footer">
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
            <span className="status-dot" />
            Model Active
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            DistilBERT · v1.0
          </div>
        </div>
      </nav>

      {/* ── Pages ── */}
      <main className="main-content">
        <Routes>
          <Route path="/"        element={<Dashboard />} />
          <Route path="/analyze" element={<Analyzer />}  />
          <Route path="/predict" element={<Predict />}   />
        </Routes>
      </main>
    </div>
  )
}
