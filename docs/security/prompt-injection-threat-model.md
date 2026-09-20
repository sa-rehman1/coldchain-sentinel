# Prompt-injection threat model

Retrieved SOP text is untrusted data. Threats include embedded role changes, requests to ignore restrictions, fabricated citations, authorization claims, direct-execution commands, policy changes, and attempts to disclose secrets or hidden reasoning.

Controls are immutable system restrictions, explicit context delimiters, closed action enums, `extra=forbid`, citation allowlists, incident-evidence allowlists, expiry checks, evidence-sufficiency checks, content rejection, bounded input/output, no secret in prompts, deterministic governance re-evaluation, dispatcher approval, kill-switch enforcement, and deterministic fallback. Malicious fixtures exercise “ignore previous,” fabricated evidence, execution, and kill-switch override language.
