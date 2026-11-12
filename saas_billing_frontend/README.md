# SaaS Billing — Frontend

React 19 + TypeScript + Vite dashboard for the SaaS Billing platform.
See the [project README](../README.md) for features, architecture and setup.

```bash
npm ci
cp .env.example .env    # optional: VITE_API_BASE_URL (default /api, proxied to Django by Vite)
npm run dev             # http://localhost:5173
npm run build           # type-check (tsc -b) + production build to dist/
npm run lint            # oxlint
npm test                # Vitest + Testing Library
```

Structure: `src/api` (typed API clients, JWT refresh in `client.ts`),
`src/context` (auth + active organization), `src/pages` (one folder per
screen), `src/utils/roles.ts` (role checks mirroring the backend permissions).
