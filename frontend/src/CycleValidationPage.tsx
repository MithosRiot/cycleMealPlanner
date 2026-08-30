import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCycleValidation, fetchMealCycles } from './mealCyclesApi'
import './CycleValidationPage.css'

export default function CycleValidationPage() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [cycleId, setCycleId] = useState<number | null>(null)
  const validation = useQuery({
    queryKey: ['cycle-validation', cycleId],
    queryFn: () => fetchCycleValidation(cycleId as number),
    enabled: cycleId !== null,
    retry: false,
  })

  const errors = validation.data?.issues.filter((issue) => issue.severity === 'ERROR') ?? []
  const warnings = validation.data?.issues.filter((issue) => issue.severity === 'WARNING') ?? []

  return (
    <section className="validation-page">
      <header className="page-heading">
        <div><p className="eyebrow">Meal Plan</p><h1>Cycle Validation</h1><p>Check a draft cycle for missing placements, broken dependencies, shortages, unit conflicts, expiration risks, and population-rule gaps.</p></div>
      </header>

      <section className="panel validation-controls">
        <label>Cycle
          <select value={cycleId ?? ''} onChange={(event) => setCycleId(event.target.value ? Number(event.target.value) : null)}>
            <option value="">Select a cycle…</option>
            {cycles.data?.map((cycle) => <option value={cycle.id} key={cycle.id}>{cycle.name}</option>)}
          </select>
        </label>
        <button type="button" className="button-secondary" disabled={cycleId === null || validation.isFetching} onClick={() => validation.refetch()}>Run validation</button>
      </section>

      {validation.isError && <div className="error-banner">{(validation.error as Error).message}</div>}
      {validation.isPending && cycleId !== null && <p>Validating cycle…</p>}

      {validation.data && (
        <section className="panel validation-results">
          <div className="validation-summary">
            <div><strong>{validation.data.valid ? 'No blocking errors' : 'Validation failed'}</strong><span>{validation.data.meal_cycle_name}</span></div>
            <div className="validation-count error-count"><strong>{validation.data.error_count}</strong><span>Errors</span></div>
            <div className="validation-count warning-count"><strong>{validation.data.warning_count}</strong><span>Warnings</span></div>
          </div>

          {validation.data.issues.length === 0 && <div className="validation-clean">No validation issues found.</div>}

          {errors.length > 0 && <div className="validation-group"><h2>Errors</h2>{errors.map((issue, index) => <article className="validation-issue validation-error" key={`${issue.code}-${index}`}><div><strong>{issue.code.replaceAll('_', ' ')}</strong><p>{issue.message}</p></div><details><summary>Context</summary><pre>{JSON.stringify(issue.context, null, 2)}</pre></details></article>)}</div>}
          {warnings.length > 0 && <div className="validation-group"><h2>Warnings</h2>{warnings.map((issue, index) => <article className="validation-issue validation-warning" key={`${issue.code}-${index}`}><div><strong>{issue.code.replaceAll('_', ' ')}</strong><p>{issue.message}</p></div><details><summary>Context</summary><pre>{JSON.stringify(issue.context, null, 2)}</pre></details></article>)}</div>}
        </section>
      )}
    </section>
  )
}
