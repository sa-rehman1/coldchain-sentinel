# ColdChain Sentinel control tower

The React control tower supports `api` mode for the integrated same-origin FastAPI demo and `mock`
mode for isolated deterministic visual development. No provider credential is bundled into the
frontend. API responses are validated with Zod, mutations are never automatically retried, and API
mode never falls back to fixtures.

```powershell
$env:VITE_CONTROL_TOWER_DATA_SOURCE='mock'
npm ci
npm run dev
```

The development server binds to `127.0.0.1:5173`. The integrated Compose demo is served at
`http://127.0.0.1:4173` in `api` mode.

Useful checks:

```powershell
npm run lint
npm run typecheck
npm test -- --run
npm run build
```
