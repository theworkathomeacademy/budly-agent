# V.I.B.E.™ — Voice Interactive Behavior Engine (Backlog Record)

**Authority:** Authorized by Project Owner d-mac  
**Status:** **BACKLOGGED / RESEARCH PRESERVED**  
**Archival Date:** 2026-09-23  
**Governance Authority:** Google Drive $\rightarrow$ `BROS` $\rightarrow$ `VIBE`  
**Git Archival Branch:** `archive/vibe-backlog-20260923`  

---

## 1. Project Objective

The Voice Interactive Behavior Engine (V.I.B.E.™) initiative was designed to provide a completely local, self-hosted, deterministic, multi-voice interactive speech synthesis engine for Budly. The goal was to enable natural, conversational voice output with $0 paid API dependencies, 100% offline isolation, and future support for a canonical Project Owner voice (`budly-primary`) once the underlying engine proved customer-ready.

---

## 2. Archival Decision & Rationale

V.I.B.E. has been formally transitioned to **BACKLOGGED / RESEARCH PRESERVED**.

### Why Backlogged:
1. **CPU Synthesis Latency Ceiling for Diffusion/CFM**: While Kokoro ONNX achieved sub-second sentence chunks (~0.45x RTF), high-fidelity zero-shot cloning with reference audio (Chatterbox Turbo) remains CPU-bound at ~2.7x–2.9x RTF (12s–105s per turn), requiring substantial compute resources or dedicated hardware acceleration for conversational voice cloning.
2. **Phase Priority Alignment**: Commercial priority is currently focused on the Budly text conversational experience, product catalog knowledge fidelity, and core conversion spine integrations.
3. **No Project Owner Voice Contamination**: The Project Owner's canonical voice was **never recorded or ingested**, preserving complete voice privacy and avoiding premature voice commitments.

---

## 3. Major Successful Experiments & Proven Capabilities

1. **VIBE-POC-001 (Offline Synthesis Proof)**:
   - Successfully proved offline PyTorch synthesis using local weights on an isolated CPU runtime.
2. **VIBE-SEC-001 (Security & Isolation Controls)**:
   - Implemented and verified Windows Firewall outbound block rules for the Python runtime.
   - Configured NTFS encrypted vault permissions and automated SHA-256 asset quarantine verification (`quarantine_voice_asset.py`).
3. **VIBE-ENGINE-001 (Multi-Voice Deterministic Routing)**:
   - Verified immutable voice registry schema (`voices/registry.json`), deterministic profile switching, and strict protection preventing assignment to `budly-primary`.
4. **VIBE-PERF-001 (Streaming Chunked Playback & Latency Optimization)**:
   - Slashed Time-to-First-Audio (TTFA) from 115s down to **2.60s** via real-time sentence chunking.
   - Built seamless audio queue with **0.000s audio gap** (+1.87s buffer lead).
   - Diagnosed and resolved mobile audio delivery blockers (user gesture token timeout vs fast chunk delivery).
   - Implemented unified `VIBEEngineRouter` integrating both Kokoro ONNX (fast runtime) and Chatterbox Turbo (offline clone).
5. **Conversational Flow Remediation**:
   - Integrated the real production conversational runtime (`ProductionConversationRuntime`), eliminating generic response loops and establishing dynamic, personalized Budly dialog.

---

## 4. Known Unresolved Defects & Limitations

1. **Chatterbox CPU Speed**: Reference-conditioned voice cloning takes 12s–105s on CPU, making interactive cloning unsuitable without GPU/NPU acceleration.
2. **Phonemizer Warning on Specific Contractions**: Certain slang or punctuation combinations trigger minor phonemizer count mismatch warnings (non-fatal, but logged).
3. **Dual-Model Memory Footprint**: Keeping both Kokoro and Chatterbox resident in RAM consumes ~4.3 GB RAM.

---

## 5. Reactivation Conditions & Gates

Reactivation of V.I.B.E. development requires explicit authorization by Project Owner `d-mac` and the satisfaction of the following gates:

1. **Hardware / Compute Acceleration Gate**: Provisioning of dedicated local GPU/NPU compute capable of sub-second zero-shot voice cloning.
2. **Commercial Priority Gate**: Formal scheduling following Phase 3/4 conversion milestones.
3. **Canonical Voice Collection Gate**: Explicit, separate authorization before recording or ingesting Project Owner reference audio for `budly-primary`.

---

## 6. Canonical Documentation Hierarchy

Governance and strategic architecture records are maintained in Google Drive:
- `Google Drive` $\rightarrow$ `BROS` $\rightarrow$ `VIBE`
  - `VIBE Backlog & Reactivation Record v1.0`
  - `VIBE-001 Discovery, Prototype & Test Record v1.0`
  - `VIBE-002 Fully Self-Hosted Natural Voice Architecture & Future Roadmap v0.1`

*This repository archive preserves the complete codebase, test fixtures, benchmarks, and integration bridges for immediate restoration upon reactivation.*
