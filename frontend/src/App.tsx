import { useQuery } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { fetchHealth } from './api'
import CycleSchedulingPanel from './CycleSchedulingPanel'
import CycleValidationPage from './CycleValidationPage'
import IngredientsPage from './IngredientsPage'
import './InventoryPage.css'
import { MealDetailPage, MealEditorPage, MealsPage } from './MealPages'
import './MealPages.css'
import { RecipeEditorPage, RecipesPage } from './RecipePages'
import { RecipeDetailWithAdvancedPage, RecipeEditorWithAdvancedPage } from './RecipeOutputPages'
import { InventoryWithReservationsPage, MealPlanWithReservationsPage } from './ReservationIntegrationPages'
import SettingsPage from './SettingsPage'
import ShoppingPage from './ShoppingPage'

const navigation = [
  ['Dashboard', '/'], ['Recipes', '/recipes'], ['Meals', '/meals'], ['Meal Plan', '/meal-plan'],
  ['Plan Validation', '/meal-plan/validation'], ['Inventory', '/inventory'], ['Shopping', '/shopping'],
  ['Leftovers', '/leftovers'], ['History', '/history'], ['Settings', '/settings'],
] as const

function PlaceholderPage({ title }: { title: string }) {
  return <section className="page-card"><p className="eyebrow">Cycle Meal Planner</p><h1>{title}</h1><p>This section is ready for its Milestone implementation.</p></section>
}

function MealPlanPageWithScheduling() {
  return <><MealPlanWithReservationsPage /><CycleSchedulingPanel /></>
}

function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: fetchHealth, retry: 1, refetchInterval: 30_000 })
  const backendStatus = health.isPending ? 'Connecting…' : health.isError ? 'Backend unavailable' : 'Backend connected'

  return <div className="app-shell">
    <header className="topbar"><div><strong>Cycle Meal Planner</strong><span className={`status ${health.isError ? 'status-error' : ''}`}>{backendStatus}</span></div></header>
    <aside className="sidebar" aria-label="Primary navigation"><nav>{navigation.map(([label, path]) => <NavLink key={path} to={path} end={path === '/'}>{label}</NavLink>)}</nav></aside>
    <main className="content"><Routes>
      <Route path="/" element={<PlaceholderPage title="Dashboard" />} />
      <Route path="/recipes" element={<RecipesPage />} />
      <Route path="/recipes/new" element={<RecipeEditorPage />} />
      <Route path="/recipes/:recipeId" element={<RecipeDetailWithAdvancedPage />} />
      <Route path="/recipes/:recipeId/edit" element={<RecipeEditorWithAdvancedPage />} />
      <Route path="/meals" element={<MealsPage />} />
      <Route path="/meals/new" element={<MealEditorPage />} />
      <Route path="/meals/:mealId" element={<MealDetailPage />} />
      <Route path="/meals/:mealId/edit" element={<MealEditorPage />} />
      <Route path="/meal-plan" element={<MealPlanPageWithScheduling />} />
      <Route path="/meal-plan/validation" element={<CycleValidationPage />} />
      <Route path="/inventory" element={<InventoryWithReservationsPage />} />
      <Route path="/shopping" element={<ShoppingPage />} />
      <Route path="/leftovers" element={<PlaceholderPage title="Leftovers" />} />
      <Route path="/history" element={<PlaceholderPage title="History" />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/settings/ingredients" element={<IngredientsPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes></main>
  </div>
}

export default App
