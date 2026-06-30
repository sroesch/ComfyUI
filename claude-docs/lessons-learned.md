# Lessons Learned — ComfyUI Stack

Hard-won lessons from building, deploying, and running the SDXL/FLUX stack. OWUI-tool-specific lessons live in [integrations.md](./integrations.md).

## Infrastructure / macOS

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

## ComfyUI workflow format

12. **Litegraph JSON required for v0.7.0** — flat API format (`{id: {class_type, inputs}}`) is rejected with Zod validation error. Need `version: 0.4`, `nodes: [...]` (each with `id, type, pos, size, flags, order, mode, inputs, outputs, properties, widgets_values`), `links: [...]`, `last_node_id`, `last_link_id`.
13. **`ImageScale` widgets_values positional order: method first** — correct: `["lanczos", 1024, 1024, "disabled"]`. Width-first breaks with sampler/scheduler type errors at runtime.
14. **`ImageToMask` requires `channel` field** — use `"red"` for greyscale masks (all channels identical).
15. **`ImageBlur` blur_radius max=31** — 12 produces good gradient softness at 1024×1024.

## SAM / GroundingDINO (`inpaint_room` auto-mask)

16. **`comfyui_segment_anything` requires `timm==0.9.2`** — newer timm breaks `sam_hq` (RotaryEmbedding missing from `timm.layers.attention_pool2d`).
17. **Class_type suffix:** `"GroundingDinoModelLoader (segment anything)"` etc. — without suffix ComfyUI returns 400. Verify via `curl .../object_info | python3 -c "..."`.
18. **SAM `model_name` fields use display names, not filenames** — `"sam_vit_l (1.25GB)"` not `"sam_vit_l_0b3195.pth"`.
19. **GroundingDINO auto-downloads on first inpaint_room call** — `groundingdino_swint_ogc.pth` (~662 MB) to `models/grounding-dino/`.
20. **Auto-mask "floor" is too blunt for large empty rooms** — SAM detects entire floor as one mask; furniture scatters, bleeds to hearths/walls. Use `threshold=0.4+` or manual clipspace mask for precision.
21. **DepthAnythingV2Preprocessor auto-downloads** `depth_anything_v2_vitl.pth` (~335 MB) on first stage_room call.

## Mask discipline (`inpaint_room`)

22. **White inpaint output = IMAGE tensor has white paint baked in** — uploading a pre-painted image means MASK is all-zeros (no alpha) and the white pixels are encoded. Always use ComfyUI's built-in mask editor (right-click LoadImage → Open in MaskEditor); clipspace stores mask separately.
23. **Mask boundary rules:** upper edge at/below baseboard; keep mask 200 px+ from walls; tight rectangular mask parallel to target wall, not a floor flood. Bleed into windows/doors confuses the model at top boundary.
24. **`mask_expand=150` is too large for sofa** — produced oversized mammoth sofa. Use 20–40 px for standard furniture; 80 px+ only for tall items (bookcases, full-height cabinets).

## SDXL architectural rules

25. **img2img without ControlNet restyles rooms, does NOT place furniture** — spatial object placement requires ControlNet depth.
26. **`stage_room` vs `inpaint_room` — hard distinction:** stage_room (img2img) restyles rooms that already have furniture; inpaint_room places new furniture in empty rooms by masking target floor area. Using stage_room to furnish an empty room produces partial furnishings with creative liberties.
27. **ControlNetApplyAdvanced does NOT take a vae input** (unlike SD3's ControlNetApplySD3). SDXL ControlNet conditioning goes through standard positive/negative CONDITIONING.
28. **Dual ControlNet chaining:** node A (depth) takes raw CLIP → node B (canny/MLSD) takes node A outputs → KSampler takes node B outputs. Both accumulate on same conditioning tensors.
29. **M-LSDPreprocessor inputs differ from CannyEdgePreprocessor** — MLSD uses `score_threshold`+`dist_threshold` (both default 0.1); Canny uses `low_threshold`+`high_threshold`. `controlnet-canny-sdxl-1.0.safetensors` is reusable with MLSD output (structurally similar).
30. **ControlNet end_percent must cover >50% of steps** to prevent architectural hallucination. At 50 steps, end_percent=0.4 covers only steps 1–20; 21–50 run with NO structural guidance and the model faithfully remodels to match style prompt. Sweet spot: 0.5–0.6.
31. **stage_room prompt scope: furniture and décor ONLY** — crown molding / recessed lighting / wall color instruct the model to remodel. ControlNet handles geometry; text handles furnishings.
32. **`SDXL_NEGATIVE` must block architectural vocab** (crown molding, coffered ceiling, recessed lighting, curtains, wallpaper, remodeled, renovated, different room) — otherwise they appear even without being in positive prompt.
33. **Floor textures in stage_room change unpredictably** — floors are nearly flat in depth map so ControlNet barely constrains them. Model rewrites floor freely at denoise≥0.55. Use inpaint_room if floor fidelity matters.

## SDXL IP-Adapter / LoRA

34. **SDXL IP-Adapter uses `comfyui_ipadapter_plus`** (IPAdapterModelLoader + IPAdapterAdvanced), NOT the SD3 `ComfyUI-InstantX-IPAdapter-SD3` node.
35. **SDXL IP-Adapter uses CLIP ViT-H** (`clip_vision_vit-h.safetensors`), NOT SigLIP.
36. **IP-Adapter `CLIPVisionEncode` requires `"crop": "center"` field** — omitting causes "Required input is missing: crop" error.
37. **`VAEEncode` is safe with SDXL on MPS** — the NaN issue was SD3.5-specific.
38. **Interior LoRA (AresWei) embeds a watermark at strength ≥0.8** — visible as text bottom-right. Max 0.5. Trigger word `mrares` at start of prompt.
39. **LoRA not used in `generate_image` or `transfer_style`** — generate_image should stay versatile; transfer_style has IP-Adapter driving style already (stacking overconstrains).
40. **SDXL negative prompts work correctly** — UNet cross-attention handles them properly. Restore full negative strings from any SD3.5 code being migrated.

## `transform_image` (InstantID)

41. **img2img cannot satisfy "same face, new scene" simultaneously** — at denoise ≤0.55 preserves composition but barely changes; ≥0.65 rewrites faces. Fundamental architectural constraint.
42. **IP-Adapter + EmptyLatentImage is the correct architecture** — source as IP-Adapter conditioning, generate from Empty latent + denoise=1.0. Scene/composition from text; appearance from IP-Adapter.
43. **IP-Adapter `plus` ≠ face transplant** — encodes full-image features; SDXL generates the face. For pixel-identical face identity, `ip-adapter-faceid-plusv2_sdxl.bin` + insightface required (not currently installed).
44. **InstantID uses antelopev2 face model**, NOT buffalo_l. Auto-downloads (~170 MB) to `models/insightface/models/antelopev2/`.
45. **InstantID ip-adapter filename is `ip-adapter.bin`**, NOT `ip-adapter_instant_id_sdxl.bin`. Exact filename required — `InstantIDModelLoader` enumerates `models/instantid/`.
46. **antelopev2 auto-extraction creates nested directory** — extracts to `.../antelopev2/antelopev2/*.onnx`. Node looks for files directly under `.../antelopev2/` → `AssertionError: 'detection' in self.models`. Fix: flatten one level, delete zip.
47. **InstantID source fidelity:** ≥1024×1024 with face ~40–60% of frame. Smaller sources → InsightFace downscales detection → pixelated output.
48. **UltralyticsDetectorProvider is in Impact-Subpack**, NOT Impact-Pack. Both repos must be installed for FaceDetailer workflow.
49. **InstantID keypoint ControlNet drives expression, not just identity** — `ApplyInstantID` bundles IP-Adapter identity embedding AND keypoint ControlNet (5-pt landmarks). With `end_at: 1.0`, mouth-corner positions lock through all steps → prompts for expression affect upper face more than lower. Shorten `end_at` (→ 0.5) to release keypoints mid-sampling, giving text control over mouth; FaceDetailer re-locks identity. Alternative: `ApplyInstantIDAdvanced` separates ip_weight from cn_strength.

## Watermark

50. **PIL watermark re-upload uses `&type=input`** — after stamping, image is uploaded to ComfyUI's `/upload/image` with `type=input`. HTTPS URL returned to OWUI must include `&type=input` (not `output`) or ComfyUI returns 404.

## FLUX.2 [klein] / GGUF

51. **ComfyUI cannot load MLX models** — it runs on PyTorch/Metal (MPS); MLX is a separate runtime (oMLX, Draw Things, DiffusionKit). The stack's `~/Models/Qwen3.5-9B-MLX-8bit` (and any `mlx-community/*`) is unusable as a ComfyUI text encoder. Need a PyTorch `.safetensors`.
52. **Diffusion text encoders are NOT interchangeable** — the transformer is trained against one specific encoder's embedding space. FLUX.2 klein 9B requires the **matching `qwen_3_8b`** (Qwen3-8B, older gen) — a newer/bigger Qwen (e.g. Qwen3.5-9B) produces noise, not "better" output. Same logic blocks substituting any "upgraded" encoder.
53. **No official Comfy single-file repackage of klein-9B** — only flux2-*dev* has one; BFL's `FLUX.2-klein-9B` is gated + diffusers-only (sharded folder), which the one-node loader can't read (it scans single-file `.safetensors/.ckpt/.pt/.pth`). Path on this box: **GGUF** (unsloth, public, no gate) via `ComfyUI-GGUF`'s `Unet Loader (GGUF)` → node's external-loader slot. BF16 GGUF (17 GiB) is full-precision, so no quality loss; 128 GB RAM makes quantization unnecessary (quants exist for small-VRAM, not us).
54. **klein 9B is FLUX Non-Commercial License v2.1** — personal/experimentation only. §4-a(i) is the express bar (covers model *and* "any data produced by" it for commercial/production); §2-d's commercial-output clause is gated by it. For listing/marketing output use **4B (Apache 2.0)** or a BFL commercial license. See [models.md](./models.md) FLUX.2 section.
55. **GGUF model never shows in the one-node MODEL dropdown** — the dropdown scans only `.safetensors/.ckpt/.pt/.pth` (verified in `nodes.py`). A `.gguf` MUST be wired via Settings → "External model/clip/vae inputs (for GGUF etc.)" toggle → `Unet Loader (GGUF)` → the node's `model` socket. The toggle being ON is required for the wired socket to be used ("toggle off = external inputs ignored even if a wire is connected"). CLIP/VAE can stay on their dropdowns — an unconnected external socket falls back to the dropdown value (`_extSlot` returns null → `else set(...)`), so no CLIPLoader/VAELoader node is needed for plain `.safetensors`. Symptom that confused: VAE/encoder/LoRAs populate but model is "missing" → it's not missing, GGUF just isn't a dropdown-eligible type.
56. **"Change Strength" = the I2I KSampler `denoise`, 1:1** (75% → 0.75; `S.i2iDenoise = pct/100` → `set("FK:171","denoise",…)`). The node author just renamed denoise to plain English. Steps/CFG/sampler/scheduler in the Advanced panel feed the same sampler.
57. **klein I2I can't do "big change + locked layout" at any global denoise** — empirically across 0.45/0.60/0.75: low denoise preserves geometry but won't apply a large material/color swap at all (at CFG 1 there's no guidance to overcome the input-image prior); 0.75 applies the change but drifts the whole room. This is the img2img mechanism's limit, not a klein flaw. For staging swaps use EDIT or PAINT instead.
58. **EDIT mode is reference-latent (Kontext) instruction editing, not img2img** — routes the image through `ReferenceLatent` nodes (supports up to **2** images for element-combining, e.g. "put the jacket from image 2 on the person in image 1"). It lands large changes *while* preserving layout where I2I can't. Two traps: (a) prompt is **imperative** ("Change the cabinets to green. Keep everything else the same"), NOT a full-scene description — over-describing causes drift; (b) **location-scope words bleed** — "perimeter counters along the back wall" also recolored the backsplash (it's on the back wall). Defend a preserved element by naming it + its material explicitly.
59. **PAINT mask controls object SIZE/COUNT, not just location** — the model fills the masked *volume*, so an oversized mask produced a whole sectional from a single-sofa prompt, oversized. Mask the object's full volume incl. **vertical height** (a sofa's back rises off the floor — a floor-only mask squashes it). Always add a grounding cue ("realistic contact shadows on the wood floor") for believable furniture. Inpaint prompt describes **only the masked fill**, not the room. Build complex scenes in **layered passes** (sofa, then rug as a separate mask) for clean control. PAINT is the bleed-proof tool — you draw the boundary instead of describing it.
