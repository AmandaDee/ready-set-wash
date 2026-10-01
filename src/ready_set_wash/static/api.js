const QUERY = `query Plan($deadline: DateTime!, $duration: Int!) {
  dashboard(deadline: $deadline, durationMinutes: $duration) {
    mode prices { start end pencePerKwh }
    plan { start end costPence nowCostPence savingsPence }
  }
}`;

export async function fetchPlan(variables) {
  const response = await fetch('/graphql', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query: QUERY, variables}),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error('Could not load prices. Please try again.');
  const payload = await response.json();
  if (payload.errors?.length) throw new Error(payload.errors[0].message);
  if (!payload.data?.dashboard) throw new Error('No price data returned.');
  return payload.data.dashboard;
}
