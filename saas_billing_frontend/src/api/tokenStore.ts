/*
 * The access token lives only in memory (a module variable), never in
 * localStorage, so injected scripts cannot read a stored copy. It is
 * short-lived (15 min); after a reload the app gets a new one from the
 * httpOnly refresh cookie via /auth/token/refresh/.
 */

let accessToken: string | null = null;

export const getAccessToken = () => accessToken;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

// Tokens were kept in localStorage before; remove leftovers once.
export const clearLegacyStoredTokens = () => {
  try {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  } catch {
    // Storage unavailable (private mode): nothing to clean.
  }
};
