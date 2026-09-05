import type { CycleValidationIssue } from './mealCyclesApi'
import type { ShoppingItem } from './shoppingApi'

export type DashboardValidationAlert = CycleValidationIssue & { key: string }

function stableContext(context: Record<string, unknown>): string {
  return JSON.stringify(context, Object.keys(context).sort())
}

export function dashboardValidationAlerts(issues: CycleValidationIssue[]): DashboardValidationAlert[] {
  const seen = new Set<string>()
  const alerts: DashboardValidationAlert[] = []
  for (const issue of [...issues].sort((a, b) => {
    const severity = (a.severity === 'ERROR' ? 0 : 1) - (b.severity === 'ERROR' ? 0 : 1)
    if (severity !== 0) return severity
    return a.code.localeCompare(b.code) || a.message.localeCompare(b.message) || stableContext(a.context).localeCompare(stableContext(b.context))
  })) {
    const key = `${issue.severity}:${issue.code}:${issue.message}:${stableContext(issue.context)}`
    if (seen.has(key)) continue
    seen.add(key)
    alerts.push({ ...issue, key })
  }
  return alerts
}

export function dashboardShoppingShortages(items: ShoppingItem[]): ShoppingItem[] {
  return items
    .filter((item) => item.status === 'PENDING' && Number(item.generated_quantity) > 0)
    .sort((a, b) => a.shopping_category_sort_order - b.shopping_category_sort_order || a.ingredient_name.localeCompare(b.ingredient_name) || a.id - b.id)
}
