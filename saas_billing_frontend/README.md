# SaaS Billing — Frontend

React 19 + TypeScript + Vite dashboard for the SaaS Billing platform.
See the [project README](../README.md) for features, architecture and setup.

```bash
npm ci
cp .env.example .env    # optional: VITE_API_BASE_URL (default http://127.0.0.1:8000/api)
npm run dev             # http://localhost:5173
npm run build           # type-check (tsc -b) + production build to dist/
npm run lint            # oxlint
```

Structure: `src/api` (typed API clients, JWT refresh in `client.ts`),
`src/context` (auth + active organization), `src/pages` (one folder per
screen), `src/utils/roles.ts` (role checks mirroring the backend permissions).
