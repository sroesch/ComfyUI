# ComfyUI — Model Decision Matrix + Parameters

## Decision matrix

| Use Case | Model | Reason |
|----------|-------|--------|
| Social media / blog | FLUX.1-schnell | ~24s, fast iteration |
| Print / MLS photos | SDXL Juggernaut XL | Photorealistic, LoRA ecosystem, negative prompts work |
| Restyling furnished rooms | SDXL `stage_room` | Dual ControlNet depth+MLSD, Interior LoRA |
| Placing furniture in empty rooms | SDXL `inpaint_room` | Fooocus inpaint + SAM auto-mask or manual clipspace mask |
| Style transfer from reference | SDXL `transfer_style` | IP-Adapter Plus SDXL + ControlNet depth |
| Face-locked portrait/headshot | SDXL `transform_image` | InstantID + 2-pass FaceDetailer |
| FLUX.2 edit/staging experiments | FLUX.2 [klein] 9B (one-node) | Modern edit/inpaint/outpaint in a single node; **9B = personal/non-commercial only** (see license note) |

**Cannot run FLUX and SDXL simultaneously** — sequential only.

## FLUX.1-schnell parameters

```
DualCLIPLoader:  clip_name1=clip_l, clip_name2=t5xxl_fp16, type=flux
KSampler:        cfg=1.0 (MUST be 1.0 for distilled; higher = severe artifacts)
                 steps=4, sampler=euler, scheduler=simple
VAE:             flux_vae.safetensors
Canvas:          1024×1024
```

## SDXL — Juggernaut XL (primary for all room workflows)

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

## FLUX.2 [klein] (one-node-flux-2-klein)

Single all-in-one node (T2I/I2I/EDIT/PAINT/FACESWAP/POSE). Loaded as native single-file `.safetensors` in `diffusion_models/` **or** via an external `Unet Loader (GGUF)` node. There is **no official Comfy-Org single-file repackage of klein-9B** (only flux2-*dev* has one), and BFL's repo is gated diffusers-only — so on this box the model is sourced as **GGUF** fed through the external loader.

**9B file set (currently installed):**

```
diffusion_models/   flux-2-klein-9b-BF16.gguf        (unsloth GGUF, 17 GiB, full-precision)
text_encoders/      qwen_3_8b.safetensors            (Comfy-Org, 15 GiB — MUST match the model; not interchangeable)
vae/                flux2-vae.safetensors            (Comfy-Org, 321 MB)
loras/              bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors   (Faceswap mode)
loras/              refcontrol_v2_poses.safetensors  (POSE mode)
background_removal/ birefnet.safetensors             (PAINT → Remove BG)
```

**Wiring:** node Settings → enable "External model/clip/vae inputs" → `Unet Loader (GGUF)` → model slot = `flux-2-klein-9b-BF16.gguf`; text-encoder dropdown = `qwen_3_8b.safetensors`; VAE dropdown = `flux2-vae.safetensors`. The GGUF model **must** come through the external loader — the node's MODEL dropdown scans only `.safetensors/.ckpt/.pt/.pth`, so a `.gguf` never appears there. CLIP/VAE stay on their dropdowns: an unconnected external socket falls back to the dropdown value, so no CLIPLoader/VAELoader node is needed for plain `.safetensors` encoders/VAE.

**Mode mechanics** (the modes are different *mechanisms*, not flavors of one thing — pick by job):

| Mode | Mechanism | Use for | Prompt style |
|---|---|---|---|
| **T2I** | text → image from noise | generate from scratch | full scene description (natural-language prose) |
| **I2I** | img2img, denoise overwrite | loose reinterpretation of one image | describe the whole desired final image |
| **EDIT** | reference-latent (Kontext); up to **2** ref images | "change X, keep the rest" / combine two images | **imperative** instruction + explicit *preserve* clause |
| **PAINT** | masked inpaint/outpaint | surgical change to one region | describe **only what fills the mask** |

- **"Change Strength" slider = the I2I KSampler `denoise`**, 1:1 (75% → 0.75). Just renamed in the UI.
- **I2I has a change-vs-preserve wall for big edits:** low denoise (≤0.6) preserves layout but won't apply a large material/color swap at all (at CFG 1 there's no guidance to overcome the input-image prior); high denoise (0.75) applies the change but drifts the layout. No single global-denoise value does both — use **EDIT or PAINT** for staging swaps, not I2I.
- **EDIT region-scope bleed:** location words ("back wall", "perimeter") catch *every* surface in that zone (e.g. a "back wall counter" instruction also recolors the backsplash). Disambiguate by naming the preserved element **and its material** ("keep the white Calacatta marble island unchanged").
- **PAINT mask = location AND size/quantity:** the model fills the masked *volume*, so an oversized mask yields oversized/extra objects (a single-sofa prompt on a large mask produced a whole sectional). Mask the object's full volume incl. vertical height (a sofa's back, not just its floor footprint); add a grounding cue ("realistic contact shadows on the floor") for believable furniture; build complex scenes in **layered passes** (furniture, then rug separately).
- **Steps:** klein is step-distilled (~4 optimal). More steps ≠ more prompt adherence (that's guidance) and ≠ more change (that's denoise). In img2img, *effective* steps = `steps × denoise`, so when you lower Change Strength, raise steps to keep detail from going undercooked.
- **CFG stays at 1** (klein is guidance-distilled). Raising it breaks output; negative prompts do ~nothing at CFG 1.

> General image-gen terminology (denoise, CFG, sampler, scheduler, GGUF vs NVFP4/DF11, etc.) lives in `~/claude-project-docs/Image_Generation_Glossary.md` — a model-agnostic quick reference with Apple-Silicon format guidance.

**4B alternative:** same node, swap GGUF for the 4B diffusion model + `qwen_3_4b` text encoder. 4B is **Apache 2.0 (commercial OK)**; preferred for any listing/marketing work.

**License (klein 9B):** FLUX Non-Commercial License v2.1. §2-b limits *model use* to Non-Commercial Purposes; §1-c excludes revenue-generating / business / end-user-facing use; §4-a(i) expressly bars commercial/production use of the model *and* "any data produced by" it. The §2-d "Outputs may be used commercially" clause is gated by "except as expressly prohibited herein" → 4-a(i). Net: 9B = personal/experimentation only; use 4B (Apache) or a BFL commercial license (bfl.ai/licensing; Builder tier is the self-serve one) for real listing output.

## OWUI tool model constants (verify at top of `openwebui_tool_comfyui.py`)

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

## Memory footprint (128 GB unified)

| Config | Unified Memory |
|--------|----------------|
| FLUX generation | ~32 GB |
| SDXL generation | ~20 GB |
| oMLX `Qwen3.6-35B-A3B-8bit` loaded | ~35 GB (8-bit weights) |
| oMLX + SDXL concurrent | ~55 GB (est. — sum of weights) |
| SDXL + InstantID + FaceDetailer | ~35–40 GB |
| ComfyUI idle | <2 GB |

## Canvas sizes (`inpaint_room`)

- `landscape` = 1152×768 (MLS 3:2 default)
- `portrait` = 768×1024
- `square` = 1024×1024

## SD3.5 legacy

`sd3.5_large.safetensors`, `sd3.5_vae.safetensors`, `sd3.5_large_controlnet_depth.safetensors` remain on disk but are inactive — safe to delete once SDXL is fully validated.
