import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMealCycles } from './mealCyclesApi'
import { adjustShoppingItem, fetchShoppingList, regenerateShoppingList } from './shoppingApi'
import './ShoppingPage.css'

export default function ShoppingPage() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [cycleId, setCycleId] = useState<number | null>(null)
  const [adjustments, setAdjustments] = useState<Record<number, string>>({})
  const shopping = useQuery({
    queryKey: ['shopping-list', cycleId],
    queryFn: () => fetchShoppingList(cycleId as number),
    enabled: cycleId !== null,
    retry: false,
  })

  const regenerate = useMutation({
    mutationFn: () => regenerateShoppingList(cycleId as number),
    onSuccess: (data) => queryClient.setQueryData(['shopping-list', cycleId], data),
  })
  const adjust = useMutation({
    mutationFn: ({ itemId, value }: { itemId: number; value: string }) => adjustShoppingItem(cycleId as number, itemId, value),
    onSuccess: (data) => queryClient.setQueryData(['shopping-list', cycleId], data),
  })

  const grouped = useMemo(() => {
    const result = new Map<string, NonNullable<typeof shopping.data>['items']>()
    for (const item of shopping.data?.items ?? []) {
      const list = result.get(item.shopping_category_name) ?? []
      list.push(item)
      result.set(item.shopping_category_name, list)
    }
    return [...result.entries()]
  }, [shopping.data])

  return (
    <section className="shopping-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Inventory-aware</p>
          <h1>Shopping</h1>
          <p>Generate shortages from planned servings, then adjust what you actually want to buy.</p>
        </div>
      </header>

      <section className="settings-card shopping-toolbar">
        <label>
          Meal cycle
          <select value={cycleId ?? ''} onChange={(event) => setCycleId(event.target.value ? Number(event.target.value) : null)}>
            <option value="">Choose a cycle…</option>
            {cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
          </select>
        </label>
        <button type="button" disabled={cycleId === null || regenerate.isPending} onClick={() => regenerate.mutate()}>
          {shopping.data ? 'Regenerate list' : 'Generate list'}
        </button>
      </section>

      {cycleId !== null && shopping.isError && !regenerate.isPending && (
        <div className="empty-state shopping-empty">
          <p>No generated shopping list for this cycle yet.</p>
          <button type="button" onClick={() => regenerate.mutate()}>Generate shopping list</button>
        </div>
      )}
      {(regenerate.isError || adjust.isError) && <div className="error-banner">{((regenerate.error || adjust.error) as Error).message}</div>}

      {shopping.data && (
        <>
          <div className="shopping-summary">
            <strong>{shopping.data.meal_cycle_name}</strong>
            <span>{shopping.data.items.filter((item) => Number(item.final_quantity) > 0).length} items to buy</span>
            <span>Generated {new Date(shopping.data.generated_at).toLocaleString()}</span>
          </div>
          <div className="shopping-groups">
            {grouped.map(([category, items]) => (
              <section className="settings-card shopping-category" key={category}>
                <h2>{category}</h2>
                <div className="shopping-items">
                  {items.map((item) => (
                    <article className={Number(item.final_quantity) > 0 ? 'shopping-item' : 'shopping-item covered'} key={item.id}>
                      <div>
                        <strong>{item.ingredient_name}</strong>
                        <div className="shopping-math">
                          Need {Number(item.required_quantity).toLocaleString()} {item.unit_code} · Have {Number(item.inventory_quantity).toLocaleString()} {item.unit_code}
                        </div>
                        {item.warning && <div className="warning-text">{item.warning}</div>}
                        <details>
                          <summary>Sources</summary>
                          <ul>
                            {(JSON.parse(item.source_trace) as Array<{ day_number: number; meal_name: string; quantity: string }>).map((source, index) => (
                              <li key={`${source.day_number}-${source.meal_name}-${index}`}>Day {source.day_number}: {source.meal_name} ({source.quantity})</li>
                            ))}
                          </ul>
                        </details>
                      </div>
                      <div className="shopping-quantity">
                        <span className="generated-quantity">Generated: {Number(item.generated_quantity).toLocaleString()} {item.unit_code}</span>
                        <label>
                          Adjustment
                          <input type="number" step="0.001" value={adjustments[item.id] ?? item.adjustment_quantity} onChange={(event) => setAdjustments({ ...adjustments, [item.id]: event.target.value })} />
                        </label>
                        <button type="button" className="button-secondary" onClick={() => adjust.mutate({ itemId: item.id, value: adjustments[item.id] ?? item.adjustment_quantity })}>Save adjustment</button>
                        <strong>Buy {Number(item.final_quantity).toLocaleString()} {item.unit_code}</strong>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ))}
            {shopping.data.items.length === 0 && <div className="empty-state">This cycle has no planned ingredient requirements yet.</div>}
          </div>
        </>
      )}
    </section>
  )
}
