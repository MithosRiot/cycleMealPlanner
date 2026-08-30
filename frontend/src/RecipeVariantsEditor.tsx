import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  archiveRecipeVariant,
  createRecipeVariant,
  fetchRecipeVariants,
  Ingredient,
  MeasurementUnit,
  Recipe,
  RecipeVariant,
  RecipeVariantInput,
  RecipeVariantOverrideInput,
  scaleRecipe,
  updateRecipeVariant,
} from './api'

function blankVariant(sortOrder: number): RecipeVariantInput {
  return { name: `Variant ${sortOrder + 1}`, notes: null, active: true, sort_order: sortOrder, overrides: [] }
}

function toInput(value: RecipeVariant): RecipeVariantInput {
  return {
    name: value.name,
    notes: value.notes,
    active: value.active,
    sort_order: value.sort_order,
    overrides: value.overrides.map(({ recipe_ingredient_id, quantity, unit_id, substitution_id, preparation, prep_method, prep_size, prep_state, notes }) => ({ recipe_ingredient_id, quantity, unit_id, substitution_id, preparation, prep_method, prep_size, prep_state, notes })),
  }
}

export default function RecipeVariantsEditor({ recipe, ingredients, units }: { recipe: Recipe; ingredients: Ingredient[]; units: MeasurementUnit[] }) {
  const queryClient = useQueryClient()
  const variants = useQuery({ queryKey: ['recipe-variants', recipe.id], queryFn: () => fetchRecipeVariants(recipe.id, true) })
  const [editingId, setEditingId] = useState<number | 'new' | null>(null)
  const selected = editingId === 'new' ? null : variants.data?.find((item) => item.id === editingId)
  const [draft, setDraft] = useState<RecipeVariantInput | null>(null)
  const form = draft ?? (selected ? toInput(selected) : blankVariant(variants.data?.length ?? 0))
  const ingredientNames = useMemo(() => new Map(ingredients.map((item) => [item.id, item.name])), [ingredients])
  const activeVariants = variants.data?.filter((item) => item.active) ?? []
  const [previewVariantId, setPreviewVariantId] = useState<number | null>(null)
  const [previewServings, setPreviewServings] = useState(recipe.base_servings)
  const preview = useMutation({ mutationFn: () => scaleRecipe(recipe.id, previewServings, {}, {}, previewVariantId) })

  const save = useMutation({
    mutationFn: () => editingId === 'new' ? createRecipeVariant(recipe.id, form) : updateRecipeVariant(recipe.id, editingId as number, form),
    onSuccess: async () => { setEditingId(null); setDraft(null); await queryClient.invalidateQueries({ queryKey: ['recipe-variants', recipe.id] }) },
  })
  const archive = useMutation({ mutationFn: (id: number) => archiveRecipeVariant(recipe.id, id), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['recipe-variants', recipe.id] }) })

  function patch(update: Partial<RecipeVariantInput>) { setDraft({ ...form, ...update }) }
  function patchOverride(index: number, update: Partial<RecipeVariantOverrideInput>) { patch({ overrides: form.overrides.map((item, current) => current === index ? { ...item, ...update } : item) }) }
  function addOverride() {
    const used = new Set(form.overrides.map((item) => item.recipe_ingredient_id))
    const candidate = recipe.ingredients.find((item) => !used.has(item.id))
    if (!candidate) return
    patch({ overrides: [...form.overrides, { recipe_ingredient_id: candidate.id, quantity: null, unit_id: null, substitution_id: null, preparation: null, prep_method: null, prep_size: null, prep_state: null, notes: null }] })
  }

  return <section className="editor-card">
    <div className="section-heading-row"><div><h2>Recipe Variants</h2><p>Named alternatives inherit the base Recipe except for fields you override here.</p></div><button type="button" onClick={() => { setEditingId('new'); setDraft(blankVariant(variants.data?.length ?? 0)) }}>Add variant</button></div>
    {variants.error instanceof Error && <p className="field-error">{variants.error.message}</p>}
    <div className="recipe-ingredient-list">{variants.data?.map((variant) => <div className="recipe-ingredient-editor" key={variant.id}>
      <div className="section-heading-row"><div><strong>{variant.name}</strong><div className="muted-line">{variant.active ? 'Active' : 'Archived'} · {variant.overrides.length} override{variant.overrides.length === 1 ? '' : 's'}</div></div><div className="form-actions"><button type="button" className="button-secondary" onClick={() => { setEditingId(variant.id); setDraft(toInput(variant)) }}>Edit</button>{variant.active && <button type="button" className="button-secondary" onClick={() => archive.mutate(variant.id)}>Archive</button>}</div></div>
      {variant.notes && <p>{variant.notes}</p>}
      {variant.overrides.map((override) => { const row = recipe.ingredients.find((item) => item.id === override.recipe_ingredient_id); const sub = row?.substitutions.find((item) => item.id === override.substitution_id); return <div className="muted-line" key={override.id}>{ingredientNames.get(row?.ingredient_id ?? 0) ?? 'Ingredient'}{override.quantity != null ? ` · qty ${override.quantity}` : ''}{override.unit_id != null ? ` · ${units.find((unit) => unit.id === override.unit_id)?.code ?? 'unit'}` : ''}{sub ? ` · substitute ${ingredientNames.get(sub.substitute_ingredient_id) ?? 'ingredient'}` : ''}</div> })}
    </div>)}</div>

    {editingId !== null && <div className="recipe-ingredient-editor" style={{ marginTop: 12 }}>
      <div className="editor-grid"><label>Name<input value={form.name} onChange={(event) => patch({ name: event.target.value })} /></label><label>Order<input type="number" min="0" value={form.sort_order} onChange={(event) => patch({ sort_order: Number(event.target.value) })} /></label><label className="span-2">Notes<textarea value={form.notes ?? ''} onChange={(event) => patch({ notes: event.target.value || null })} /></label><label className="checkbox-label"><input type="checkbox" checked={form.active} onChange={(event) => patch({ active: event.target.checked })} />Active</label></div>
      <div className="section-heading-row"><h3>Ingredient overrides</h3><button type="button" className="button-secondary" disabled={form.overrides.length >= recipe.ingredients.length} onClick={addOverride}>Add override</button></div>
      <div className="recipe-ingredient-list">{form.overrides.map((override, index) => { const base = recipe.ingredients.find((item) => item.id === override.recipe_ingredient_id); const used = new Set(form.overrides.filter((_item, current) => current !== index).map((item) => item.recipe_ingredient_id)); return <div className="recipe-ingredient-editor" key={`${override.recipe_ingredient_id}-${index}`}>
        <div className="editor-grid"><label>Base ingredient<select value={override.recipe_ingredient_id} onChange={(event) => patchOverride(index, { recipe_ingredient_id: Number(event.target.value), substitution_id: null })}>{recipe.ingredients.filter((item) => item.id === override.recipe_ingredient_id || !used.has(item.id)).map((item) => <option key={item.id} value={item.id}>{ingredientNames.get(item.ingredient_id) ?? `Ingredient #${item.ingredient_id}`}</option>)}</select></label><label>Quantity override<input type="number" min="0" step="0.001" placeholder={base?.quantity ?? ''} value={override.quantity ?? ''} onChange={(event) => patchOverride(index, { quantity: event.target.value || null })} /></label><label>Unit override<select value={override.unit_id ?? ''} onChange={(event) => patchOverride(index, { unit_id: event.target.value ? Number(event.target.value) : null })}><option value="">Inherit ({units.find((unit) => unit.id === base?.unit_id)?.code ?? 'unit'})</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label><label>Substitution<select value={override.substitution_id ?? ''} onChange={(event) => patchOverride(index, { substitution_id: event.target.value ? Number(event.target.value) : null })}><option value="">Inherit preferred/canonical</option>{base?.substitutions.map((sub) => <option key={sub.id} value={sub.id}>{ingredientNames.get(sub.substitute_ingredient_id) ?? `Ingredient #${sub.substitute_ingredient_id}`}</option>)}</select></label><label>Prep method<input value={override.prep_method ?? ''} onChange={(event) => patchOverride(index, { prep_method: event.target.value || null })} /></label><label>Prep size<input value={override.prep_size ?? ''} onChange={(event) => patchOverride(index, { prep_size: event.target.value || null })} /></label><label>Prep state<input value={override.prep_state ?? ''} onChange={(event) => patchOverride(index, { prep_state: event.target.value || null })} /></label><label>Preparation<input value={override.preparation ?? ''} onChange={(event) => patchOverride(index, { preparation: event.target.value || null })} /></label><label className="span-2">Override notes<input value={override.notes ?? ''} onChange={(event) => patchOverride(index, { notes: event.target.value || null })} /></label></div>
        <button type="button" className="button-secondary" onClick={() => patch({ overrides: form.overrides.filter((_item, current) => current !== index) })}>Remove override</button>
      </div> })}</div>
      {save.error instanceof Error && <p className="field-error">{save.error.message}</p>}
      <div className="form-actions"><button type="button" disabled={save.isPending || !form.name.trim()} onClick={() => save.mutate()}>Save variant</button><button type="button" className="button-secondary" onClick={() => { setEditingId(null); setDraft(null) }}>Cancel</button></div>
    </div>}

    {activeVariants.length > 0 && <div className="recipe-ingredient-editor" style={{ marginTop: 12 }}><h3>Variant serving preview</h3><div className="editor-grid"><label>Variant<select value={previewVariantId ?? ''} onChange={(event) => setPreviewVariantId(event.target.value ? Number(event.target.value) : null)}><option value="">Base Recipe</option>{activeVariants.map((variant) => <option key={variant.id} value={variant.id}>{variant.name}</option>)}</select></label><label>Requested servings<input type="number" min="0.1" step="0.1" value={previewServings} onChange={(event) => setPreviewServings(event.target.value)} /></label></div><button type="button" onClick={() => preview.mutate()}>Preview variant</button>{preview.error instanceof Error && <p className="field-error">{preview.error.message}</p>}{preview.data && <div className="recipe-ingredient-list" style={{ marginTop: 12 }}>{preview.data.ingredients.map((item) => <div className="muted-line" key={item.recipe_ingredient_id}><strong>{ingredientNames.get(item.ingredient_id) ?? `Ingredient #${item.ingredient_id}`}</strong> · {item.quantity} {item.unit_code}{item.prep_method ? ` · ${item.prep_method}` : ''}{item.manual_review ? ' · Manual review' : ''}</div>)}</div>}</div>}
  </section>
}
