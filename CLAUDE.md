# ComfyUI — Project Context

**Location:** `~/ComfyUI/ComfyUI/`
**Platform:** Mac Studio M4 Max · 128 GB Unified Memory · macOS
**ComfyUI Version:** v0.26.0
**OWUI Tool Version:** v5.9.2

## Purpose

Real estate marketing image generation: exteriors, interiors, lifestyle, social media content, blog/print hero images, digital staging with ControlNet depth + MLSD, and OpenWebUI chat-driven image generation.

## Directory Structure

```
~/ComfyUI/ComfyUI/
├── main.py                     ← ComfyUI entry point
├── venv/                       ← Python virtual environment
├── output/                     ← All generated images
├── models/
│   ├── checkpoints/juggernautXL_ragnarokBy.safetensors   ← Primary SDXL model
│   ├── loras/E5AEA4E58685E79A84E7A68FE99FB320E5AEA4E5.fDUS.safetensors  ← Interior LoRA (watermark @ ≥0.8)
│   ├── vae/{sdxl-vae-fp16-fix, flux_vae}.safetensors
│   ├── diffusion_models/flux-schnell/flux1-schnell.safetensors  ← FLUX (22 GB)
│   ├── clip/{clip_l, clip_g, t5xxl_fp16}.safetensors      ← CLIP + T5 encoders
│   ├── controlnet/{depth, canny, instantid_*}.safetensors
│   ├── ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors
│   ├── clip_vision/clip_vision_vit-h.safetensors
│   ├── instantid/ip-adapter.bin                           ← InstantID model
│   ├── insightface/models/antelopev2/*.onnx               ← InstantID face model
│   ├── ultralytics/bbox/face_yolov8m.pt                   ← FaceDetailer YOLO
│   ├── sams/sam_vit_l                                     ← SAM for inpaint auto-mask
│   ├── grounding-dino/groundingdino_swint_ogc.pth         ← GroundingDINO for inpaint
│   └── inpaint/{fooocus_inpaint_head.pth, inpaint_v26.fooocus.patch}
├── custom_nodes/               ← Installed extensions
├── start_comfyui.sh            ← Startup script
├── openwebui_tool_comfyui.py   ← OWUI tool source (edit here, deploy via script)
├── deploy_tool.sh              ← One-command deploy to OpenWebUI
├── claude-docs/                ← Per-feature reference docs (read on demand)
└── .env                        ← OWUI API key + tool ID (chmod 600)
```

## Startup

```bash
cd ~/ComfyUI/ComfyUI && ./start_comfyui.sh
```

Manual:
```bash
cd ~/ComfyUI/ComfyUI
source venv/bin/activate
export PYTORCH_ENABLE_MPS_FALLBACK=1
python main.py --listen 0.0.0.0 --port 8188
```

### Critical startup flags

- `--listen 0.0.0.0` — REQUIRED. Default `127.0.0.1` blocks Caddy reverse proxy.
- `PYTORCH_ENABLE_MPS_FALLBACK=1` — REQUIRED. Enables Metal fallback for unsupported ops.
- ComfyUI binds port **8189**; Caddy listens on 8188 and proxies → 8189.

## Access URLs

| Method | URL |
|--------|-----|
| Local (direct)      | `http://localhost:8189` |
| Via Caddy (local)   | `http://localhost:8188` → 8189 |
| Local network       | `http://192.168.1.65:8188` (via Caddy) |
| Tailscale           | `http://stevens-mac-studio.tail7c9d1c.ts.net:8188` (Caddy → 8189) |
| OpenWebUI (Docker)  | `http://host.docker.internal:8189` (direct, bypasses Caddy) |

### Caddy / Tailscale quirk

Tailscale TLS certs cover port 443 only. ComfyUI block in Caddyfile must use explicit `http://`:

```
# /opt/homebrew/etc/Caddyfile
stevens-mac-studio.tail7c9d1c.ts.net:8188 {
    reverse_proxy http://localhost:8189
}
```

Firefox HSTS cache can force HTTPS and break access — use Chrome, or clear HSTS.

## Custom nodes installed

| Node | Purpose |
|------|---------|
| websocket_image_save | Save images via websocket |
| ComfyUI-Manager | Node/model management UI |
| comfyui_pulid_flux_ll | PuLID face consistency for FLUX |
| comfyui_segment_anything | SAM + GroundingDINO auto-masking. **Requires `timm==0.9.2`** |
| ComfyUI_IPAdapter_plus | SDXL IP-Adapter (transfer_style) |
| comfyui_controlnet_aux | DepthAnythingV2Preprocessor, M-LSDPreprocessor, CannyEdgePreprocessor |
| ComfyUI_DifferentialDiffusion | (currently unused after Fooocus swap — retained) |
| comfyui-inpaint-nodes (Acly) | INPAINT_LoadFooocusInpaint + INPAINT_VAEEncodeInpaintConditioning + INPAINT_ApplyFooocusInpaint |
| ComfyUI_InstantID (cubiq) | InstantIDModelLoader, InstantIDFaceAnalysis, ApplyInstantID |
| ComfyUI-Impact-Pack (ltdrdata) | FaceDetailer |
| ComfyUI-Impact-Subpack (ltdrdata) | UltralyticsDetectorProvider / YOLO bbox — **separate repo from Impact-Pack** |
| ComfyUI-SD3-nodes / comfyui-sd3-powerlab | SD3.5 TripleCLIPLoader (legacy, SD3.5 inactive) |

**Node gotchas:**
- `comfyui_segment_anything` requires `timm==0.9.2` — newer timm breaks `sam_hq` import.
- `UltralyticsDetectorProvider` lives in Impact-**Subpack**, not Impact-Pack.
- Segment_anything class_types include `" (segment anything)"` suffix — required in workflow JSON.

## Critical Rules (top gotchas)

Full list in [`claude-docs/lessons-learned.md`](./claude-docs/lessons-learned.md). The most load-bearing:

- **cfg=1.0 is non-negotiable for FLUX** — distilled models break at higher values.
- **`PYTORCH_ENABLE_MPS_FALLBACK=1` must be exported** before launching.
- **`--listen 0.0.0.0` required** for any access beyond localhost.
- **Caddyfile is at `/opt/homebrew/etc/Caddyfile`** — not `~/Caddyfile`.
- **VAEDecodeTiled causes black images on MPS** — NEVER use it. VAEDecode only.
- **MPS NaN contamination is sticky** — once it appears, restart: `kill $(lsof -ti :8189) && ./start_comfyui.sh`.
- **FLUX and SDXL cannot run simultaneously** — sequential only.
- **Always verify `class_type` strings** against `/object_info` before deploying workflows.
- **OWUI tool param descriptions must be imperative, not informative** — describe what to do, not what's available.
- **OWUI tool status messages teach the LLM param names** — always echo the literal signature param name.

## Quick reference commands

```bash
# Start ComfyUI
cd ~/ComfyUI/ComfyUI && ./start_comfyui.sh

# Check model files
ls -lh models/checkpoints/ models/loras/ models/vae/ models/controlnet/

# View recent generated images
ls -lt output/ | head -20 && open output/

# Update ComfyUI core — THIS IS A FORK (sroesch/ComfyUI, branch mac-studio).
# Do NOT use the ComfyUI-Manager "Update" button: it hardcodes the stock `master`
# branch + assumes a clean tree, so it fails on this fork ("Failed to checkout 'master'").
# Plain `git pull` only pulls origin/mac-studio (your fork) — it does NOT get upstream.
# Correct update = fetch upstream and merge into mac-studio, then reinstall deps:
cd ~/ComfyUI/ComfyUI && git fetch upstream && git merge upstream/master
./venv/bin/pip install -r requirements.txt   # new deps land with most updates
git push origin mac-studio                    # back the merge up to your fork
# then restart (kill + start) to load the new version; watch log for custom-node import fails

# Deploy tool changes
cd ~/ComfyUI/ComfyUI && ./deploy_tool.sh

# Kill + restart (MPS NaN recovery)
kill $(lsof -ti :8189) && cd ~/ComfyUI/ComfyUI && ./start_comfyui.sh
```

## Reference Docs — read when relevant

**Read these files at session start when the user's task touches that area.** Auto-discovery does not pull `claude-docs/*.md` — you must read them explicitly. If the user mentions any of the trigger words below, read the matching sub-file before proposing changes.

- [models.md](./claude-docs/models.md) — model decision matrix, FLUX/SDXL parameters, OWUI tool model constants, memory footprint, canvas sizes
- [prompt-engineering.md](./claude-docs/prompt-engineering.md) — FLUX dual encoder, SDXL CLIPTextEncodeSDXL, real-estate prompt rules, SDXL_NEGATIVE
- [integrations.md](./claude-docs/integrations.md) — OpenWebUI tool functions + workspace settings + deploy workflow + OWUI lessons; n8n integration plan
- [lessons-learned.md](./claude-docs/lessons-learned.md) — full list of hard-won gotchas (workflow format, SAM/DINO, mask discipline, SDXL architecture, IP-Adapter/LoRA, InstantID, watermark)
- [roadmap.md](./claude-docs/roadmap.md) — Phase 12 in-progress + Phase 13 next; Phases 2–11 collapsed to changelog pointer

For broader project reference: `~/claude-project-docs/` — `ComfyUI_Image_Generation_Guide.md`, `ComfyUI_Project_Summary_Supplement.md`, `LLM_Project_Changelog_v2_Mac.md`, `LLM_Full_Project_Summary_v2.md`, `Quick_Reference_Commands.md`.

## End-of-Session Wrapup Routing

When `/wrapup` runs after a session, route updates to the right destination:

- **Tool/model parameter change** → `claude-docs/models.md` or `claude-docs/integrations.md`
- **New gotcha or hard-won lesson** → `claude-docs/lessons-learned.md`
- **Phase progression / next steps** → `claude-docs/roadmap.md`
- **Global infra change** (port, Caddy, startup flags, dependencies) → this main CLAUDE.md
- **Session narrative** → `~/claude-project-docs/LLM_Project_Changelog_v2_Mac.md` only

If this main CLAUDE.md grows past ~150 lines, flag for splitting in the wrapup handoff.
