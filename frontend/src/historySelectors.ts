import type { InventoryHistoryEntry, MealHistoryUsage } from './historyApi'

export function inventoryHistoryName(row: InventoryHistoryEntry): string {
  return row.ingredient_name ?? row.source_name ?? row.source_type
}

export function signedQuantity(row: InventoryHistoryEntry): string {
  return `${Number(row.quantity_delta) > 0 ? '+' : ''}${row.quantity_delta} ${row.unit_code}`
}

export function usageTitle(usage: MealHistoryUsage): string {
  return `${usage.recipe_name} · ${usage.actual_ingredient_name}${usage.substituted ? ' (substitution)' : ''}`
}
