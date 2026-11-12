/**
 * Poll `load` until `isReady` accepts its result, or give up.
 *
 * Stripe confirms plan changes and checkouts through a webhook that
 * lands a moment after our own request returns. Polling for a few
 * seconds lets the page show the new state without a manual refresh.
 * Returns the last value loaded (ready or not), or null if every
 * attempt failed.
 */
export async function waitFor<T>(
  load: () => Promise<T>,
  isReady: (value: T) => boolean,
  { attempts = 8, delayMs = 1000 } = {},
): Promise<T | null> {
  let latest: T | null = null;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      latest = await load();

      if (isReady(latest)) {
        return latest;
      }
    } catch {
      // A failed attempt is retried like a not-ready one.
    }

    if (attempt < attempts - 1) {
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
  }

  return latest;
}
