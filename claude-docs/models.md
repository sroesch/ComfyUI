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
| Ollama qwen3.5:35b loaded | ~20–25 GB |
| Ollama + SDXL concurrent | ~40–45 GB |
| SDXL + InstantID + FaceDetailer | ~35–40 GB |
| ComfyUI idle | <2 GB |

## Canvas sizes (`inpaint_room`)

- `landscape` = 1152×768 (MLS 3:2 default)
- `portrait` = 768×1024
- `square` = 1024×1024

## SD3.5 legacy

`sd3.5_large.safetensors`, `sd3.5_vae.safetensors`, `sd3.5_large_controlnet_depth.safetensors` remain on disk but are inactive — safe to delete once SDXL is fully validated.
