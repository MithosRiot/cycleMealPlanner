import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { fetchRecipe } from './api'
import { fetchCookingSteps, saveCookingSteps, type CookingStepInput } from './cookingApi'

function normalize(items: CookingStepInput[]): CookingStepInput[] {
  return items.map((item, index) => ({ ...item, sort_order: index }))
}

export default function RecipeCookingStepsPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const queryClient = useQueryClient()
  const recipe = useQuery({ queryKey: ['recipe', id], queryFn: () => fetchRecipe(id), enabled: Number.isFinite(id) })
  const steps = useQuery({ queryKey: ['recipe-cooking-steps', id], queryFn: () => fetchCookingSteps(id), enabled: Number.isFinite(id) })
  const [draft, setDraft] = useState<CookingStepInput[] | null>(null)

  useEffect(() => {
    if (!steps.data) return
    setDraft(steps.data.map((item) => ({ title: item.title, instructions: item.instructions, prep_group_id: item.prep_group_id, sort_order: item.sort_order })))
  }, [steps.data])

  const save = useMutation({
    mutationFn: () => saveCookingSteps(id, normalize(draft ?? [])),
    onSuccess: async (saved) => {
      setDraft(saved.map((item) => ({ title: item.title, instructions: item.instructions, prep_group_id: item.prep_group_id, sort_order: item.sort_order })))
      await queryClient.invalidateQueries({ queryKey: ['recipe-cooking-steps', id] })
      await queryClient.invalidateQueries({ queryKey: ['cycle-cooking-mode'] })
    },
  })

  if (!Number.isFinite(id)) return null
  const items = draft ?? []
  const groups = recipe.data?.prep_groups ?? []

  function patch(index: number, update: Partial<CookingStepInput>) {
    setDraft(items.map((item, current) => current === index ? { ...item, ...update } : item))
  }
  function move(index: number, offset: -1 | 1) {
    const target = index + offset
    if (target < 0 || target >= items.length) return
    const copy = [...items]
    ;[copy[index], copy[target]] = [copy[target], copy[index]]
    setDraft(normalize(copy))
  }

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cooking steps</h2><p className="planning-note">Ordered steps used by Cooking Mode. Save the Recipe first, then maintain its execution steps here.</p></div>
      <button type="button" onClick={() => setDraft([...items, { title: `Step ${items.length + 1}`, instructions: null, prep_group_id: null, sort_order: items.length }])}>Add step</button>
    </div>
    {steps.error instanceof Error && <div className="error-banner">{steps.error.message}</div>}
    {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
    <div className="recipe-ingredient-list">
      {items.map((item, index) => <div className="recipe-ingredient-editor" key={index}>
        <div className="advanced-grid">
          <label>Title<input required value={item.title} onChange={(event) => patch(index, { title: event.target.value })} /></label>
          <label>Prep group<select value={item.prep_group_id ?? ''} onChange={(event) => patch(index, { prep_group_id: event.target.value ? Number(event.target.value) : null })}><option value="">All component ingredients</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
          <label className="span-2">Instructions<textarea value={item.instructions ?? ''} onChange={(event) => patch(index, { instructions: event.target.value || null })} /></label>
        </div>
        <div className="header-actions"><button type="button" className="button-secondary" disabled={index === 0} onClick={() => move(index, -1)}>Move up</button><button type="button" className="button-secondary" disabled={index === items.length - 1} onClick={() => move(index, 1)}>Move down</button><button type="button" className="button-secondary" onClick={() => setDraft(normalize(items.filter((_item, current) => current !== index)))}>Remove</button></div>
      </div>)}
    </div>
    {!steps.isPending && items.length === 0 && <p className="muted-line">No cooking steps yet.</p>}
    <button type="button" disabled={save.isPending || items.some((item) => !item.title.trim())} onClick={() => save.mutate()}>Save cooking steps</button>
  </section>
}
