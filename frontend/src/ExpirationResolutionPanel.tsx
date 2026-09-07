import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assignDirectRecipe, assignPlannedMeal, assignProducedSource, fetchExpirationResolutions, fetchProducedSourceOptions, movePlannedMeal, type ExpirationResolutionAction } from './mealCyclesApi'

async function freezeLot(lotId: number, freezerLocationId: number): Promise<void> {
  const response = await fetch(`/api/inventory/${lotId}/freeze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ freezer_location_id: freezerLocationId, note: 'Expiration resolution: frozen from Use Soon' }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Freeze request failed: ${response.status}`)
  }
}

function actionLabel(action: ExpirationResolutionAction): string {
  if (action.kind === 'MOVE_EXISTING') return `Apply move to Day ${action.target_day_number}`
  if (action.kind === 'PLAN_MEAL') return `Plan Meal on Day ${action.target_day_number}`
  if (action.kind === 'PLAN_RECIPE') return `Plan Recipe on Day ${action.target_day_number}`
  if (action.kind === 'PLAN_PRODUCED') return `Plan produced stock on Day ${action.target_day_number}`
  return `Freeze in ${action.freezer_location_name ?? 'Freezer'}`
}

export default function ExpirationResolutionPanel({ cycleId }: { cycleId: number }) {
  const queryClient = useQueryClient()
  const resolutions = useQuery({
    queryKey: ['expiration-resolutions', cycleId, 7],
    queryFn: () => fetchExpirationResolutions(cycleId, 7),
    refetchInterval: 5_000,
  })
  const produced = useQuery({ queryKey: ['produced-source-options'], queryFn: fetchProducedSourceOptions })

  const apply = useMutation({
    mutationFn: async ({ lotId, action }: { lotId: number; action: ExpirationResolutionAction }) => {
      if (action.kind === 'MOVE_EXISTING') {
        if (!action.source_slot_id || !action.target_slot_id) throw new Error('Move suggestion is missing slot provenance')
        return movePlannedMeal(cycleId, action.source_slot_id, action.target_slot_id)
      }
      if (action.kind === 'PLAN_MEAL') {
        if (!action.meal_id || !action.target_slot_id) throw new Error('Meal suggestion is missing placement provenance')
        return assignPlannedMeal(cycleId, action.target_slot_id, action.meal_id)
      }
      if (action.kind === 'PLAN_RECIPE') {
        if (!action.recipe_id || !action.target_slot_id || !action.planned_servings) throw new Error('Recipe suggestion is missing placement provenance')
        return assignDirectRecipe(cycleId, action.target_slot_id, action.recipe_id, action.planned_servings)
      }
      if (action.kind === 'PLAN_PRODUCED') {
        if (!action.target_slot_id || !action.quantity) throw new Error('Produced-stock suggestion is missing placement provenance')
        const option = produced.data?.find((row) => row.lot_id === lotId)
        if (!option) throw new Error('Produced-stock source is no longer available')
        return assignProducedSource(cycleId, action.target_slot_id, option, action.quantity)
      }
      if (!action.freezer_location_id) throw new Error('Freeze suggestion is missing Freezer provenance')
      await freezeLot(lotId, action.freezer_location_id)
      return null
    },
    onSuccess: async () => {
      const keys: unknown[][] = [
        ['expiration-resolutions'], ['dashboard-use-soon'], ['meal-cycles'], ['meal-cycle', cycleId],
        ['expiration-suggestions', cycleId], ['cycle-validation', cycleId], ['shopping-list', cycleId],
        ['inventory'], ['inventory-availability'], ['production-inventory-availability'], ['produced-source-options'],
        ['dashboard'], ['dashboard-alerts'],
      ]
      await Promise.all(keys.map((queryKey) => queryClient.invalidateQueries({ queryKey })))
    },
  })

  if (resolutions.isPending) return <p className="muted-line">Loading expiration resolutions…</p>
  if (resolutions.error instanceof Error) return <div className="error-banner">{resolutions.error.message}</div>

  return <>
    {apply.error instanceof Error && <div className="error-banner">{apply.error.message}</div>}
    {resolutions.data?.resolutions.map((row) => <div className="inventory-history-row" key={`resolution-${row.source_type}-${row.lot_id}`}>
      <strong>{row.days_remaining === 0 ? 'Use today' : row.days_remaining === 1 ? '1 day left' : `${row.days_remaining} days left`} · {row.source_name}</strong>
      <span>{row.source_type === 'INGREDIENT' ? 'Ingredient' : row.source_type === 'LEFTOVER' ? 'Leftover' : 'Recipe output'} · Lot {row.lot_id}</span>
      <span>{row.available_quantity} {row.unit_code} available · {row.location_name} · Expires {row.expiration_date}</span>
      {row.status === 'NO_SUGGESTION' && <span className="planning-note">No suggestion: {row.no_suggestion_reason}</span>}
      {row.actions.map((action, index) => <div className="expiration-action" key={`${row.lot_id}-${action.kind}-${index}`}>
        <strong>#{index + 1} · {action.title}</strong>
        <span>{action.detail}</span>
        <button type="button" className="button-secondary" disabled={apply.isPending} onClick={() => apply.mutate({ lotId: row.lot_id, action })}>
          {apply.isPending ? 'Applying…' : actionLabel(action)}
        </button>
      </div>)}
    </div>)}
    {resolutions.data?.resolutions.length === 0 && <p className="muted-line">No available Inventory expires within the next 7 days.</p>}
  </>
}
