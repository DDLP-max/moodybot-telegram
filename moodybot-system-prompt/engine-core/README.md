# MoodyBot Engine Architecture  
### Unified System Overview — Sections 6 & 7

This document outlines the **complete emotional response pipeline** that governs how MoodyBot interprets user input, simulates tone, selects modules, adjusts emotional intensity, and delivers final output.

It combines:

- Section 6 — 🧪 Design Process (Simulation, Rewrite, Goal Evaluation)
- Section 7 — 🎚 Emotional Modulation (Tone Scaling, Command Mapping, Filters)

Together, they form the **Core Emotional Drive System** — the equivalent of F1 telemetry + traction control.

---

## 🧠 1. Response Flow Overview

```mermaid
flowchart TD
    A[User Input] --> B[Live Simulation Loop]
    B --> C[Intent Parsing + Module Forecast]
    C --> D[Tone Stack + Format Selection]
    D --> E[Filter Activation (if needed)]
    E --> F[Draft Generated]
    F --> G[Output Goal Evaluator]
    G --> H{Meets Goal?}
    H -- Yes --> I[Deliver Output]
    H -- No --> J[Rewrite Logic]
    J --> G
