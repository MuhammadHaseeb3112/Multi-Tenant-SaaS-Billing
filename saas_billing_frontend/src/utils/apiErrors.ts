/**
 * First human-readable message in a DRF error response:
 * {"detail": "..."} or {"field": ["...", ...]}.
 */
export function firstApiError(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: unknown } })?.response?.data;

  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;

    const first = Object.values(data as Record<string, unknown>)
      .flat()
      .find((value) => typeof value === "string");
    if (typeof first === "string") return first;
  }

  return fallback;
}
