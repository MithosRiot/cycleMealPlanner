export type HealthResponse = {
  status: string
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch('/health')
  if (!response.ok) {
    throw new Error(`Backend health check failed: ${response.status}`)
  }
  return response.json() as Promise<HealthResponse>
}
