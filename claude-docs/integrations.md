# OpenWebUI + n8n Integrations

## OpenWebUI Integration

**Tool source:** `~/ComfyUI/ComfyUI/openwebui_tool_comfyui.py` (edit here → `./deploy_tool.sh`).
**Internal API call:** `http://host.docker.internal:8189` (from inside OWUI Docker).
**Image URLs returned:** `https://stevens-mac-studio.tail7c9d1c.ts.net/comfyui/view?filename=...` (HTTPS via Caddy).

### Tool functions

| Function | Description | Timeout | Notes |
|----------|-------------|---------|-------|
| `generate_image(prompt, model)` | txt2img; model="flux" or "sdxl"; no LoRA on SDXL path | — | Imperative param description routes correctly to SDXL for MLS prompts (v5.9.2 fix) |
| `transform_image(prompt, appearance_strength, image_url)` | InstantID + 2-pass FaceDetailer | 360s | Prompt = attire/scene only. Status string echoes `appearance_strength` (signature name) to prevent confabulation |
| `edit_image(prompt, image_url, denoise)` | img2img + Interior LoRA; room restyling | — | denoise=0.65 default |
| `stage_room(prompt, denoise, controlnet_strength)` | Dual ControlNet (depth+MLSD) + Interior LoRA + watermark | 300s | 50 steps; furnished room restyling |
| `inpaint_room(prompt, mask_subject, denoise, threshold, mask_expand, canvas_size)` | SAM auto-mask + Fooocus inpaint + Interior LoRA + watermark | 480s | Furniture in empty rooms |
| `transfer_style(prompt, style_strength)` | IP-Adapter Plus + ControlNet depth; no LoRA | 360s | Attach reference (1st) + room (2nd) |

### OWUI Workspace Settings

- **Function Calling = Native** (not Default — Default outputs `<tool_code>` text).
- System prompt inline-image rule: after any tool returns a URL, embed as `![image](url)`.
- Prompt passthrough rule: pass user text verbatim; do not paraphrase, simplify, or interpret.

### Deploy workflow

Edit `.py` → `./deploy_tool.sh` → live in OWUI. API key in `.env` (OWUI "Create new secret key" button is broken; key inserted directly into SQLite `api_key` table as workaround).

### OWUI tool integration lessons

- **OWUI image URLs must use HTTPS** (port 443 via Caddy `/comfyui/*` route). HTTP URLs get HSTS-upgraded → break.
- **OWUI API key button broken** — backend returns 403 "not allowed in environment" even with `ENABLE_API_KEY=true`. Workaround: insert key via `docker exec` into SQLite `api_key`. Key stored in `.env`.
- **`deploy_tool.sh`** pushes via REST API — no copy-paste.
- **OWUI LLM paraphrases and strips spatial detail** from prompts — routing LLM summarizes before calling tool. Add explicit "Prompt passthrough (MANDATORY)" rule to system prompt.
- **OWUI tool status messages teach the LLM parameter names** — every friendly label gets interpreted as the canonical param. Rule: always use the literal signature param name in status messages (`appearance_strength=0.8`), even at the cost of friendliness. The tool's output is a more reliable teacher than the system prompt.
- **Qwen confabulates technical explanations** when a tool call produces unexpected output (because the LLM's own kwarg was dropped). Mitigate with: (a) explicit param-name enforcement in system prompt, (b) status-message discipline, (c) BOUNDARIES rule forbidding confabulation.
- **OWUI tool param descriptions targeting LLM argument routing must be imperative, not informative.** "FLUX is fast, SDXL is detailed" describes the options; the model reads it, decides in CoT which one fits, but doesn't reliably emit the kwarg in the function call. "ALWAYS pass `model='sdxl'` for X, Y, Z; pass `'flux'` only for W" instructs the model.

## n8n Integration

Planned (medium-term). See `~/claude-project-docs/n8n_Project_Summary.md` § 7. Concept: n8n workflow triggers ComfyUI API → image generated → uploaded to Google Drive or output tab in Google Sheets as part of marketing content pipeline.
