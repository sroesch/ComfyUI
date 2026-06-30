# ComfyUI — Changelog

Per-project narrative history (source of truth for the ComfyUI subsystem). Cross-cutting/infra events live in `~/claude-project-docs/LLM_System_Timeline.md`. Pre-2026-07 ComfyUI history: `~/claude-project-docs/LLM_Project_Changelog_2026-H1_archive.md` (grep `(ComfyUI`).

**Rotation:** by calendar year; if this file passes ~1,000 lines mid-year, roll the older half into `changelog-<year>-H1.md` and keep this file lean.

**Entry format** (newest on top):

```
## YYYY-MM-DD (Session N) — one-line summary
**Trigger:** …
**Fix/Task:** …
**Verification:** …
**Files/Commits:** …
**Docs/Memory:** …
```

---

<!-- New ComfyUI entries go below this line, newest on top. -->

## 2026-06-30 (Session 27) — FLUX.2 [klein] 9B installed (one-node + GGUF); license analysis
**Trigger:** Steven wanted to try the `one-node-flux-2-klein` custom node (yanokusnir-ai) in ComfyUI, mainly toward digital-staging experiments.
**Fix/Task:**
- Cloned `one-node-flux-2-klein` into `custom_nodes/`. No `requirements.txt`; its two optional deps were already present (`comfyui-inpaint-cropandstitch` for PAINT, `comfyui_controlnet_aux` for POSE/DWPose).
- Established that ComfyUI cannot use the existing MLX Qwen as the text encoder (PyTorch/MPS-only; encoders not interchangeable) → downloaded the matching `qwen_3_8b` instead.
- No official Comfy single-file repackage of klein-9B exists + BFL repo gated/diffusers-only → installed `ComfyUI-GGUF` (city96) + `gguf 0.19.0` into the venv; sourced the model as BF16 GGUF (full precision) via the node's external loader.
- Downloaded the 9B set (all public, no HF token): `flux-2-klein-9b-BF16.gguf` (17 GiB), `qwen_3_8b.safetensors` (15 GiB), `flux2-vae.safetensors`, `birefnet.safetensors`, `bfs_head_v1_flux-klein_9b…` + `refcontrol_v2_poses.safetensors` LoRAs.
- License deep-read: klein 9B = FLUX Non-Commercial v2.1; §4-a(i) bars commercial/production use of model + output data; 9B kept for personal/experimentation. 4B (Apache 2.0) is the path for real listing work; BFL Builder tier is the self-serve commercial option (no public price).
**Verification:** Files verified present at expected sizes; staging dir cleaned. **NOT yet runtime-tested** — ComfyUI not restarted with the new node/models in-session (Steven to restart and test in a fresh session).
**Files/Commits:** docs only in repo (custom_nodes + models are gitignored): `CLAUDE.md`, `claude-docs/{models,lessons-learned,changelog}.md`.
**Docs/Memory:** CLAUDE.md custom-nodes table + gguf gotcha; models.md FLUX.2 section + license note; lessons-learned 51–54 (MLX≠ComfyUI, encoder-not-interchangeable, no klein single-file→GGUF, license); memory `comfyui_architecture.md` + timeline pointer.
