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

## 2026-06-30 (Session 28) — FLUX.2 [klein] runtime-validated end-to-end (T2I/I2I/EDIT/PAINT) + image-gen glossary
**Trigger:** Session 27 installed klein 9B but never restarted ComfyUI / runtime-tested. Steven restarted, wired the node, and ran the full mode arc — also wanting to learn image-gen concepts coming from a Stability background.
**Fix/Task:**
- **GGUF wiring confirmed:** model absent from the node's MODEL dropdown because it scans `.safetensors/.ckpt/.pt/.pth` only (`nodes.py`). Wired via External-inputs toggle → `Unet Loader (GGUF)` → `model` socket. Verified `ComfyUI-GGUF` imported clean (`object_info` lists `UnetLoaderGGUF` et al.). CLIP/VAE left on dropdowns (unconnected sockets fall back to dropdown values — verified in JS `_extSlot`).
- **Full mode characterization on klein:** T2I (luxury kitchen, excellent first-prompt result) → I2I (proved the change-vs-preserve wall across denoise 0.45/0.60/0.75) → EDIT (reference-latent/Kontext instruction editing landed the green-cabinet swap I2I couldn't, while locking layout; learned region-scope bleed + disambiguation) → PAINT (masked backsplash fix = zero bleed; furniture-placement test on a real listing photo learned mask-size = object-size/count + vertical-volume + grounding cue).
- **"Change Strength" decoded** as the I2I KSampler `denoise` (1:1) by reading the node JS.
- **Created `~/claude-project-docs/Image_Generation_Glossary.md`** — model-agnostic terminology quick-ref (core dials, model parts, modes, file formats/quantization with Apple-Silicon targeting, prompting, rules of thumb). Includes a GGUF-vs-NVFP4/DF11/INT8/SVDQuant section flagging which formats are useless on MPS.
**Verification:** All four modes ran successfully and outputs reviewed (FK_00006 EDIT, FK_00007 EDIT-disambiguated, FK_00008 PAINT backsplash, FK_00010 PAINT furniture). klein behaves per the distilled-model model: 4 steps, CFG 1, no negative.
**Files/Commits:** docs only — `claude-docs/{models,lessons-learned,changelog}.md`; new `~/claude-project-docs/Image_Generation_Glossary.md` (not git-tracked). No code/model changes (custom_nodes + models gitignored; install committed last session @ `0d69db6a`).
**Docs/Memory:** models.md FLUX.2 mode-mechanics table + GGUF-dropdown note + glossary pointer; lessons-learned 55–59; memory `comfyui_roadmap.md` (S28) + `comfyui_architecture.md` runtime-validated flag; timeline one-liner.

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
