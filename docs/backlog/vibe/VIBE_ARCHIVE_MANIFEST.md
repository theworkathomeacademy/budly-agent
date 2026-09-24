# V.I.B.E.™ — Archive Manifest & Index

**Initiative:** Voice Interactive Behavior Engine (V.I.B.E.™)  
**Authority:** Project Owner d-mac  
**Status:** BACKLOGGED / RESEARCH PRESERVED  
**Date:** 2026-09-23  
**Archive Branch:** `archive/vibe-backlog-20260923`  
**NAS Archive Location:** `B:\99 - Archive\VIBE-ARCHIVE\2026-09-23-backlog\` (`\\cccultivate.taild80aeb.ts.net\Budly\99 - Archive\VIBE-ARCHIVE\2026-09-23-backlog\`)  
**Local Archive Location:** `C:\Users\19196\Documents\VIBE-ARCHIVE\VIBE-BACKLOG-20260923.zip`  

---

## 1. Inventory of Archived Components

### A. Source Code & Bridges
| Path / File | Purpose / Role |
| :--- | :--- |
| `src/vibe_engine_router.py` | Unified multi-engine router supporting Kokoro ONNX and Chatterbox Turbo |
| `src/web_app.py` | Budly Sales local web server with resident VIBE bridge and telemetry |
| `src/budly_runtime/production_runtime.py` | Core conversation runtime integrating real Budly intelligence |
| `web/app.js` | Frontend client with streaming audio queue, sentence chunking, Auto-Speak |
| `web/index.html` | Clean customer UI with background diagnostics |
| `web/styles.css` | Minimalist customer chat styling and voice controls |
| `C:\Users\19196\Documents\VIBE\synthesize.py` | Resident Chatterbox Turbo synthesis engine |
| `C:\Users\19196\Documents\VIBE\voice_registry.py` | Voice profile registry management and validation |
| `C:\Users\19196\Documents\VIBE\register_voices.py` | CLI tool for profile registration and reference hashing |
| `C:\Users\19196\Documents\VIBE\hash_voice_asset.py` | SHA-256 asset verification utility |
| `C:\Users\19196\Documents\VIBE\quarantine_voice_asset.py` | Tamper detection and asset quarantine module |
| `C:\Users\19196\Documents\VIBE\create_test_voice_fixtures.py` | Synthetic reference audio fixture generator |

### B. Validation & Security Scripts
| Path / File | Purpose / Role |
| :--- | :--- |
| `scripts/benchmark_streaming_chunking.py` | Sentence streaming pipeline and audio gap benchmark |
| `scripts/benchmark_kokoro.py` | Kokoro ONNX CPU performance benchmarks (10w, 25w, 50w, 100w) |
| `scripts/benchmark_chatterbox_tuning.py` | Chatterbox CPU thread scaling and condition caching benchmark |
| `scripts/verify_remediation.py` | Automated multi-turn conversational and voice fidelity verifier |
| `scripts/stage_a_text_only.py` | Fast conversational quality test script |
| `scripts/stage_b_voice_performance.py` | Voice generation latency measurement script |
| `tests/test_vibe_e2e_bridge.py` | Automated end-to-end HTTP bridge regression suite |
| `C:\Users\19196\Documents\VIBE\tests\test_offline_synthesis.py` | Unit tests for offline synthesis |
| `C:\Users\19196\Documents\VIBE\tests\test_voice_registry.py` | Unit tests for voice registry schema |
| `C:\Users\19196\Documents\VIBE\tests\test_firewall_isolation.py` | Unit tests for network isolation controls |
| `C:\Users\19196\Documents\VIBE\tests\test_quarantine_tamper.py` | Unit tests for tamper detection |
| `C:\Users\19196\Documents\VIBE\tests\test_multi_voice_isolation.py` | Unit tests for voice profile isolation |
| `C:\Users\19196\Documents\VIBE\tests\test_reserved_voice_protection.py` | Unit tests verifying `budly-primary` cannot be used |

### C. Security & Firewall Controls
| Path / File | Purpose / Role |
| :--- | :--- |
| `C:\Users\19196\Documents\VIBE\setup_firewall_rule.ps1` | Windows Firewall outbound block rule generator |
| `C:\Users\19196\Documents\VIBE\remove_firewall_rule.ps1` | Firewall rule cleanup script |
| `C:\Users\19196\Documents\VIBE\docs\vault_acl_backup.txt` | NTFS ACL permission backup for secure vault |
| `C:\Users\19196\Documents\VIBE\docs\vault_acl_backup_original.txt` | Original NTFS ACL state baseline |

### D. Validation Records & Documentation
| Path / File | Purpose / Role |
| :--- | :--- |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-POC-001-installation-record.md` | POC installation and proof record |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-SEC-001-security-record.md` | Security and network isolation record |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-SEC-001-recovery-and-deletion.md` | Secure recovery and asset deletion procedures |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-ENGINE-001-validation-record.md` | Multi-voice deterministic engine validation record |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-E2E-001-validation-record.md` | E2E integration and human acceptance test record |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-PERF-001-benchmark-record.md` | Latency reduction and engine benchmark record |
| `C:\Users\19196\Documents\VIBE\docs\VIBE-E2E-001-UX-review\README.md` | UI cleanup and telemetry review documentation |

### E. Benchmark & Telemetry Datasets
| Path / File | Purpose / Role |
| :--- | :--- |
| `C:\Users\19196\Documents\VIBE\output\streaming_pipeline_results.json` | Sentence chunking pipeline benchmark telemetry |
| `C:\Users\19196\Documents\VIBE\output\kokoro_benchmark_results.json` | Kokoro ONNX CPU latency benchmarks |
| `C:\Users\19196\Documents\VIBE\output\chatterbox_tuning_results.json` | Chatterbox thread and condition cache benchmarks |
| `C:\Users\19196\Documents\VIBE\output\e2e_live_telemetry.jsonl` | Structured background live telemetry dataset |
| `C:\Users\19196\Documents\VIBE\output\remediation_round1_results.json` | Remediation round 1 multi-turn test results |

---

## 2. Environment & Reproducibility Baseline

- **Operating System:** Windows 11 Pro 64-bit (Build 26100)
- **CPU:** Intel Core i7-10700T @ 2.00GHz (8 Cores, 16 Logical Processors)
- **RAM:** 32.0 GB DDR4
- **Base Python Runtime:** Python 3.11.9 (`C:\Users\19196\Documents\VIBE\runtime\Python311\python.exe`)
- **VIBE Virtual Environment:** `C:\Users\19196\Documents\VIBE\env-vibe`
- **Primary Packages:**
  - `torch == 2.6.0+cpu`
  - `torchaudio == 2.6.0+cpu`
  - `onnxruntime == 1.20.1`
  - `kokoro-onnx == 0.4.9`
  - `soundfile == 0.13.1`
  - `transformers == 4.49.0`
  - `diffusers == 0.32.2`
  - `phonemizer == 3.3.0`
  - `chatterbox-tts == 0.1.0` (local build from repo)
- **Firewall Rule:** `VIBE-Python-Outbound-Block` (Blocks outbound traffic for `env-vibe\Scripts\python.exe`)
- **Scheduled Task:** `Budly Local Runtime` (Disabled on closure; preserved for reactivation)

---

## 3. Canonical Voice Protection Confirmation

- **Canonical Project Owner Voice:** `budly-primary` was **never recorded, collected, processed, or referenced**.
- **Voice Vault Status:** Purely synthetic disposable test fixtures (`test-voice-a`, `test-voice-b`, `test-voice-c`) and pre-trained default weights were used.
- **Sensitive Asset Exclusion:** Zero audio files (*.wav) or model weights are committed to git.

---

## 4. Governance Pointers

- **Governance Authority:** `Google Drive` $\rightarrow$ `BROS` $\rightarrow$ `VIBE`
- **Reactivation Authority:** Requires direct Project Owner `d-mac` authorization following hardware acceleration provisioning.
