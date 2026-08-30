import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  archiveRecipe,
  createRecipe,
  fetchIngredients,
  fetchMeasurementUnits,
  fetchRecipe,
  fetchRecipes,
  fetchTags,
  Ingredient,
  MeasurementUnit,
  RecipeIngredientInput,
  RecipeInput,
  RecipePrepGroupInput,
  scaleRecipe,
  updateRecipe,
} from './api'

const SCALING_MODES: RecipeIngredientInput['scaling_mode'][] = ['LINEAR', 'FIXED', 'ROUND_UP', 'MANUAL']
const REQUIRED_STATES = ['ANY', 'FRESH', 'FROZEN', 'THAWED', 'REFRIGERATED', 'PANTRY']
const COMMON_MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner', 'Snack', 'Dessert', 'Side']

function numberOrNull(value: string): number | null { return value.trim() ? Number(value) : null }
function groupKey(id: number): string { return `group-${id}` }
function newGroupKey(): string { return `new-${Date.now()}-${Math.random().toString(36).slice(2)}` }

function emptyIngredient(units: MeasurementUnit[], ingredients: Ingredient[]): RecipeIngredientInput {
  const ingredient = ingredients[0]
  return {
    ingredient_id: ingredient?.id ?? 0,
    prep_group_key: null,
    quantity: '1',
    unit_id: ingredient?.preferred_unit_id ?? units[0]?.id ?? 0,
    display_text: null,
    preparation: null,
    prep_method: null,
    prep_size: null,
    prep_state: null,
    optional: false,
    scaling_mode: 'LINEAR',
    required_state: 'ANY',
    sort_order: 0,
    notes: null,
  }
}

function ingredientName(id: number, ingredients: Ingredient[]): string { return ingredients.find((item) => item.id === id)?.name ?? `Ingredient #${id}` }
function unitCode(id: number, units: MeasurementUnit[]): string { return units.find((item) => item.id === id)?.code ?? '' }

export function RecipesPage() {
  const [search, setSearch] = useState('')
  const [mealType, setMealType] = useState('')
  const [tagId, setTagId] = useState('')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => fetchTags(false) })
  const recipes = useQuery({ queryKey: ['recipes', search, mealType, tagId, favoritesOnly], queryFn: () => fetchRecipes({ search, meal_type: mealType || undefined, tag_id: tagId ? Number(tagId) : undefined, favorite: favoritesOnly ? true : undefined }) })

  return <section className="recipe-page">
    <header className="page-heading"><div><p className="eyebrow">Recipe Library</p><h1>Recipes</h1><p>Build structured recipes now so planning and shopping can use them later.</p></div><Link className="button-link" to="/recipes/new">New recipe</Link></header>
    <div className="filter-bar">
      <input aria-label="Search recipes" placeholder="Search recipes" value={search} onChange={(event) => setSearch(event.target.value)} />
      <select value={mealType} onChange={(event) => setMealType(event.target.value)}><option value="">All meal types</option>{COMMON_MEAL_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select>
      <select value={tagId} onChange={(event) => setTagId(event.target.value)}><option value="">All tags</option>{tags.data?.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select>
      <label className="checkbox-label"><input type="checkbox" checked={favoritesOnly} onChange={(event) => setFavoritesOnly(event.target.checked)} />Favorites</label>
    </div>
    {recipes.isError && <div className="error-banner">{(recipes.error as Error).message}</div>}
    <div className="recipe-grid">{recipes.data?.map((recipe) => <Link key={recipe.id} to={`/recipes/${recipe.id}`} className="recipe-card"><div className="recipe-card-heading"><h2>{recipe.name}</h2>{recipe.favorite && <span title="Favorite">★</span>}</div><p>{recipe.description || 'No description yet.'}</p><div className="recipe-meta"><strong>Serves {recipe.base_servings} {recipe.serving_unit}</strong><span>{recipe.prep_time_minutes ?? 0} min prep</span><span>{recipe.cook_time_minutes ?? 0} min cook</span></div><div className="chip-row">{recipe.meal_types.map((type) => <span key={type} className="chip">{type}</span>)}{recipe.tags.map((tag) => <span key={tag.id} className="chip chip-muted">{tag.name}</span>)}</div></Link>)}</div>
    {!recipes.isPending && recipes.data?.length === 0 && <p className="empty-state">No recipes match these filters.</p>}
  </section>
}

function RecipeIngredientEditor({ value, index, ingredients, units, prepGroups, onChange, onRemove }: { value: RecipeIngredientInput; index: number; ingredients: Ingredient[]; units: MeasurementUnit[]; prepGroups: RecipePrepGroupInput[]; onChange: (value: RecipeIngredientInput) => void; onRemove: () => void }) {
  function patch(update: Partial<RecipeIngredientInput>) { onChange({ ...value, ...update, sort_order: index }) }
  return <div className="recipe-ingredient-editor">
    <div className="ingredient-main-row">
      <select value={value.ingredient_id} onChange={(event) => { const ingredientId = Number(event.target.value); const preferred = ingredients.find((item) => item.id === ingredientId)?.preferred_unit_id; patch({ ingredient_id: ingredientId, unit_id: preferred ?? value.unit_id }) }}>{ingredients.map((ingredient) => <option key={ingredient.id} value={ingredient.id}>{ingredient.name}</option>)}</select>
      <input aria-label="Quantity" inputMode="decimal" value={value.quantity} onChange={(event) => patch({ quantity: event.target.value })} />
      <select value={value.unit_id} onChange={(event) => patch({ unit_id: Number(event.target.value) })}>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.code} — {unit.name}</option>)}</select>
      <select value={value.prep_group_key ?? ''} onChange={(event) => patch({ prep_group_key: event.target.value || null })}><option value="">Ungrouped</option>{prepGroups.map((group) => <option key={group.client_key} value={group.client_key}>{group.name}</option>)}</select>
      <button type="button" className="button-secondary" onClick={onRemove}>Remove</button>
    </div>
    <details className="advanced-panel"><summary>Prep & advanced</summary><div className="advanced-grid">
      <label>Legacy preparation<input placeholder="e.g. diced" value={value.preparation ?? ''} onChange={(event) => patch({ preparation: event.target.value || null })} /></label>
      <label>Prep method<input placeholder="e.g. dice, mince, grate" value={value.prep_method ?? ''} onChange={(event) => patch({ prep_method: event.target.value || null })} /></label>
      <label>Size / shape<input placeholder="e.g. 1/2-inch cubes" value={value.prep_size ?? ''} onChange={(event) => patch({ prep_size: event.target.value || null })} /></label>
      <label>Prep state<input placeholder="e.g. peeled, drained" value={value.prep_state ?? ''} onChange={(event) => patch({ prep_state: event.target.value || null })} /></label>
      <label>Scaling<select value={value.scaling_mode} onChange={(event) => patch({ scaling_mode: event.target.value as RecipeIngredientInput['scaling_mode'] })}>{SCALING_MODES.map((mode) => <option key={mode}>{mode}</option>)}</select></label>
      <label>Required state<select value={value.required_state} onChange={(event) => patch({ required_state: event.target.value })}>{REQUIRED_STATES.map((state) => <option key={state}>{state}</option>)}</select></label>
      <label>Display text<input value={value.display_text ?? ''} onChange={(event) => patch({ display_text: event.target.value || null })} /></label>
      <label>Notes<input value={value.notes ?? ''} onChange={(event) => patch({ notes: event.target.value || null })} /></label>
      <label className="checkbox-label"><input type="checkbox" checked={value.optional} onChange={(event) => patch({ optional: event.target.checked })} />Optional ingredient</label>
    </div></details>
  </div>
}

function PrepGroupEditor({ groups, ingredients, onChange }: { groups: RecipePrepGroupInput[]; ingredients: RecipeIngredientInput[]; onChange: (groups: RecipePrepGroupInput[], ingredients?: RecipeIngredientInput[]) => void }) {
  function normalize(next: RecipePrepGroupInput[]) { return next.map((group, index) => ({ ...group, sort_order: index })) }
  return <section className="editor-card">
    <div className="section-heading-row"><div><h2>Prep Groups</h2><p>Optional sections for organizing ingredient prep.</p></div><button type="button" onClick={() => onChange([...groups, { client_key: newGroupKey(), name: `Prep group ${groups.length + 1}`, sort_order: groups.length }])}>Add prep group</button></div>
    <div className="recipe-ingredient-list">{groups.map((group, index) => <div className="ingredient-main-row" key={group.client_key}>
      <input value={group.name} onChange={(event) => onChange(groups.map((current, currentIndex) => currentIndex === index ? { ...current, name: event.target.value } : current))} />
      <button type="button" className="button-secondary" disabled={index === 0} onClick={() => { const copy = [...groups]; [copy[index - 1], copy[index]] = [copy[index], copy[index - 1]]; onChange(normalize(copy)) }}>↑</button>
      <button type="button" className="button-secondary" disabled={index === groups.length - 1} onClick={() => { const copy = [...groups]; [copy[index], copy[index + 1]] = [copy[index + 1], copy[index]]; onChange(normalize(copy)) }}>↓</button>
      <button type="button" className="button-secondary" onClick={() => onChange(normalize(groups.filter((_, currentIndex) => currentIndex !== index)), ingredients.map((item) => item.prep_group_key === group.client_key ? { ...item, prep_group_key: null } : item))}>Remove</button>
    </div>)}</div>
  </section>
}

export function RecipeEditorPage() {
  const { recipeId } = useParams()
  const editingId = recipeId ? Number(recipeId) : null
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const recipeQuery = useQuery({ queryKey: ['recipe', editingId], queryFn: () => fetchRecipe(editingId as number), enabled: editingId !== null })
  const ingredientsQuery = useQuery({ queryKey: ['ingredients', 'recipe-editor'], queryFn: () => fetchIngredients() })
  const unitsQuery = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const tagsQuery = useQuery({ queryKey: ['tags'], queryFn: () => fetchTags(false) })
  const recipe = recipeQuery.data
  const ingredients = ingredientsQuery.data ?? []
  const units = unitsQuery.data ?? []
  const [draft, setDraft] = useState<RecipeInput | null>(null)

  const initialDraft = useMemo<RecipeInput>(() => {
    if (recipe) {
      const prep_groups = recipe.prep_groups.map((group) => ({ client_key: groupKey(group.id), name: group.name, sort_order: group.sort_order }))
      return {
        name: recipe.name, description: recipe.description, base_servings: recipe.base_servings, serving_unit: recipe.serving_unit, yield_quantity: recipe.yield_quantity, yield_unit_id: recipe.yield_unit_id, prep_time_minutes: recipe.prep_time_minutes, cook_time_minutes: recipe.cook_time_minutes, notes: recipe.notes, favorite: recipe.favorite, meal_types: recipe.meal_types, tag_ids: recipe.tags.map((tag) => tag.id), prep_groups,
        ingredients: recipe.ingredients.map((item) => ({ ingredient_id: item.ingredient_id, prep_group_key: item.prep_group_id ? groupKey(item.prep_group_id) : null, quantity: item.quantity, unit_id: item.unit_id, display_text: item.display_text, preparation: item.preparation, prep_method: item.prep_method, prep_size: item.prep_size, prep_state: item.prep_state, optional: item.optional, scaling_mode: item.scaling_mode, required_state: item.required_state, sort_order: item.sort_order, notes: item.notes })), active: recipe.active,
      }
    }
    return { name: '', description: null, base_servings: '4', serving_unit: 'servings', yield_quantity: null, yield_unit_id: null, prep_time_minutes: null, cook_time_minutes: null, notes: null, favorite: false, meal_types: [], tag_ids: [], prep_groups: [], ingredients: [] }
  }, [recipe])

  const form = draft ?? initialDraft
  function patch(update: Partial<RecipeInput>) { setDraft({ ...form, ...update }) }
  const save = useMutation({ mutationFn: async () => { const payload: RecipeInput = { ...form, prep_groups: form.prep_groups.map((group, index) => ({ ...group, sort_order: index })), ingredients: form.ingredients.map((item, index) => ({ ...item, sort_order: index })) }; return recipe ? updateRecipe(recipe, payload) : createRecipe(payload) }, onSuccess: async (saved) => { await queryClient.invalidateQueries({ queryKey: ['recipes'] }); await queryClient.invalidateQueries({ queryKey: ['recipe', saved.id] }); navigate(`/recipes/${saved.id}`) } })
  function submit(event: FormEvent) { event.preventDefault(); save.mutate() }
  if (editingId !== null && recipeQuery.isPending) return <p>Loading recipe…</p>

  return <section className="recipe-page">
    <header className="page-heading"><div><p className="eyebrow">Recipe Editor</p><h1>{recipe ? `Edit ${recipe.name}` : 'New Recipe'}</h1></div><Link className="button-link button-link-secondary" to={recipe ? `/recipes/${recipe.id}` : '/recipes'}>Cancel</Link></header>
    {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
    <form className="recipe-editor" onSubmit={submit}>
      <section className="editor-card"><h2>Recipe</h2><div className="editor-grid">
        <label className="span-2">Name<input required value={form.name} onChange={(event) => patch({ name: event.target.value })} /></label>
        <label className="span-2">Description<textarea value={form.description ?? ''} onChange={(event) => patch({ description: event.target.value || null })} /></label>
        <label>Base servings<input required min="0.1" step="0.1" type="number" value={form.base_servings} onChange={(event) => patch({ base_servings: event.target.value })} /></label>
        <label>Serving label<input required value={form.serving_unit} onChange={(event) => patch({ serving_unit: event.target.value })} /></label>
        <label>Prep minutes<input min="0" type="number" value={form.prep_time_minutes ?? ''} onChange={(event) => patch({ prep_time_minutes: numberOrNull(event.target.value) })} /></label>
        <label>Cook minutes<input min="0" type="number" value={form.cook_time_minutes ?? ''} onChange={(event) => patch({ cook_time_minutes: numberOrNull(event.target.value) })} /></label>
        <label>Yield quantity<input min="0" step="0.01" type="number" value={form.yield_quantity ?? ''} onChange={(event) => patch({ yield_quantity: event.target.value || null })} /></label>
        <label>Yield unit<select value={form.yield_unit_id ?? ''} onChange={(event) => patch({ yield_unit_id: event.target.value ? Number(event.target.value) : null })}><option value="">None</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label>
        <label className="span-2">Notes<textarea value={form.notes ?? ''} onChange={(event) => patch({ notes: event.target.value || null })} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={form.favorite} onChange={(event) => patch({ favorite: event.target.checked })} />Favorite</label>
      </div></section>
      <section className="editor-card"><h2>Meal Types</h2><div className="chip-checks">{COMMON_MEAL_TYPES.map((type) => <label key={type} className={`chip-check ${form.meal_types.includes(type) ? 'selected' : ''}`}><input type="checkbox" checked={form.meal_types.includes(type)} onChange={(event) => patch({ meal_types: event.target.checked ? [...form.meal_types, type] : form.meal_types.filter((item) => item !== type) })} />{type}</label>)}</div><h3>Tags</h3><div className="chip-checks">{tagsQuery.data?.map((tag) => <label key={tag.id} className={`chip-check ${form.tag_ids.includes(tag.id) ? 'selected' : ''}`}><input type="checkbox" checked={form.tag_ids.includes(tag.id)} onChange={(event) => patch({ tag_ids: event.target.checked ? [...form.tag_ids, tag.id] : form.tag_ids.filter((id) => id !== tag.id) })} />{tag.name}</label>)}</div></section>
      <PrepGroupEditor groups={form.prep_groups} ingredients={form.ingredients} onChange={(prep_groups, nextIngredients) => patch({ prep_groups, ...(nextIngredients ? { ingredients: nextIngredients } : {}) })} />
      <section className="editor-card"><div className="section-heading-row"><h2>Ingredients</h2><button type="button" disabled={!ingredients.length || !units.length} onClick={() => patch({ ingredients: [...form.ingredients, { ...emptyIngredient(units, ingredients), sort_order: form.ingredients.length }] })}>Add ingredient</button></div>{!ingredients.length && <p>Add ingredients under Settings → Ingredients & Tags before building recipes.</p>}<div className="recipe-ingredient-list">{form.ingredients.map((item, index) => <RecipeIngredientEditor key={`${item.ingredient_id}-${index}`} value={item} index={index} ingredients={ingredients} units={units} prepGroups={form.prep_groups} onChange={(next) => patch({ ingredients: form.ingredients.map((current, currentIndex) => currentIndex === index ? next : current) })} onRemove={() => patch({ ingredients: form.ingredients.filter((_current, currentIndex) => currentIndex !== index) })} />)}</div></section>
      <div className="form-actions"><button type="submit" disabled={save.isPending || !form.name.trim()}>Save recipe</button><Link className="button-link button-link-secondary" to={recipe ? `/recipes/${recipe.id}` : '/recipes'}>Cancel</Link></div>
    </form>
  </section>
}

export function RecipeDetailPage() {
  const { recipeId } = useParams(); const id = Number(recipeId); const navigate = useNavigate(); const queryClient = useQueryClient()
  const recipe = useQuery({ queryKey: ['recipe', id], queryFn: () => fetchRecipe(id), enabled: Number.isFinite(id) })
  const ingredients = useQuery({ queryKey: ['ingredients', 'recipe-detail'], queryFn: () => fetchIngredients() })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const [servings, setServings] = useState(''); const [scaleResult, setScaleResult] = useState<Awaited<ReturnType<typeof scaleRecipe>> | null>(null)
  const scale = useMutation({ mutationFn: (requested: string) => scaleRecipe(id, requested), onSuccess: setScaleResult })
  const archive = useMutation({ mutationFn: () => archiveRecipe(id), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['recipes'] }); navigate('/recipes') } })
  if (recipe.isPending) return <p>Loading recipe…</p>
  if (recipe.isError || !recipe.data) return <div className="error-banner">Recipe could not be loaded.</div>
  const data = recipe.data; const ingredientList = ingredients.data ?? []; const unitList = units.data ?? []; const scaledById = new Map(scaleResult?.ingredients.map((item) => [item.recipe_ingredient_id, item]))
  const sections = [...data.prep_groups.map((group) => ({ id: group.id, name: group.name, sort_order: group.sort_order })), { id: null, name: 'Ungrouped', sort_order: 999999 }]

  return <section className="recipe-page">
    <header className="page-heading"><div><p className="eyebrow">Recipe</p><h1>{data.name} {data.favorite && '★'}</h1><p>{data.description}</p></div><div className="header-actions"><Link className="button-link" to={`/recipes/${data.id}/edit`}>Edit</Link><button type="button" className="button-secondary" onClick={() => archive.mutate()}>Archive</button></div></header>
    <div className="recipe-detail-grid"><section className="editor-card"><h2>Overview</h2><dl className="detail-list"><div><dt>Serves</dt><dd>{data.base_servings} {data.serving_unit}</dd></div><div><dt>Prep</dt><dd>{data.prep_time_minutes ?? 0} min</dd></div><div><dt>Cook</dt><dd>{data.cook_time_minutes ?? 0} min</dd></div></dl><div className="chip-row">{data.meal_types.map((type) => <span className="chip" key={type}>{type}</span>)}{data.tags.map((tag) => <span className="chip chip-muted" key={tag.id}>{tag.name}</span>)}</div></section><section className="editor-card"><h2>Serving Scaler</h2><form className="scale-form" onSubmit={(event) => { event.preventDefault(); scale.mutate(servings || data.base_servings) }}><label>Requested servings<input min="0.1" step="0.1" type="number" value={servings} placeholder={data.base_servings} onChange={(event) => setServings(event.target.value)} /></label><button type="submit" disabled={scale.isPending}>Preview</button></form>{scale.error instanceof Error && <p className="field-error">{scale.error.message}</p>}{scaleResult && <p>Scale factor: {scaleResult.scale_factor}×</p>}</section></div>
    <section className="editor-card"><h2>Ingredients</h2>{sections.sort((a, b) => a.sort_order - b.sort_order).map((section) => { const rows = data.ingredients.filter((item) => item.prep_group_id === section.id); if (!rows.length) return null; return <div key={section.id ?? 'ungrouped'}><h3>{section.name}</h3><div className="ingredient-detail-list">{rows.map((item) => { const scaled = scaledById.get(item.id); const prep = [item.prep_method, item.prep_size, item.prep_state].filter(Boolean).join(' · ') || item.preparation; return <div key={item.id} className="ingredient-detail-row"><strong>{ingredientName(item.ingredient_id, ingredientList)}</strong><span>{scaled?.quantity ?? item.quantity} {scaled?.unit_code ?? unitCode(item.unit_id, unitList)}</span><span>{prep || '—'}</span><span>{item.optional ? 'Optional' : item.scaling_mode}</span>{scaled?.manual_review && <span className="warning-text">Manual review</span>}</div> })}</div></div> })}</section>
    {data.notes && <section className="editor-card"><h2>Notes</h2><p>{data.notes}</p></section>}<Link className="text-link" to="/recipes">← Back to Recipe Library</Link>
  </section>
}
