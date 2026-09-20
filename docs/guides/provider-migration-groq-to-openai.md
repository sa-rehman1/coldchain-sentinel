# Provider migration: Groq to OpenAI

Change only provider configuration: set the provider identifier, OpenAI-compatible base URL, API-key environment-variable name, supported model, billing mode, and safety limits. Supply the new secret only through the runtime environment. Do not alter domain types, SOPs, retrieval, persistence, governance, approval, or API logic. Run mocked contract tests first and add any provider-specific live smoke test as explicit opt-in. This milestone does not call the official OpenAI API.
