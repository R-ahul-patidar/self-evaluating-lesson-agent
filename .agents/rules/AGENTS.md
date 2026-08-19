# Self-Evaluating Lesson Agent — Project Rules

These rules apply to all AI agents working on this codebase.

## Architecture Rules

1. **Topic is data, not code.** Never write `if topic == "RAG"` in workflow or agent logic.
   The topic flows through state; rubric and reference are configurable per topic.

2. **Generator and Evaluator are SEPARATE agents.** The evaluator must NOT have access
   to the generator's internal prompt logic. Independence is what makes the quality gate meaningful.

3. **All prompts live in `src/prompts/`.** No prompt strings in `routes.py`, `nodes.py`,
   or agent files. Always import from the prompts module.

4. **No business logic in route handlers.** `routes.py` validates input and dispatches —
   all workflow logic is in `src/graph/` and `src/agents/`.

5. **Evaluator temperature = 0.** Deterministic evaluation. Do not change this.

6. **MAX_RETRIES is enforced.** The workflow MUST always terminate. Never add `while True`
   or recursion without a bounded exit condition.

7. **FAISS index is cached to disk.** Do not rebuild on every request. Staleness is detected
   by `ref_mtime` in the metadata JSON.

## Code Style Rules

8. **Pydantic for all data contracts.** Use `BaseModel` for API schemas, evaluator output,
   memory records, and run results. No raw dicts crossing module boundaries.

9. **Typed state only.** All LangGraph state must use `AgentState` TypedDict. No ad-hoc
   keys added outside of `state.py`.

10. **Node functions return partial dicts.** Each node returns ONLY the keys it updates.
    LangGraph merges — do not return the full state.

11. **Imports are absolute.** Always use `from src.x.y import z` — not relative imports.

## Security Rules

12. **Never commit `.env`.** `.gitignore` must always exclude `.env`.

13. **No hard-coded API keys or model names in business logic.** All configuration comes
    from `src/config.py` via pydantic-settings.

14. **Never expose stack traces to users.** FastAPI routes must catch all exceptions and
    return clean error messages.

## Testing Rules

15. **All LLM calls are mocked in unit tests.** Use `@patch("src.agents.evaluator.ChatGoogleGenerativeAI")`.
    Unit tests must work without a Gemini API key.

16. **Use temp databases in memory tests.** Never write to `output/memory.db` in tests.
    Use `tempfile.mktemp()` and patch `DB_PATH`.

17. **Tests must cover all 9 assessment requirements.** See `tests/` for the full list.
    Do not delete any existing test.

## UI Rules

18. **No React/Vue/Angular.** Frontend is Jinja2 + HTML5 + CSS3 + Vanilla JS only.

19. **No business logic in JavaScript.** `app.js` handles: form submission, polling,
    DOM updates, copy/download. Nothing else.

20. **Polling interval is 2 seconds.** Do not reduce below 1s (rate limiting risk).
    Do not exceed 5s (poor UX for the demo).
