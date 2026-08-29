import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fetchRecipes, fetchTags } from './api'
import { archiveMeal, createMeal, fetchMeal, fetchMeals, MealInput, MealRecipeInput, updateMeal } from './mealsApi'

const COMMON_MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner', 'Snack', 'Dessert', 'Side']

export function MealsPage() {
  const [search, setSearch] = useState('')
  const [mealType, setMealType] = useState('')
  const [tagId, setTagId] = useState('')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => fetchTags(false) })
  const meals = useQuery({
    queryKey: ['meals', search, mealType, tagId, favoritesOnly],
    queryFn: () => fetchMeals({
      search,
      meal_type: mealType || undefined,
      tag_id: tagId ? Number(tagId) : undefined,
      favorite: favoritesOnly ? true : undefined,
    }),
  })

  return (
    <section className="recipe-page">
      <header className="page-heading">
        <div><p className="eyebrow">Meal Library</p><h1>Meals</h1><p>Combine reusable recipes into meal templates for planning.</p></div>
        <Link className="button-link" to="/meals/new">New meal</Link>
      </header>
      <div className="filter-bar">
        <input placeholder="Search meals" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={mealType} onChange={(e) => setMealType(e.target.value)}><option value="">All meal types</option>{COMMON_MEAL_TYPES.map((type) => <option key={type}>{type}</option>)}</select>
        <select value={tagId} onChange={(e) => setTagId(e.target.value)}><option value="">All tags</option>{tags.data?.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select>
        <label className="checkbox-label"><input type="checkbox" checked={favoritesOnly} onChange={(e) => setFavoritesOnly(e.target.checked)} /> Favorites</label>
      </div>
      {meals.isError && <div className="error-banner">{(meals.error as Error).message}</div>}
      <div className="recipe-grid">
        {meals.data?.map((meal) => (
          <Link key={meal.id} to={`/meals/${meal.id}`} className="recipe-card">
            <div className="recipe-card-heading"><h2>{meal.name}</h2>{meal.favorite && <span>★</span>}</div>
            <p>{meal.description || 'No description yet.'}</p>
            <div className="recipe-meta"><strong>{meal.recipes.length} component{meal.recipes.length === 1 ? '' : 's'}</strong></div>
            <div className="chip-row">{meal.meal_types.map((type) => <span key={type} className="chip">{type}</span>)}{meal.tags.map((tag) => <span key={tag.id} className="chip chip-muted">{tag.name}</span>)}</div>
          </Link>
        ))}
      </div>
      {!meals.isPending && meals.data?.length === 0 && <p className="empty-state">No meals match these filters.</p>}
    </section>
  )
}

function emptyComponent(recipeId: number, index: number): MealRecipeInput {
  return { recipe_id: recipeId, serving_multiplier: '1', default_servings: null, sort_order: index, notes: null }
}

export function MealEditorPage() {
  const { mealId } = useParams()
  const editingId = mealId ? Number(mealId) : null
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const mealQuery = useQuery({ queryKey: ['meal', editingId], queryFn: () => fetchMeal(editingId as number), enabled: editingId !== null })
  const recipesQuery = useQuery({ queryKey: ['recipes', 'meal-editor'], queryFn: () => fetchRecipes() })
  const tagsQuery = useQuery({ queryKey: ['tags'], queryFn: () => fetchTags(false) })
  const meal = mealQuery.data
  const recipes = recipesQuery.data ?? []
  const [draft, setDraft] = useState<MealInput | null>(null)

  const initialDraft = useMemo<MealInput>(() => meal ? {
    name: meal.name,
    description: meal.description,
    favorite: meal.favorite,
    meal_types: meal.meal_types,
    tag_ids: meal.tags.map((tag) => tag.id),
    recipes: meal.recipes.map(({ id: _id, meal_id: _mealId, ...item }) => item),
    active: meal.active,
  } : { name: '', description: null, favorite: false, meal_types: [], tag_ids: [], recipes: [] }, [meal])
  const current = draft ?? initialDraft

  const save = useMutation({
    mutationFn: (input: MealInput) => meal ? updateMeal(meal, input) : createMeal(input),
    onSuccess: async (saved) => { await queryClient.invalidateQueries({ queryKey: ['meals'] }); navigate(`/meals/${saved.id}`) },
  })

  function patch(update: Partial<MealInput>) { setDraft({ ...current, ...update }) }
  function submit(event: FormEvent) { event.preventDefault(); save.mutate({ ...current, recipes: current.recipes.map((item, index) => ({ ...item, sort_order: index })) }) }

  if ((editingId && mealQuery.isPending) || recipesQuery.isPending) return <p>Loading…</p>

  return (
    <section className="recipe-page">
      <header className="page-heading"><div><p className="eyebrow">Meal Editor</p><h1>{meal ? 'Edit meal' : 'New meal'}</h1></div></header>
      {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
      <form className="recipe-editor" onSubmit={submit}>
        <section className="editor-card"><div className="editor-grid">
          <label>Name<input required value={current.name} onChange={(e) => patch({ name: e.target.value })} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={current.favorite} onChange={(e) => patch({ favorite: e.target.checked })} /> Favorite</label>
          <label className="span-2">Description<textarea value={current.description ?? ''} onChange={(e) => patch({ description: e.target.value || null })} /></label>
        </div></section>
        <section className="editor-card"><h2>Meal types</h2><div className="chip-checks">{COMMON_MEAL_TYPES.map((type) => { const selected = current.meal_types.includes(type.toUpperCase()); return <label key={type} className={`chip-check ${selected ? 'selected' : ''}`}><input type="checkbox" checked={selected} onChange={(e) => patch({ meal_types: e.target.checked ? [...current.meal_types, type.toUpperCase()] : current.meal_types.filter((value) => value !== type.toUpperCase()) })} />{type}</label> })}</div></section>
        <section className="editor-card"><h2>Tags</h2><div className="chip-checks">{tagsQuery.data?.map((tag) => { const selected = current.tag_ids.includes(tag.id); return <label key={tag.id} className={`chip-check ${selected ? 'selected' : ''}`}><input type="checkbox" checked={selected} onChange={(e) => patch({ tag_ids: e.target.checked ? [...current.tag_ids, tag.id] : current.tag_ids.filter((id) => id !== tag.id) })} />{tag.name}</label> })}</div></section>
        <section className="editor-card"><div className="section-heading-row"><h2>Recipe components</h2><button type="button" disabled={!recipes.length} onClick={() => patch({ recipes: [...current.recipes, emptyComponent(recipes[0].id, current.recipes.length)] })}>Add recipe</button></div>
          <div className="meal-component-list">{current.recipes.map((component, index) => (
            <div className="meal-component-row" key={`${index}-${component.recipe_id}`}>
              <select value={component.recipe_id} onChange={(e) => patch({ recipes: current.recipes.map((item, i) => i === index ? { ...item, recipe_id: Number(e.target.value) } : item) })}>{recipes.map((recipe) => <option key={recipe.id} value={recipe.id}>{recipe.name}</option>)}</select>
              <label>Multiplier<input type="number" min="0.001" step="any" value={component.serving_multiplier} onChange={(e) => patch({ recipes: current.recipes.map((item, i) => i === index ? { ...item, serving_multiplier: e.target.value } : item) })} /></label>
              <label>Default servings<input type="number" min="0.001" step="any" value={component.default_servings ?? ''} onChange={(e) => patch({ recipes: current.recipes.map((item, i) => i === index ? { ...item, default_servings: e.target.value || null } : item) })} /></label>
              <input placeholder="Component notes" value={component.notes ?? ''} onChange={(e) => patch({ recipes: current.recipes.map((item, i) => i === index ? { ...item, notes: e.target.value || null } : item) })} />
              <button type="button" className="button-secondary" onClick={() => patch({ recipes: current.recipes.filter((_, i) => i !== index) })}>Remove</button>
            </div>
          ))}</div>
          {!current.recipes.length && <p className="muted-line">Add at least one recipe component.</p>}
        </section>
        <div className="form-actions"><button type="submit" disabled={!current.recipes.length || save.isPending}>Save meal</button><button type="button" className="button-secondary" onClick={() => navigate('/meals')}>Cancel</button></div>
      </form>
    </section>
  )
}

export function MealDetailPage() {
  const { mealId } = useParams()
  const id = Number(mealId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const meal = useQuery({ queryKey: ['meal', id], queryFn: () => fetchMeal(id) })
  const recipes = useQuery({ queryKey: ['recipes', 'meal-detail'], queryFn: () => fetchRecipes({ include_inactive: true }) })
  const archive = useMutation({ mutationFn: () => archiveMeal(id), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['meals'] }); navigate('/meals') } })
  const recipeNames = useMemo(() => new Map((recipes.data ?? []).map((recipe) => [recipe.id, recipe.name])), [recipes.data])
  if (meal.isPending) return <p>Loading…</p>
  if (meal.error instanceof Error) return <div className="error-banner">{meal.error.message}</div>
  const data = meal.data!
  return (
    <section className="recipe-page">
      <header className="page-heading"><div><p className="eyebrow">Saved Meal</p><h1>{data.name}</h1><p>{data.description || 'No description yet.'}</p></div><div className="header-actions"><Link className="button-link" to={`/meals/${id}/edit`}>Edit</Link><button className="button-danger" onClick={() => archive.mutate()}>Archive</button></div></header>
      <section className="editor-card"><div className="chip-row">{data.meal_types.map((type) => <span className="chip" key={type}>{type}</span>)}{data.tags.map((tag) => <span className="chip chip-muted" key={tag.id}>{tag.name}</span>)}</div></section>
      <section className="editor-card"><h2>Components</h2><div className="meal-detail-list">{data.recipes.map((component) => <div key={component.id}><strong>{recipeNames.get(component.recipe_id) ?? `Recipe #${component.recipe_id}`}</strong><span>× {component.serving_multiplier}</span><span>{component.default_servings ? `${component.default_servings} servings` : 'Recipe default servings'}</span>{component.notes && <span>{component.notes}</span>}</div>)}</div></section>
    </section>
  )
}
