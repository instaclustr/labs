[Task 4: Orchestrator Expert](../tasks/orchestrator-agent.md)

## Troubleshooting reference

| Symptom | Check and next action |
|---|---|
| Compose rejects a duplicate environment key | Retain one declaration each of `USE_EXTERNAL_ORCH_AI` and `USE_EXTERNAL_LLM_AI` in `lab.environment`, preserving their values. See Step 1. |
| `src.host_agent` cannot be imported | Re-enter the Orchestrator package containing `Makefile` and `src/host_agent`. Check the numbered workshop directory versus the archive's `orchestrator_agent` directory. |
| Printed model settings differ between terminals | Compare their selected settings and inherited exports. Restore the Task 1 profile, then restart the affected service. |
| Agent Card cannot be reached | Confirm the existing expert process is running and the configured base URL is reachable inside `lab`. Return to its earlier task for dependency diagnosis. |
| Discovery succeeds but a later task fails | A card describes an interface, not downstream readiness. Inspect the expert status/warnings and its existing process logs. |
| Host cannot reach port `10000` | The supplied Compose file does not publish that port. Run this task's probe inside `lab`. |
| `/health` or `/v1/models` returns `404` | Those routes do not exist in this Orchestrator. Use the POST input-contract probe in Step 6. |
| Expected validation probe returns `400` | This is success for the deliberately empty user message. Check `error.code` is `missing_user_message`. |
| Planner/completion fallback warning appears | Inspect the relevant model trace and service log for a schema, policy, parameter, authorization, or timeout failure. A deterministic fallback is not proof the model call succeeded. |
| Model provider rejects the token budget or parameters | Inspect the effective model profile and recorded error. Keep the validated profile; do not disable governance to hide provider incompatibility. |
| An initial single-expert route ends with two experts | Inspect the completion decision and actual delegate list. The current additional-call gate enforces budget/non-repetition, not a separate deterministic relevance check. |
| Combined response contains separate sections | Inspect `synthesis.attempts`, `error_type`, citation sets, and `outcome`. Separate-section fallback can preserve results when synthesis fails. |
| A well-cited answer contains an unsupported statement | Citation membership is not semantic verification. Inspect the underlying expert evidence and acknowledge the verifier's limits. |
| Audit verification reports valid but no record exists | Check the configured path and `records` count. Missing files are treated as empty valid chains; the HTTP rejection probe writes no record. |
| Audit verification or append fails | Preserve the file and inspect permissions, disk space, and corruption. Do not alter the active chain or disable release checks as a repair. |
| Audit records disappear after container replacement | The supplied Compose configuration has no persistent audit mount for `lab`. Container replacement does not preserve that local demonstration state. |
| `make test` finds no tests | The supplied archive has no Orchestrator `tests/` directory, development requirements file, or `.env.example`, despite references in the technical overview. The local exercises here do not require those files. |

