# Security Policy

This is a small, non-commercial practice/portfolio project. It has no
production deployment and does not process real user or patient data.

## Reporting a Vulnerability

If you find a security issue (e.g. a way to make the Executor run arbitrary
code, bypass the action whitelist, or leak an API key), please open a
private report via GitHub's "Report a vulnerability" feature on this
repository, or open an issue without including exploit details.

## Design notes relevant to security

- The `SafeExecutor` only ever calls a fixed, whitelisted set of
  `ToyRobotEnv` methods (see `src/geniac_cap/execution/validation.py`). It
  never calls `exec()` or `eval()` on planner output.
- No API key is ever hardcoded in source. `OPENAI_API_KEY` /
  `ANTHROPIC_API_KEY` are read only from environment variables (see
  `.env.example`) and are not required to run anything in this version.
- `.gitignore` excludes `.env` and generated result files containing
  potentially sensitive run data.
