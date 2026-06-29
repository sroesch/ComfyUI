# ComfyUI Roadmap

## Phases 2–11 ✅ Complete

Per-phase narrative lives in `~/claude-project-docs/LLM_Project_Changelog_v2_Mac.md`. High-level snapshot:

- **Phases 2–7** built the SD3.5 baseline (img2img, ControlNet depth, SAM/GroundingDINO auto-mask, IP-Adapter style transfer, manual-mask inpaint).
- **Phase 8** migrated the entire room workflow stack to **SDXL Juggernaut XL** (replacing SD3.5).
- **Phases 8.5–9.1** added `transform_image` (IP-Adapter Plus → InstantID + 2-pass FaceDetailer), MLSD ControlNet, Fooocus inpaint precursors, watermark, and architectural-fidelity tuning (depth/MLSD end_percent 0.55, MLSD strength 0.35, denoise 0.65).
- **Phase 11** swapped inpaint to Fooocus algorithm (`INPAINT_LoadFooocusInpaint` + `INPAINT_VAEEncodeInpaintConditioning` + `INPAINT_ApplyFooocusInpaint`), added `canvas_size` param to `inpaint_room`, deployed dashboard split (`~/dashboard/` standalone), shipped Virtual Staging tab. Tool v5.9.0.

## Phase 12 🟡 In progress

OWUI tool quality + identity/expression control on `transform_image`.

- **v5.9.2 directive `:param model:` description** — `generate_image` docstring rewritten from informative to imperative ("ALWAYS pass `model='sdxl'` for real-estate / MLS / interior / staging work"). Fixes the routing failure where Qwen's CoT decided "use sdxl" but never emitted the kwarg, leaving tool default `flux` to win. Smoke-test confirms Juggernaut XL loads on first attempt.
- **antelopev2 nesting fix** — auto-extracted as `antelopev2/antelopev2/*.onnx` causing `AssertionError`. Fix: flatten one level and delete zip.
- **Identity lock solid** at `appearance_strength=0.8` with 1024×1024 source (face 40–60% of frame). Smaller sources cause InsightFace to downscale detection → pixelated output.
- **Status-message hallucination fix (v5.9.1)** — both pre-run emit and return string echo `appearance_strength=X` matching the signature, blocking the prior "identity_lock_strength" confabulation chain.
- **Expression control characterized — NOT YET FIXED.** InstantID keypoint ControlNet (active via `end_at: 1.0`) projects source mouth-corner positions into output. Prompts for "scowl" land brows ~50% of the time but mouth stays smiling. Candidate fix pending empirical test: shorten `end_at` on `ApplyInstantID` to 0.5.
- **OWUI General Chat system prompt** now includes prompt-refinement escape hatch, AVAILABLE SKILLS block, `appearance_strength` param-name enforcement, MJ-flag stripping, InstantID no-face-descriptors rule, confabulation-guard rule.
- **SDXL Prompt Writing skill v2** drafted at `~/Desktop/SDXL_Prompt_Writing_v2.md`.

## Phase 13 — Next

- **Step 3:** real `appearance_strength=0.5` scowl test — verify system-prompt passthrough. (a) success → document; (b) brow-only → proceed to end_at=0.5.
- **Step 4 (conditional):** `end_at: 1.0 → 0.5` on `ApplyInstantID` (line 755 in tool source), bump to v5.10.0. If identity loss too severe, migrate to `ApplyInstantIDAdvanced` (separate `ip_weight` / `cn_strength` / independent start-end).
- User feedback on staging tab — pending.
- Export SDXL inpaint workflow as litegraph JSON (never re-exported post-Phase-8).
- LoRA replacement — find interior LoRA without embedded watermark.
- n8n ComfyUI integration (medium-term).

## Digital staging note

Digital staging for vacant listings requires at minimum: img2img + ControlNet depth model. FLUX alone (text-to-image) is not sufficient. ControlNet is what makes geometry-aware furniture placement reliable.
