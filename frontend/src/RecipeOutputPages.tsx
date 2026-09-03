import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { fetchRecipe } from './api'
import { RecipeDetailWithVariantsPage, RecipeEditorWithVariantsPage } from './RecipeVariantPages'
import RecipeOutputsPanel from './RecipeOutputsPanel'
import TypedAdvancePrepPanel from './TypedAdvancePrepPanel'

function OutputsPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const recipe = useQuery({ queryKey: ['recipe', id], queryFn: () => fetchRecipe(id), enabled: Number.isFinite(id) })
  if (!recipe.data) return null
  return <div style={{ marginTop: 20 }}><RecipeOutputsPanel recipe={recipe.data} /></div>
}

export function RecipeEditorWithAdvancedPage() {
  return <><RecipeEditorWithVariantsPage /><TypedAdvancePrepPanel /><OutputsPanel /></>
}

export function RecipeDetailWithAdvancedPage() {
  return <><RecipeDetailWithVariantsPage /><TypedAdvancePrepPanel /><OutputsPanel /></>
}
