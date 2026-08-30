import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { fetchIngredients, fetchMeasurementUnits, fetchRecipe } from './api'
import { RecipeDetailPage, RecipeEditorPage } from './RecipePages'
import RecipeVariantsEditor from './RecipeVariantsEditor'

function VariantsPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const recipe = useQuery({ queryKey: ['recipe', id], queryFn: () => fetchRecipe(id), enabled: Number.isFinite(id) })
  const ingredients = useQuery({ queryKey: ['ingredients', 'recipe-variants'], queryFn: () => fetchIngredients() })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  if (!recipe.data || !ingredients.data || !units.data) return null
  return <div style={{ marginTop: 20 }}><RecipeVariantsEditor recipe={recipe.data} ingredients={ingredients.data} units={units.data} /></div>
}

export function RecipeEditorWithVariantsPage() {
  return <><RecipeEditorPage /><VariantsPanel /></>
}

export function RecipeDetailWithVariantsPage() {
  return <><RecipeDetailPage /><VariantsPanel /></>
}
