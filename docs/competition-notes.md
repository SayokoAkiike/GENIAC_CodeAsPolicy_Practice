# GENIAC-PRIZE Theme 2 — Practice Notes

> These are informal working notes for a self-study project, **not** an
> official or authoritative description of GENIAC-PRIZE. Details about the
> competition itself should always be verified against the official GENIAC
> materials rather than this document.

## Working hypothesis about Theme 2

Theme 2 is treated here, for practice purposes, as being broadly about
**Code-as-Policy (CaP) style approaches**: turning natural-language
instructions into executable robot behavior, where "executable" can mean
either structured action sequences or generated code, and where evaluation
considers both planning correctness and execution safety.

This project is a personal exercise built around that hypothesis. It is
intentionally scoped much smaller than a real competition submission would
be, so that later phases (LLM integration, VLM, simulators, CaP-X /
CaP-Bench-style evaluation) can be added incrementally on top of a working
foundation.

## What this practice project deliberately does NOT claim

- It does not claim to reproduce any official GENIAC benchmark, dataset, or
  scoring methodology.
- It does not run on any physical or simulated robot yet — the "Toy Robot
  Environment" is a simple in-memory Python model.
- It does not use any external LLM API in its default configuration.

## Open questions to revisit as the project grows

- What does the official evaluation protocol for Theme 2 actually score
  (task success only, or also code quality / safety / efficiency)?
- How should healthcare/assistive-care-adjacent tasks be scoped so they stay
  within "object transport / environment tidying" rather than anything
  resembling clinical action?
- Which simulator (if any) is worth adopting first once Phase 5 begins —
  MuJoCo vs. a 2D grid-world upgrade vs. Isaac Sim?

## Sources

Because GENIAC-PRIZE details can change over time, please check the
official GENIAC website/announcements directly rather than relying on this
file for anything time-sensitive.
