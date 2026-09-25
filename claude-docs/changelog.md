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

## 2026-09-25 (Session 29) — COMFY-10: SD3.5 + FLUX.1-schnell retired, 86.7 GB archived to NAS, tool v5.9.3
**Trigger:** The 2026-09-25 disk sweep left ComfyUI at 142 GB, and only SDXL (Juggernaut) and FLUX.2 klein are in use. The work was planned in one session (plan `~/.claude/plans/pasted-content-id-fad5-picking-up-goofy-adleman.md`) and executed in a fresh one.
**Fix/Task:**
- **Consumers fixed first, with the weights still present.** Tool v5.9.3: the FLUX.1 branch of `generate_image` is deleted, and every `model` value (default now `"sdxl"`) renders Juggernaut XL, so saved prompts that pass `"flux"` still work. The `real-estate-imaging` workspace prompt was edited over the OWUI API: its two model lines (`flux` for social, `sd35` for MLS) became one `sdxl` line. General Chat never names a model, and it was the path that would have silently broken on the old `"flux"` default.
- **Archived, then removed:** 415 files and 86.74 GB went to the NAS at `/volume1/@home/steven/retired-models-2026-09/` (a private home folder, not a Syncthing share). That covers SD3.5 (unet, diffusers copy, depth ControlNet, VAE, and the IP-Adapter pair `ipadapter/ip-adapter.bin` + `siglip`), FLUX.1-schnell (dir + `flux_vae`), the `clip/` encoders, the duplicate `models/groundingdino/`, and 5 orphan custom nodes. The 4 HF cache stubs were deleted without archiving. ComfyUI went from 142 to 61 GB, and the Data volume gained about 78 GiB free.
- **Three surprises, each handled:**
  1. The file count was 415, not the planned 414. The extra file is `models/clip/.DS_Store`, and the bytes and zero-byte count matched the plan.
  2. OWUI 0.9.6's `/models/model/update` returns a 500 if `access_grants` is omitted, because the router re-validates an explicit `None`. The update had to send the grant list, and `set_access_grants` deletes and recreates the rows: the read grant for user `06beb1fb` is the same in meaning but has a new row id.
  3. The UGREEN-patched rsync on the NAS refuses **every** destination path while the UGOS Rsync service is off, and scp/SFTP sees a different path layout. The copy went by tar over SSH (Steven's call), with an identical SHA-256 gate.
- **Gate B finding:** the klein one-node keeps its settings in browser localStorage, which is separate for each browser and address. On a fresh origin, "External model/clip/vae inputs" defaults to OFF. With it off, the node **ignores the wired GGUF loader** and uses the MODEL dropdown (`none`). The LoRA picks also reset. Nothing server-side changed.
**Verification:** A direct-call harness (`~/comfy-retire-2026-09/harness.py`, 9 calls across all 6 tool methods) passed 9/9 at control, after the fix, and after removal. From the fix onward, the default and `"flux"` calls render SDXL. NAS `sha256sum -c` showed 415/415 OK, and the file count was 415, before any local delete. On restart, exactly the 5 orphan nodes are gone, with 0 import failures. `/object_info` shows the key nodes, and the loaders list only the kept SDXL files. The GroundingDINO `.pth` is unchanged (no re-download). The retired-model grep returns 0 hits across the tool source, the installed tool and both workspace prompts. Steven's 4 live checks were confirmed from `/history`: General Chat, Real Estate Imaging and dashboard staging all rendered on Juggernaut XL, and klein T2I produced `FK_00012_` via the GGUF.
**Files/Commits:** fork `8e38638d` (tool v5.9.3, pushed to `origin/mac-studio`); docs `CLAUDE.md`, `claude-docs/{models,integrations,lessons-learned,prompt-engineering,roadmap,changelog}.md`. Artifacts (manifest, sizes, harness outputs, prompt backup `real-estate-imaging.before.json`) are in `~/comfy-retire-2026-09/`.
**Docs/Memory:** `models.md` has a new "Retired 2026-09" section with the archive and restore steps. `~/claude-project-docs/ComfyUI_Image_Generation_Guide.md` was fully rewritten as an SDXL + klein guide, and the Supplement, the full summary, Quick Reference, the OWUI summary and n8n §16 were updated. Board: COMFY-10 is Done, and the Ideas card COMFY-11 was added.

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
