# ColdChain Sentinel control-tower prototype

This is a deterministic, browser-only design prototype. It does not contact the FastAPI backend, infrastructure services, or an AI provider.

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The development server binds to `127.0.0.1` only.

Useful checks:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```
