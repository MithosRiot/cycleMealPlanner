import { useQuery } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { fetchHealth } from './api'
import SettingsPage from './SettingsPage'

const navigation = [
  ['Dashboard', '/'],
  ['Recipes', '/recipes'],
  ['Meals', '/meals'],
  ['Meal Plan', '/meal-plan'],
  ['Inventory', '/inventory'],
  ['Shopping', '/shopping'],
  ['Leftovers', '/leftovers'],
  ['History', '/history'],
  ['Settings', '/settings'],
] as const

function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="page-card">
      <p className="eyebrow">Cycle Meal Planner</p>
      <h1>{title}</h1>
      <p>This section is ready for its Milestone implementation.</p>
    </section>
  )
}

function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: 1,
    refetchInterval: 30_000,
  })

  const backendStatus = health.isPending
    ? 'Connecting…'
    : health.isError
      ? 'Backend unavailable'
      : 'Backend connected'

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <strong>Cycle Meal Planner</strong>
          <span className={`status ${health.isError ? 'status-error' : ''}`}>{backendStatus}</span>
        </div>
      </header>

      <aside className="sidebar" aria-label="Primary navigation">
        <nav>
          {navigation.map(([label, path]) => (
            <NavLink key={path} to={path} end={path === '/'}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="content">
        <Routes>
          <Route path="/" element={<PlaceholderPage title="Dashboard" />} />
          <Route path="/recipes" element={<PlaceholderPage title="Recipes" />} />
          <Route path="/meals" element={<PlaceholderPage title="Meals" />} />
          <Route path="/meal-plan" element={<PlaceholderPage title="Meal Plan" />} />
          <Route path="/inventory" element={<PlaceholderPage title="Inventory" />} />
          <Route path="/shopping" element={<PlaceholderPage title="Shopping" />} />
          <Route path="/leftovers" element={<PlaceholderPage title="Leftovers" />} />
          <Route path="/history" element={<PlaceholderPage title="History" />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
