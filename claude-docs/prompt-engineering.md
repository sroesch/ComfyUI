# Prompt Engineering — SDXL + FLUX.2 klein

FLUX.2 klein prompt style is per mode (prose for T2I, imperative + preserve clause for EDIT, fill-only for PAINT) — see the mode table in [models.md](./models.md). The FLUX.1 dual-encoder (clip_l/t5xxl) rules were retired with FLUX.1-schnell on 2026-09-25.

## SDXL — CLIPTextEncodeSDXL

- `text_g` = full NL description.
- `text_l` = comma-separated keywords.
- Negative prompts work as expected (UNet cross-attention).
- `SDXL_NEGATIVE` must block architectural-hallucination vocab: crown molding, coffered/tray ceiling, recessed lighting, curtains, drapes, wallpaper, remodeled, renovated, different room.

## Real Estate Prompt Rules

- Always specify lighting, materials, camera style ("professional real estate photography").
- San Diego context: stucco, palm trees, desert landscaping, blue agave.
- Prefer specificity: "white Carrara marble with grey veining" > "beautiful kitchen".
- **`stage_room` prompt scope: furniture and décor ONLY** — architectural terms cause the model to remodel even with ControlNet. Let the ControlNet hold geometry; use text for soft furnishings only.
