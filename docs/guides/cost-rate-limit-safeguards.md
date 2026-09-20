# Cost and rate-limit safeguards

Live calls default off and require a nonempty environment key. Input and output are bounded; there are no batch, startup, health, ingestion, CI, or default-test calls. One live attempt is allowed per demo incident, with one bounded retry only for network, 429, or server failure. `Retry-After` is capped, circuit opening temporarily disables the provider, and deterministic fallback remains available. Free-tier cost metadata is configuration-derived and must not be interpreted as verified account billing.
