import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { fetchMeasurementUnits, fetchRecipes, MeasurementUnit, Recipe } from './api'
import {
  archiveRecipeOutput,
  createRecipeDependency,
  createRecipeOutput,
  deleteRecipeDependency,
  fetchAvailableOutputs,
  fetchRecipeOutputs,
  RecipeDependency,
  RecipeDependencyInput,
  RecipeOutput,
  RecipeOutputInput,
  scaleRecipeDependencies,
  updateRecipeDependency,
  updateRecipeOutput,
} from './recipeOutputsApi'

const SCALING_MODES: RecipeDependencyInput['scaling_mode'][] = ['LINEAR', 'FIXED', 'ROUND_UP', 'MANUAL']

function outputInput(value?: RecipeOutput): RecipeOutputInput {
  return value ? { name: value.name, quantity: value.quantity, unit_id: value.unit_id, notes: value.notes, active: value.active, sort_order: value.sort_order } : { name: 'Prepared output', quantity: '1', unit_id: 0, notes: null, active: true, sort_order: 0 }
}

function dependencyInput(value?: RecipeDependency): RecipeDependencyInput {
  return value ? { recipe_output_id: value.recipe_output_id, quantity: value.quantity, unit_id: value.unit_id, scaling_mode: value.scaling_mode, notes: value.notes, sort_order: value.sort_order } : { recipe_output_id: 0, quantity: '1', unit_id: 0, scaling_mode: 'LINEAR', notes: null, sort_order: 0 }
}

export default function RecipeOutputsPanel({ recipe }: { recipe: Recipe }) {
  const queryClient = useQueryClient()
  const bundle = useQuery({ queryKey: ['recipe-outputs', recipe.id], queryFn: () => fetchRecipeOutputs(recipe.id) })
  const available = useQuery({ queryKey: ['available-recipe-outputs', recipe.id], queryFn: () => fetchAvailableOutputs(recipe.id) })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const recipes = useQuery({ queryKey: ['recipes', 'output-source-names'], queryFn: () => fetchRecipes({ include_inactive: true }) })
  const recipeNames = useMemo(() => new Map((recipes.data ?? []).map((item) => [item.id, item.name])), [recipes.data])
  const outputMap = useMemo(() => new Map([...(available.data ?? []), ...(bundle.data?.outputs ?? [])].map((item) => [item.id, item])), [available.data, bundle.data])

  const [outputEditing, setOutputEditing] = useState<number | 'new' | null>(null)
  const [outputDraft, setOutputDraft] = useState<RecipeOutputInput | null>(null)
  const selectedOutput = outputEditing === 'new' ? undefined : bundle.data?.outputs.find((item) => item.id === outputEditing)
  const outputForm = outputDraft ?? outputInput(selectedOutput)

  const [dependencyEditing, setDependencyEditing] = useState<number | 'new' | null>(null)
  const [dependencyDraft, setDependencyDraft] = useState<RecipeDependencyInput | null>(null)
  const selectedDependency = dependencyEditing === 'new' ? undefined : bundle.data?.dependencies.find((item) => item.id === dependencyEditing)
  const dependencyForm = dependencyDraft ?? dependencyInput(selectedDependency)

  const [previewServings, setPreviewServings] = useState(recipe.base_servings)
  const preview = useMutation({ mutationFn: () => scaleRecipeDependencies(recipe.id, previewServings) })

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['recipe-outputs', recipe.id] })
    await queryClient.invalidateQueries({ queryKey: ['available-recipe-outputs'] })
  }

  const saveOutput = useMutation({ mutationFn: () => outputEditing === 'new' ? createRecipeOutput(recipe.id, outputForm) : updateRecipeOutput(recipe.id, outputEditing as number, outputForm), onSuccess: async () => { setOutputEditing(null); setOutputDraft(null); await refresh() } })
  const archiveOutputMutation = useMutation({ mutationFn: (id: number) => archiveRecipeOutput(recipe.id, id), onSuccess: refresh })
  const saveDependency = useMutation({ mutationFn: () => dependencyEditing === 'new' ? createRecipeDependency(recipe.id, dependencyForm) : updateRecipeDependency(recipe.id, dependencyEditing as number, dependencyForm), onSuccess: async () => { setDependencyEditing(null); setDependencyDraft(null); await refresh() } })
  const deleteDependencyMutation = useMutation({ mutationFn: (id: number) => deleteRecipeDependency(recipe.id, id), onSuccess: refresh })

  function unitOptions(currentId: number): MeasurementUnit[] { return (units.data ?? []).filter((unit) => currentId === 0 || unit.id === currentId || true) }

  return <section className="editor-card">
    <div><h2>Outputs & Dependencies</h2><p>Define reusable prepared outputs this Recipe produces and upstream prepared outputs it requires.</p></div>

    <div className="section-heading-row"><h3>Produces</h3><button type="button" onClick={() => { const firstUnit = units.data?.[0]?.id ?? 0; setOutputEditing('new'); setOutputDraft({ ...outputInput(), unit_id: firstUnit, sort_order: bundle.data?.outputs.length ?? 0 }) }}>Add output</button></div>
    <div className="recipe-ingredient-list">{bundle.data?.outputs.map((output) => <div className="recipe-ingredient-editor" key={output.id}><div className="section-heading-row"><div><strong>{output.name}</strong><div className="muted-line">{output.quantity} {units.data?.find((unit) => unit.id === output.unit_id)?.code ?? ''} · {output.active ? 'Active' : 'Archived'}</div>{output.notes && <div className="muted-line">{output.notes}</div>}</div><div className="form-actions"><button type="button" className="button-secondary" onClick={() => { setOutputEditing(output.id); setOutputDraft(outputInput(output)) }}>Edit</button>{output.active && <button type="button" className="button-secondary" onClick={() => archiveOutputMutation.mutate(output.id)}>Archive</button>}</div></div></div>)}</div>
    {outputEditing !== null && <div className="recipe-ingredient-editor" style={{ marginTop: 12 }}><div className="editor-grid"><label>Name<input value={outputForm.name} onChange={(event) => setOutputDraft({ ...outputForm, name: event.target.value })} /></label><label>Quantity<input type="number" min="0.000001" step="0.001" value={outputForm.quantity} onChange={(event) => setOutputDraft({ ...outputForm, quantity: event.target.value })} /></label><label>Unit<select value={outputForm.unit_id} onChange={(event) => setOutputDraft({ ...outputForm, unit_id: Number(event.target.value) })}>{unitOptions(outputForm.unit_id).map((unit) => <option key={unit.id} value={unit.id}>{unit.code} — {unit.name}</option>)}</select></label><label>Order<input type="number" min="0" value={outputForm.sort_order} onChange={(event) => setOutputDraft({ ...outputForm, sort_order: Number(event.target.value) })} /></label><label className="span-2">Notes<textarea value={outputForm.notes ?? ''} onChange={(event) => setOutputDraft({ ...outputForm, notes: event.target.value || null })} /></label><label className="checkbox-label"><input type="checkbox" checked={outputForm.active} onChange={(event) => setOutputDraft({ ...outputForm, active: event.target.checked })} />Active</label></div>{saveOutput.error instanceof Error && <p className="field-error">{saveOutput.error.message}</p>}<div className="form-actions"><button type="button" disabled={!outputForm.name.trim() || outputForm.unit_id === 0 || saveOutput.isPending} onClick={() => saveOutput.mutate()}>Save output</button><button type="button" className="button-secondary" onClick={() => { setOutputEditing(null); setOutputDraft(null) }}>Cancel</button></div></div>}

    <div className="section-heading-row" style={{ marginTop: 20 }}><h3>Requires</h3><button type="button" disabled={!available.data?.length} onClick={() => { const candidate = available.data?.[0]; if (!candidate) return; setDependencyEditing('new'); setDependencyDraft({ ...dependencyInput(), recipe_output_id: candidate.id, unit_id: candidate.unit_id, sort_order: bundle.data?.dependencies.length ?? 0 }) }}>Add dependency</button></div>
    <div className="recipe-ingredient-list">{bundle.data?.dependencies.map((dependency) => { const output = outputMap.get(dependency.recipe_output_id); return <div className="recipe-ingredient-editor" key={dependency.id}><div className="section-heading-row"><div><strong>{recipeNames.get(output?.recipe_id ?? 0) ?? 'Recipe'} → {output?.name ?? 'Output'}</strong><div className="muted-line">{dependency.quantity} {units.data?.find((unit) => unit.id === dependency.unit_id)?.code ?? ''} · {dependency.scaling_mode}</div>{dependency.notes && <div className="muted-line">{dependency.notes}</div>}</div><div className="form-actions"><button type="button" className="button-secondary" onClick={() => { setDependencyEditing(dependency.id); setDependencyDraft(dependencyInput(dependency)) }}>Edit</button><button type="button" className="button-secondary" onClick={() => deleteDependencyMutation.mutate(dependency.id)}>Remove</button></div></div></div> })}</div>
    {dependencyEditing !== null && <div className="recipe-ingredient-editor" style={{ marginTop: 12 }}><div className="editor-grid"><label>Required output<select value={dependencyForm.recipe_output_id} onChange={(event) => { const output = available.data?.find((item) => item.id === Number(event.target.value)); setDependencyDraft({ ...dependencyForm, recipe_output_id: Number(event.target.value), unit_id: output?.unit_id ?? dependencyForm.unit_id }) }}>{available.data?.map((output) => <option key={output.id} value={output.id}>{recipeNames.get(output.recipe_id) ?? 'Recipe'} → {output.name}</option>)}</select></label><label>Quantity<input type="number" min="0.000001" step="0.001" value={dependencyForm.quantity} onChange={(event) => setDependencyDraft({ ...dependencyForm, quantity: event.target.value })} /></label><label>Unit<select value={dependencyForm.unit_id} onChange={(event) => setDependencyDraft({ ...dependencyForm, unit_id: Number(event.target.value) })}>{units.data?.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label><label>Scaling<select value={dependencyForm.scaling_mode} onChange={(event) => setDependencyDraft({ ...dependencyForm, scaling_mode: event.target.value as RecipeDependencyInput['scaling_mode'] })}>{SCALING_MODES.map((mode) => <option key={mode} value={mode}>{mode}</option>)}</select></label><label>Order<input type="number" min="0" value={dependencyForm.sort_order} onChange={(event) => setDependencyDraft({ ...dependencyForm, sort_order: Number(event.target.value) })} /></label><label className="span-2">Notes<textarea value={dependencyForm.notes ?? ''} onChange={(event) => setDependencyDraft({ ...dependencyForm, notes: event.target.value || null })} /></label></div>{saveDependency.error instanceof Error && <p className="field-error">{saveDependency.error.message}</p>}<div className="form-actions"><button type="button" disabled={dependencyForm.recipe_output_id === 0 || dependencyForm.unit_id === 0 || saveDependency.isPending} onClick={() => saveDependency.mutate()}>Save dependency</button><button type="button" className="button-secondary" onClick={() => { setDependencyEditing(null); setDependencyDraft(null) }}>Cancel</button></div></div>}

    {(bundle.data?.dependencies.length ?? 0) > 0 && <div className="recipe-ingredient-editor" style={{ marginTop: 20 }}><h3>Dependency serving preview</h3><div className="editor-grid"><label>Requested servings<input type="number" min="0.1" step="0.1" value={previewServings} onChange={(event) => setPreviewServings(event.target.value)} /></label></div><button type="button" onClick={() => preview.mutate()}>Preview dependencies</button>{preview.error instanceof Error && <p className="field-error">{preview.error.message}</p>}{preview.data && <div className="recipe-ingredient-list" style={{ marginTop: 12 }}>{preview.data.dependencies.map((row) => <div className="muted-line" key={row.dependency_id}><strong>{recipeNames.get(row.source_recipe_id) ?? 'Recipe'} → {row.output_name}</strong> · {row.quantity} {row.unit_code} · {row.scaling_mode}{row.manual_review ? ' · Manual review' : ''}</div>)}</div>}</div>}
  </section>
}
