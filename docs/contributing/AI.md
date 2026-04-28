# AI Policy

Hermetic accepts contributions written, edited, or assisted by
large language models. There is nothing special about an
AI-assisted patch — it must clear the same review bar as any
human-written patch:

- Tests that demonstrate the change.
- Honest documentation, including limitations.
- No new runtime dependencies.
- Code that obeys the existing style.

This page is for contributors who use AI tools, and for users
who deploy hermetic in front of an AI agent.

## If you use AI tools to contribute

- **You are responsible for the patch.** Review the diff before
  you push. If the model wrote a guard, run the test suite —
  including `test/test_security/` — and read the bootstrap
  output by eye. Do not paste model output untouched.
- **Cite where helpful.** If a non-obvious design choice came
  from a model, mention it in the PR description so the reviewer
  can probe the reasoning. (You don't need to disclose every
  use; this is about making review easier, not surveillance.)
- **Don't import what you can't audit.** Hermetic has zero
  runtime dependencies on purpose. A model may suggest pulling
  in a library to "simplify" a guard — push back. The reason
  the guard is hand-rolled is so it keeps working when the
  ecosystem moves around it.
- **Watch for fabricated APIs.** Models routinely invent
  `socket.someplausiblemethod` or `ctypes.SafeLoad` or similar.
  If a guard targets a name you can't find in the CPython
  source, it isn't a guard.
- **Run the bootstrap.** Changes to `hermetic/guards/*.py` must
  be reflected in `hermetic/bootstrap.py` (regenerated via
  `scripts/build_bootstrap.py`). Models often forget this; the
  test suite will catch it but only if you run it.

## If you use hermetic to constrain an AI agent

This is one of hermetic's intended use cases. A few notes:

- **Choose the right guards.** A typical agent sandbox is:
  ```
  hermetic \
      --no-network --allow-domain api.openai.com --allow-domain api.anthropic.com \
      --no-subprocess \
      --fs-readonly=./agent-workspace \
      --block-native \
      --seal \
      -- python run_agent.py
  ```
  Each flag corresponds to one capability the agent should not
  have.
- **`--seal`.** Use it for agents. Without it, an agent that
  inspects its environment can call `hermetic.guards.uninstall_all()`
  and reverse the policy. With it, the policy is one-way.
- **`--trace`.** Useful for debugging agent behavior — every
  blocked call appears on stderr with a clear reason. Pipe it
  to a log file for incident review.
- **Hermetic is not enough.** If the agent is hostile or
  Anthropic-grade-capable in a security sense, run it inside a
  container, a VM, or `gVisor` *as well*. Hermetic gives you
  fast feedback at the Python layer; OS-level isolation gives
  you the actual security boundary. See [Threat
  Model](../threat-model.md).
- **Capability passing beats sandboxing.** Where you can,
  give the agent the *result* it needs (a fetched document,
  a database row), not the *capability* to fetch it. Then
  hermetic just enforces the obvious "no other capabilities"
  rule.

## What this project will not do

- Add a "trusted-LLM" allow-list. There is no such thing.
- Add a heuristic that tries to detect "looks like agent
  behavior" and apply different rules. Policy stays simple
  and explicit.
- Promise that a sealed hermetic process will resist a model
  that can write `.so` files, escape via `gc`, or otherwise
  reach the assumptions in the [Threat
  Model](../threat-model.md). It won't.

If you see hermetic being marketed as "AI-safe", flag it. The
honest framing is "loud failures for poorly-behaved agents,
paired with a real sandbox for hostile ones".
