# Optional OpenAI provider setup

OpenAI is optional. ColdChain Sentinel defaults to the deterministic local provider, and live
provider calls default to disabled. The shared server-side adapter uses Chat Completions with strict
Structured Outputs so OpenAI returns the same eight-field advisory decision used by the Groq path.
Application code—not the model—adds expiry, identity, prompt, schema, timing, token, correlation,
validation, and fallback metadata.

## Configure locally

1. Create an API key in your OpenAI account and store it only as `OPENAI_API_KEY` in the ignored
   local `.env`. Never use a `VITE_*` variable or place the key in Compose or frontend files.
2. Set `LLM_PROVIDER=openai`.
3. Set `OPENAI_MODEL` to a current Chat Completions model that supports Structured Outputs. Confirm
   compatibility in the [official OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
   before selecting it.
4. Keep `OPENAI_BASE_URL=https://api.openai.com/v1` and `LLM_LIVE_CALLS_ENABLED=false` until a
   separately authorized smoke test or demo.

The health endpoint reads configuration only; it does not contact OpenAI. An empty key or model is
reported as unconfigured, and any provider failure returns the deterministic recommendation path.
OpenAI output is advisory and can neither approve an action nor create or execute a command.

## Future one-request smoke test

This procedure is intentionally not run as part of ordinary tests. Review current pricing and set a
small account budget first. In a PowerShell process, obtain explicit authorization for one request,
then run:

```powershell
$env:OPENAI_API_KEY = '<set locally; do not print>'
$env:OPENAI_MODEL = '<verified structured-output model ID>'
$env:RUN_LIVE_OPENAI_SMOKE = 'true'
uv run pytest tests/live/test_openai_smoke.py -q --no-cov
Remove-Item Env:RUN_LIVE_OPENAI_SMOKE
Remove-Item Env:OPENAI_API_KEY
Remove-Item Env:OPENAI_MODEL
```

The smoke harness disables retries, uses synthetic data, and therefore makes at most one HTTP
request. Stop immediately on failure. To disable calls immediately, keep or restore
`LLM_LIVE_CALLS_ENABLED=false` and restart the relevant local process. Revoke the key from the
OpenAI account if it may have been exposed or is no longer needed.
