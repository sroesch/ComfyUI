# CLAUDE.md — ComfyUI Project Context
**Location:** `~/ComfyUI/ComfyUI/`
**Platform:** Mac Studio M4 Max · 128GB Unified Memory · macOS
**ComfyUI Version:** v0.7.0
**Last Updated:** 2026-04-28

> **Historical phase narratives** (Phases 2–10) and older lessons live in
> `~/claude-project-docs/LLM_Project_Changelog_v2_Mac.md` and
> `~/claude-project-docs/ComfyUI_Image_Generation_Guide.md`. This file covers
> the current (SDXL) stack + Phase 11+ only.

---

## Project Purpose

Real estate marketing image generation (exteriors, interiors, lifestyle), social media content, blog/print hero images, digital staging with ControlNet depth + MLSD, and OpenWebUI chat-driven image generation.

---

## Directory Structure

```
~/ComfyUI/ComfyUI/
├── main.py                     ← ComfyUI entry point
├── venv/                       ← Python virtual environment
├── output/                     ← All generated images
├── models/
│   ├── checkpoints/juggernautXL_ragnarokBy.safetensors   ← Primary SDXL model
│   ├── loras/E5AEA4E58685E79A84E7A68FE99FB320E5AEA4E5.fDUS.safetensors  ← Interior LoRA (watermark @ ≥0.8)
│   ├── vae/sdxl-vae-fp16-fix.safetensors                  ← SDXL VAE (fp16 fix)
│   ├── vae/flux_vae.safetensors                           ← FLUX VAE (320MB)
│   ├── diffusion_models/flux-schnell/flux1-schnell.safetensors  ← FLUX (22GB)
│   ├── clip/{clip_l, clip_g, t5xxl_fp16}.safetensors      ← CLIP + T5 encoders
│   ├── controlnet/control-lora-depth-rank256.safetensors  ← SDXL depth
│   ├── controlnet/controlnet-canny-sdxl-1.0.safetensors   ← SDXL canny (reused for MLSD output)
│   ├── controlnet/instantid_controlnet_sdxl.safetensors   ← InstantID
│   ├── ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors   ← SDXL IP-Adapter
│   ├── clip_vision/clip_vision_vit-h.safetensors          ← SDXL vision encoder
│   ├── instantid/ip-adapter.bin                           ← InstantID model
│   ├── insightface/models/antelopev2/*.onnx               ← InstantID face model (auto-extracted)
│   ├── ultralytics/bbox/face_yolov8m.pt                   ← FaceDetailer YOLO
│   ├── sams/sam_vit_l                                     ← SAM for inpaint auto-mask
│   ├── grounding-dino/groundingdino_swint_ogc.pth         ← GroundingDINO for inpaint
│   └── inpaint/{fooocus_inpaint_head.pth, inpaint_v26.fooocus.patch}  ← Fooocus inpaint
├── custom_nodes/               ← Installed extensions (see list below)
├── start_comfyui.sh            ← Startup script
├── openwebui_tool_comfyui.py   ← OWUI tool source (edit here, deploy via script)
├── deploy_tool.sh              ← One-command deploy to OpenWebUI
└── .env                        ← OWUI API key + tool ID (chmod 600)
```

SD3.5 legacy files (`sd3.5_large.safetensors`, `sd3.5_vae.safetensors`, `sd3.5_large_controlnet_depth.safetensors`) remain on disk but are inactive — safe to delete once SDXL is fully validated.

---

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

### Critical Startup Flags
- `--listen 0.0.0.0` — REQUIRED. Default 127.0.0.1 blocks Caddy reverse proxy.
- `PYTORCH_ENABLE_MPS_FALLBACK=1` — REQUIRED. Enables Metal fallback for unsupported ops.
- ComfyUI binds port **8189**; Caddy listens on 8188 and proxies → 8189.

---

## Access URLs

| Method | URL |
|--------|-----|
| Local (direct)      | `http://localhost:8189` |
| Via Caddy (local)   | `http://localhost:8188` → 8189 |
| Local network       | `http://192.168.1.65:8188` (via Caddy) |
| Tailscale           | `http://stevens-mac-studio.tail7c9d1c.ts.net:8188` (Caddy → 8189) |
| OpenWebUI (Docker)  | `http://host.docker.internal:8189` (direct, bypasses Caddy) |

### Caddy / Tailscale Quirk
Tailscale TLS certs cover port 443 only. ComfyUI block in Caddyfile must use explicit `http://`:

```
# /opt/homebrew/etc/Caddyfile
stevens-mac-studio.tail7c9d1c.ts.net:8188 {
    reverse_proxy http://localhost:8189
}
```

Firefox HSTS cache can force HTTPS and break access — use Chrome, or clear HSTS.

---

## Model Decision Matrix

| Use Case | Model | Reason |
|----------|-------|--------|
| Social media / blog | FLUX.1-schnell | ~24s, fast iteration |
| Print / MLS photos | SDXL Juggernaut XL | Photorealistic, LoRA ecosystem, negative prompts work |
| Restyling furnished rooms | SDXL `stage_room` | Dual ControlNet depth+MLSD, Interior LoRA |
| Placing furniture in empty rooms | SDXL `inpaint_room` | Fooocus inpaint + SAM auto-mask or manual clipspace mask |
| Style transfer from reference | SDXL `transfer_style` | IP-Adapter Plus SDXL + ControlNet depth |
| Face-locked portrait/headshot | SDXL `transform_image` | InstantID + 2-pass FaceDetailer |

**Cannot run FLUX and SDXL simultaneously** — sequential only.

---

## Model Parameters (do not change without reason)

### FLUX.1-schnell
```
DualCLIPLoader:  clip_name1=clip_l, clip_name2=t5xxl_fp16, type=flux
KSampler:        cfg=1.0 (MUST be 1.0 for distilled; higher = severe artifacts)
                 steps=4, sampler=euler, scheduler=simple
VAE:             flux_vae.safetensors
Canvas:          1024×1024
```

### SDXL — Juggernaut XL (primary for all room workflows)
```
CheckpointLoaderSimple: juggernautXL_ragnarokBy.safetensors
LoraLoader (interior; NOT generate_image + NOT transfer_style):
  lora_name: E5AEA4E58685E79A84E7A68FE99FB320E5AEA4E5.fDUS.safetensors
  strength_model: 0.5    ← MAXIMUM. ≥0.8 embeds "MUVSSTAЁE" watermark bottom-right
  trigger_word: mrares   ← MUST be at START of prompt: f"mrares, {prompt}"
VAE: sdxl-vae-fp16-fix.safetensors

CLIPTextEncodeSDXL:
  text_g: full natural language
  text_l: comma-separated keywords

KSampler (standard): dpmpp_2m, karras, steps=30, cfg=7
KSampler (stage_room): steps=50 hardcoded

Canvas sizes:
  Default:   1024×1024
  Landscape: 1152×768    ← canvas_size="landscape" (inpaint_room)
  Portrait:  768×1024    ← canvas_size="portrait"
```

---

## Prompt Engineering

### FLUX — Dual Encoder
`clip_l` (77-token hard limit): short comma-separated keywords — search-tag / hashtag style.
`t5xxl` (~unlimited): full natural language description, materials, lighting, atmosphere, camera style.
Negative prompts: same short phrase in both inputs (`blurry, low quality, distorted, dark`).

### SDXL — CLIPTextEncodeSDXL
`text_g` = full NL description (same for simplicity). `text_l` = comma-separated keywords. Negative prompts work as expected (UNet cross-attention). `SDXL_NEGATIVE` must block architectural-hallucination vocab: crown molding, coffered/tray ceiling, recessed lighting, curtains, drapes, wallpaper, remodeled, renovated, different room.

### Real Estate Prompt Rules
- Always specify lighting, materials, camera style ("professional real estate photography").
- San Diego context: stucco, palm trees, desert landscaping, blue agave.
- Prefer specificity: "white Carrara marble with grey veining" > "beautiful kitchen".
- **`stage_room` prompt scope: furniture and décor ONLY** — architectural terms cause the model to remodel even with ControlNet. Let the ControlNet hold geometry; use text for soft furnishings only.

---

## Memory Footprint

| Config | Unified Memory |
|--------|----------------|
| FLUX generation | ~32GB |
| SDXL generation | ~20GB |
| Ollama qwen3.5:35b loaded | ~20–25GB |
| Ollama + SDXL concurrent | ~40–45GB |
| SDXL + InstantID + FaceDetailer | ~35–40GB |
| ComfyUI idle | <2GB |

128GB total — comfortable headroom on all combos.

---

## Custom Nodes Installed

| Node | Purpose |
|------|---------|
| websocket_image_save | Save images via websocket |
| ComfyUI-Manager | Node/model management UI |
| comfyui_pulid_flux_ll | PuLID face consistency for FLUX |
| comfyui_segment_anything | SAM + GroundingDINO auto-masking (inpaint_room). **Requires `timm==0.9.2`** |
| ComfyUI_IPAdapter_plus | SDXL IP-Adapter (transfer_style) |
| comfyui_controlnet_aux | DepthAnythingV2Preprocessor, M-LSDPreprocessor, CannyEdgePreprocessor |
| ComfyUI_DifferentialDiffusion | (currently unused after Fooocus swap — retained) |
| comfyui-inpaint-nodes (Acly) | INPAINT_LoadFooocusInpaint + INPAINT_VAEEncodeInpaintConditioning + INPAINT_ApplyFooocusInpaint |
| ComfyUI_InstantID (cubiq) | InstantIDModelLoader, InstantIDFaceAnalysis, ApplyInstantID (transform_image) |
| ComfyUI-Impact-Pack (ltdrdata) | FaceDetailer |
| ComfyUI-Impact-Subpack (ltdrdata) | UltralyticsDetectorProvider / YOLO bbox — **separate repo from Impact-Pack** |
| ComfyUI-SD3-nodes / comfyui-sd3-powerlab | SD3.5 TripleCLIPLoader (legacy, SD3.5 inactive) |

**Node gotchas:**
- `comfyui_segment_anything` requires `timm==0.9.2` — newer timm breaks `sam_hq` import.
- `UltralyticsDetectorProvider` lives in Impact-**Subpack**, not Impact-Pack.
- Segment_anything class_types include `" (segment anything)"` suffix — required in workflow JSON.

---

## OpenWebUI Integration

**Status:** Phase 11 complete (2026-04-13). Phase 12 in progress: transform_image (InstantID + FaceDetailer) live-tested 2026-04-17 — identity lock solid at `appearance_strength=0.8` with 1024×1024 source, expression control ~50% (keypoint ControlNet `end_at=0.5` fix queued).
**Tool source:** `~/ComfyUI/ComfyUI/openwebui_tool_comfyui.py` (edit here → `./deploy_tool.sh`).
**Internal API call:** `http://host.docker.internal:8189` (from inside OWUI Docker).
**Image URLs returned:** `https://stevens-mac-studio.tail7c9d1c.ts.net/comfyui/view?filename=...` (HTTPS via Caddy).

### Current Tool Functions (v5.9.2)

| Function | Description | Timeout | Notes |
|----------|-------------|---------|-------|
| `generate_image(prompt, model)` | txt2img; model="flux" or "sdxl"; no LoRA on SDXL path | — | — |
| `transform_image(prompt, appearance_strength, image_url)` | InstantID + 2-pass FaceDetailer | 360s | Prompt = attire/scene only. v5.9.1: status echoes `appearance_strength` (signature name) |
| `edit_image(prompt, image_url, denoise)` | img2img + Interior LoRA; room restyling | — | denoise=0.65 default |
| `stage_room(prompt, denoise, controlnet_strength)` | Dual ControlNet (depth+MLSD) + Interior LoRA + watermark | 300s | 50 steps; furnished room restyling |
| `inpaint_room(prompt, mask_subject, denoise, threshold, mask_expand, canvas_size)` | SAM auto-mask + Fooocus inpaint + Interior LoRA + watermark | 480s | Furniture in empty rooms |
| `transfer_style(prompt, style_strength)` | IP-Adapter Plus + ControlNet depth; no LoRA | 360s | Attach reference (1st) + room (2nd) |

### Model Constants (verify at top of tool file)
```python
SDXL_CHECKPOINT      = "juggernautXL_ragnarokBy.safetensors"
INTERIOR_LORA        = "E5AEA4E58685E79A84E7A68FE99FB320E5AEA4E5.fDUS.safetensors"
LORA_STRENGTH        = 0.5   # 0.8+ embeds AresWei watermark
SDXL_VAE             = "sdxl-vae-fp16-fix.safetensors"
CONTROLNET_DEPTH     = "control-lora-depth-rank256.safetensors"
CONTROLNET_CANNY     = "controlnet-canny-sdxl-1.0.safetensors"
IPADAPTER_SDXL       = "ip-adapter-plus_sdxl_vit-h.safetensors"
CLIP_VISION_VIT_H    = "clip_vision_vit-h.safetensors"
INSTANTID_MODEL      = "ip-adapter.bin"                 # models/instantid/ — exact name
INSTANTID_CONTROLNET = "instantid_controlnet_sdxl.safetensors"
SDXL_SAMPLER="dpmpp_2m" / SDXL_SCHEDULER="karras" / SDXL_STEPS=30 / SDXL_CFG=7
```

### OWUI Workspace Settings
- **Function Calling = Native** (not Default — Default outputs `<tool_code>` text).
- System prompt inline-image rule: after any tool returns a URL, embed as `![image](url)`.
- Prompt passthrough rule: pass user text verbatim; do not paraphrase, simplify, or interpret.

**Deploy workflow:** Edit `.py` → `./deploy_tool.sh` → live in OWUI. API key in `.env` (OWUI "Create new secret key" button is broken; key inserted directly into SQLite `api_key` table as workaround).

---

## Development Roadmap

### Phases 2–10 ✅ COMPLETE (see changelog for details)
- **Phase 2 (2026-03-24):** img2img deployed in OWUI.
- **Phase 3 (2026-03-24):** ControlNet Depth via `stage_room`.
- **Phase 4 (2026-03-25):** SAM + GroundingDINO auto-masking via `inpaint_room`.
- **Phase 5–6 (2026-03-25/26):** IP-Adapter Style Transfer, then geometry preservation via ControlNet depth.
- **Phase 7/7b (2026-03-27):** Inpainting for furniture placement; manual-mask debugging (white-blob root cause).
- **Phase 8 (2026-04-07):** **Full SDXL migration** — Juggernaut XL replaces SD3.5 backbone across all room tools. Tool v5.0.0.
- **Phase 8.5 (2026-04-08):** `transform_image` added (IP-Adapter Plus + EmptyLatentImage architecture). Tool v5.2.0.
- **Phase 9 (2026-04-10):** MLSD swap (stage_room), DifferentialDiffusion (inpaint_room, later superseded by Fooocus), InstantID + 2-pass FaceDetailer (transform_image rewrite), PIL watermark, KSampler 30→50 for stage_room. Tool v5.3.0.
- **Phase 9.1 (2026-04-10):** Architectural fidelity fixes for stage_room — depth/MLSD end_percent 0.4/0.3 → 0.55, MLSD strength 0.25 → 0.35, default denoise 0.72 → 0.65. Tool v5.4.0.

### Phase 11 ✅ COMPLETE (2026-04-13)
- **Fooocus inpaint algorithm** replaces VAEEncodeForInpaint + DifferentialDiffusion. New nodes: `INPAINT_LoadFooocusInpaint`, `INPAINT_VAEEncodeInpaintConditioning`, `INPAINT_ApplyFooocusInpaint`. Models in `models/inpaint/`: `fooocus_inpaint_head.pth`, `inpaint_v26.fooocus.patch`.
- `canvas_size` param added to `inpaint_room()`: landscape=1152×768 (MLS 3:2 default), portrait=768×1024, square=1024×1024.
- **Dashboard split:** `~/dashboard/` standalone service (port 8000) proxies all tool APIs.
- **Virtual Staging tab** deployed — canvas mask painter + Fooocus workflow submission.
- Tool version v5.9.0.

### Phase 12 🟡 IN PROGRESS (2026-04-17 → 2026-04-28)
- **v5.9.2 directive `:param model:` description (2026-04-28, OWUI session 26)** — `generate_image` docstring at line 339 rewritten from informative ("flux is fast, sdxl is detailed") to imperative ("ALWAYS pass `model='sdxl'` for real-estate / MLS / interior / staging work; pass `'flux'` only for social-media graphics"). Fixes session-24 OWUI smoke-test row 5 where Qwen's CoT decided "use sdxl" but never passed the kwarg → tool default `flux` won. Smoke-test post-deploy: "MLS-ready interior shot of a kitchen" → Juggernaut XL loaded (53.89 s, 30 steps), confirmed in logs. Deployed via `./deploy_tool.sh`.
- **antelopev2 nesting fix** — auto-extracted as `antelopev2/antelopev2/*.onnx` causing `AssertionError: 'detection' in self.models`. Fix: flatten one level and delete zip.
- **First successful InstantID run** — identity lock solid with 1024×1024 source (face 40–60% of frame). Small sources cause InsightFace to downscale detection → pixelated output.
- **Status-message hallucination fix (v5.9.1)** — status/return strings echoed "Identity lock strength: X" which Qwen learned as the param name, then invented `identity_lock_strength=` on subsequent calls. Dropped as unknown kwarg → default fired → Qwen confabulated. Fix: both pre-run emit (line 882) and return string (line 892) now echo `appearance_strength=X` matching the signature.
- **Expression control characterized — NOT YET FIXED** — InstantID keypoint ControlNet (active via `end_at: 1.0`) projects source mouth-corner positions into output. Prompts for "scowl" land brows ~50% of the time but mouth stays smiling. Candidate fix pending empirical test: shorten `end_at` on ApplyInstantID (line 755) 1.0 → 0.5 so keypoints release after step 15, giving text prompt lower-face control while FaceDetailer re-locks identity.
- **OWUI General Chat system prompt rewritten** — adds prompt-refinement escape hatch, `# AVAILABLE SKILLS` block referencing SDXL Prompt Writing skill, `appearance_strength` param-name enforcement, MJ-flag stripping, InstantID no-face-descriptors rule, confabulation-guard rule.
- **SDXL Prompt Writing skill v2 drafted** at `~/Desktop/SDXL_Prompt_Writing_v2.md`.

### Phase 13 — NEXT
- **Step 3 (current plan):** real `appearance_strength=0.5` scowl test — verify system-prompt passthrough. (a) success → document; (b) brow-only → proceed to end_at=0.5.
- **Step 4 (conditional):** `end_at: 1.0 → 0.5` on ApplyInstantID (line 755), bump to v5.10.0. If identity loss too severe, migrate to `ApplyInstantIDAdvanced` (separate ip_weight / cn_strength / independent start-end).
- User feedback on staging tab — pending.
- Export SDXL inpaint workflow as litegraph JSON (never re-exported post-Phase-8).
- LoRA replacement — find interior LoRA without embedded watermark.
- n8n ComfyUI integration (medium-term).

### Digital Staging Notes
Digital staging for vacant listings requires at minimum: img2img + ControlNet depth model. FLUX alone (text-to-image) is not sufficient. ControlNet is what makes geometry-aware furniture placement reliable.

---

## n8n Integration

Planned (medium-term). See `n8n_Project_Summary.md` § 7. Concept: n8n workflow triggers ComfyUI API → image generated → uploaded to Google Drive or output tab in Google Sheets as part of marketing content pipeline.

---

## Lessons Learned (current stack)

### Infrastructure / macOS
1. **cfg=1.0 is non-negotiable for FLUX** — distilled models break at higher values.
2. **`PYTORCH_ENABLE_MPS_FALLBACK=1` must be exported** before launching (not just set in script).
3. **`--listen 0.0.0.0` required** for any access beyond localhost (Caddy, network clients).
4. **Caddyfile: `/opt/homebrew/etc/Caddyfile`** — not `~/Caddyfile`.
5. **Firefox HSTS** can silently force HTTPS on HTTP-only blocks — use Chrome for first test.
6. **FLUX and SDXL cannot run simultaneously** — sequential only, swap between jobs.
7. **CLIP-L and T5-XXL are shared** — one copy on disk serves both FLUX and SD3.5.
8. **Generation time regression** (times increasing) = memory leak → restart ComfyUI.
9. **VAEDecodeTiled causes black images on MPS** — NEVER use it. VAEDecode only. NaN after long sessions → restart ComfyUI to clear MPS state.
10. **After NaN in a session, subsequent runs also produce NaN** — MPS accumulates corrupted state across runs in same process. If `invalid value encountered in cast` appears, restart: `kill $(lsof -ti :8189) && ./start_comfyui.sh`.
11. **transfer_style + stage_room in same session** can cause MPS NaN contamination. If warning appears after style transfer, restart before staging.

### OpenWebUI / Tool
12. **OWUI image URLs must use HTTPS** (port 443 via Caddy `/comfyui/*` route). HTTP URLs get HSTS-upgraded → break.
13. **OWUI API key button broken** — backend returns 403 "not allowed in environment" even with `ENABLE_API_KEY=true`. Workaround: insert key via `docker exec` into SQLite `api_key`. Key stored in `.env`.
14. **`deploy_tool.sh`** pushes via REST API — no copy-paste.
15. **OWUI LLM paraphrases and strips spatial detail** from prompts — routing LLM summarizes before calling tool. Add explicit "Prompt passthrough (MANDATORY)" rule to system prompt.
16. **OWUI tool status messages teach the LLM parameter names** — every friendly label gets interpreted as the canonical param. Rule: always use the literal signature param name in status messages (`appearance_strength=0.8`), even at the cost of friendliness. The tool's output is a more reliable teacher than the system prompt.
17. **Qwen confabulates technical explanations** when a tool call produces unexpected output (because the LLM's own kwarg was dropped). Mitigate with: (a) explicit param-name enforcement in system prompt, (b) status-message discipline, (c) BOUNDARIES rule forbidding confabulation.
17b. **OWUI tool param descriptions targeting LLM argument routing must be imperative, not informative.** "FLUX is fast, SDXL is detailed" describes the options; the model reads it, decides in CoT which one fits, but doesn't reliably emit the kwarg in the function call. "ALWAYS pass `model='sdxl'` for X, Y, Z; pass `'flux'` only for W" instructs the model. Confirmed v5.9.2 fix: smoke-test routing went from FLUX-default-wins to SDXL-on-first-attempt with the description rewrite alone (no other changes).

### ComfyUI workflow format
18. **Litegraph JSON required for v0.7.0** — flat API format (`{id: {class_type, inputs}}`) is rejected with Zod validation error. Need `version: 0.4`, `nodes: [...]` (each with `id, type, pos, size, flags, order, mode, inputs, outputs, properties, widgets_values`), `links: [...]`, `last_node_id`, `last_link_id`.
19. **`ImageScale` widgets_values positional order: method first** — correct: `["lanczos", 1024, 1024, "disabled"]`. Width-first breaks with sampler/scheduler type errors at runtime.
20. **`ImageToMask` requires `channel` field** — use `"red"` for greyscale masks (all channels identical).
21. **`ImageBlur` blur_radius max=31** — 12 produces good gradient softness at 1024×1024.

### SAM / GroundingDINO (inpaint_room auto-mask)
22. **`comfyui_segment_anything` requires `timm==0.9.2`** — newer timm breaks `sam_hq` (RotaryEmbedding missing from `timm.layers.attention_pool2d`).
23. **Class_type suffix:** `"GroundingDinoModelLoader (segment anything)"` etc. — without suffix ComfyUI returns 400. Verify via `curl .../object_info | python3 -c "..."`.
24. **SAM `model_name` fields use display names, not filenames** — `"sam_vit_l (1.25GB)"` not `"sam_vit_l_0b3195.pth"`.
25. **GroundingDINO auto-downloads on first inpaint_room call** — `groundingdino_swint_ogc.pth` (~662MB) to `models/grounding-dino/`.
26. **Auto-mask "floor" is too blunt for large empty rooms** — SAM detects entire floor as one mask; furniture scatters, bleeds to hearths/walls. Use `threshold=0.4+` or manual clipspace mask for precision.
27. **DepthAnythingV2Preprocessor auto-downloads** `depth_anything_v2_vitl.pth` (~335MB) on first stage_room call.

### Mask discipline (inpaint_room)
28. **White inpaint output = IMAGE tensor has white paint baked in** — uploading a pre-painted image means MASK is all-zeros (no alpha) and the white pixels are encoded. Always use ComfyUI's built-in mask editor (right-click LoadImage → Open in MaskEditor); clipspace stores mask separately.
29. **Mask boundary rules:** upper edge at/below baseboard; keep mask 200px+ from walls; tight rectangular mask parallel to target wall, not a floor flood. Bleed into windows/doors confuses the model at top boundary.
30. **`mask_expand=150` is too large for sofa** — produced oversized mammoth sofa. Use 20–40px for standard furniture; 80px+ only for tall items (bookcases, full-height cabinets).

### SDXL architectural rules
31. **img2img without ControlNet restyles rooms, does NOT place furniture** — spatial object placement requires ControlNet depth.
32. **`stage_room` vs `inpaint_room` — hard distinction:** stage_room (img2img) restyles rooms that already have furniture; inpaint_room places new furniture in empty rooms by masking target floor area. Using stage_room to furnish an empty room produces partial furnishings with creative liberties.
33. **ControlNetApplyAdvanced does NOT take a vae input** (unlike SD3's ControlNetApplySD3). SDXL ControlNet conditioning goes through standard positive/negative CONDITIONING.
34. **Dual ControlNet chaining:** node A (depth) takes raw CLIP → node B (canny/MLSD) takes node A outputs → KSampler takes node B outputs. Both accumulate on same conditioning tensors.
35. **M-LSDPreprocessor inputs differ from CannyEdgePreprocessor** — MLSD uses `score_threshold`+`dist_threshold` (both default 0.1); Canny uses `low_threshold`+`high_threshold`. `controlnet-canny-sdxl-1.0.safetensors` is reusable with MLSD output (structurally similar).
36. **ControlNet end_percent must cover >50% of steps** to prevent architectural hallucination. At 50 steps, end_percent=0.4 covers only steps 1–20; 21–50 run with NO structural guidance and the model faithfully remodels to match style prompt. Sweet spot: 0.5–0.6.
37. **stage_room prompt scope: furniture and décor ONLY** — crown molding / recessed lighting / wall color instruct the model to remodel. ControlNet handles geometry; text handles furnishings.
38. **`SDXL_NEGATIVE` must block architectural vocab** (crown molding, coffered ceiling, recessed lighting, curtains, wallpaper, remodeled, renovated, different room) — otherwise they appear even without being in positive prompt.
39. **Floor textures in stage_room change unpredictably** — floors are nearly flat in depth map so ControlNet barely constrains them. Model rewrites floor freely at denoise≥0.55. Use inpaint_room if floor fidelity matters.

### SDXL IP-Adapter / LoRA
40. **SDXL IP-Adapter uses `comfyui_ipadapter_plus`** (IPAdapterModelLoader + IPAdapterAdvanced), NOT the SD3 `ComfyUI-InstantX-IPAdapter-SD3` node.
41. **SDXL IP-Adapter uses CLIP ViT-H** (`clip_vision_vit-h.safetensors`), NOT SigLIP.
42. **IP-Adapter `CLIPVisionEncode` requires `"crop": "center"` field** — omitting causes "Required input is missing: crop" error.
43. **`VAEEncode` is safe with SDXL on MPS** — the NaN issue was SD3.5-specific.
44. **Interior LoRA (AresWei) embeds a watermark at strength ≥0.8** — visible as text bottom-right. Max 0.5. Trigger word `mrares` at start of prompt.
45. **LoRA not used in `generate_image` or `transfer_style`** — generate_image should stay versatile; transfer_style has IP-Adapter driving style already (stacking overconstrains).
46. **SDXL negative prompts work correctly** — UNet cross-attention handles them properly. Restore full negative strings from any SD3.5 code being migrated.

### transform_image (InstantID)
47. **img2img cannot satisfy "same face, new scene" simultaneously** — at denoise ≤0.55 preserves composition but barely changes; ≥0.65 rewrites faces. Fundamental architectural constraint.
48. **IP-Adapter + EmptyLatentImage is the correct architecture** — source as IP-Adapter conditioning, generate from Empty latent + denoise=1.0. Scene/composition from text; appearance from IP-Adapter.
49. **IP-Adapter `plus` ≠ face transplant** — encodes full-image features; SDXL generates the face. For pixel-identical face identity, `ip-adapter-faceid-plusv2_sdxl.bin` + insightface required (not currently installed).
50. **InstantID uses antelopev2 face model**, NOT buffalo_l. Auto-downloads (~170MB) to `models/insightface/models/antelopev2/`.
51. **InstantID ip-adapter filename is `ip-adapter.bin`**, NOT `ip-adapter_instant_id_sdxl.bin`. Exact filename required — `InstantIDModelLoader` enumerates `models/instantid/`.
52. **antelopev2 auto-extraction creates nested directory** — extracts to `.../antelopev2/antelopev2/*.onnx`. Node looks for files directly under `.../antelopev2/` → `AssertionError: 'detection' in self.models`. Fix: flatten one level, delete zip.
53. **InstantID source fidelity:** ≥1024×1024 with face ~40–60% of frame. Smaller sources → InsightFace downscales detection → pixelated output.
54. **UltralyticsDetectorProvider is in Impact-Subpack**, NOT Impact-Pack. Both repos must be installed for FaceDetailer workflow.
55. **InstantID keypoint ControlNet drives expression, not just identity** — `ApplyInstantID` bundles IP-Adapter identity embedding AND keypoint ControlNet (5-pt landmarks). With `end_at: 1.0`, mouth-corner positions lock through all steps → prompts for expression affect upper face more than lower. Shorten `end_at` (→ 0.5) to release keypoints mid-sampling, giving text control over mouth; FaceDetailer re-locks identity. Alternative: `ApplyInstantIDAdvanced` separates ip_weight from cn_strength.

### Watermark
56. **PIL watermark re-upload uses `&type=input`** — after stamping, image is uploaded to ComfyUI's `/upload/image` with `type=input`. HTTPS URL returned to OWUI must include `&type=input` (not `output`) or ComfyUI returns 404.

---

## Quick Reference Commands

```bash
# Start ComfyUI
cd ~/ComfyUI/ComfyUI && ./start_comfyui.sh

# Check model files
ls -lh models/checkpoints/ models/loras/ models/vae/ models/controlnet/

# View recent generated images
ls -lt output/ | head -20 && open output/

# Update ComfyUI core
cd ~/ComfyUI/ComfyUI && git pull

# Deploy tool changes
cd ~/ComfyUI/ComfyUI && ./deploy_tool.sh

# Kill + restart (MPS NaN recovery)
kill $(lsof -ti :8189) && cd ~/ComfyUI/ComfyUI && ./start_comfyui.sh
```

---

## Related Project Files

Canonical documentation lives in `~/claude-project-docs/`:

| File | Contents |
|------|----------|
| `ComfyUI_Image_Generation_Guide.md` | Full workflows, prompts, parameters, troubleshooting |
| `ComfyUI_Project_Summary_Supplement.md` | Production validation, Tailscale fix, node inventory |
| `LLM_Project_Changelog_v2_Mac.md` | Full phase history (2–13) and session narratives |
| `LLM_Full_Project_Summary_v2.md` | Master architecture + status dashboard |
| `Quick_Reference_Commands.md` | All service commands and port table |
