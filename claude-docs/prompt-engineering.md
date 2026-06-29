# Prompt Engineering — FLUX + SDXL

## FLUX — Dual Encoder

- `clip_l` (77-token hard limit): short comma-separated keywords — search-tag / hashtag style.
- `t5xxl` (~unlimited): full natural language description, materials, lighting, atmosphere, camera style.
- Negative prompts: same short phrase in both inputs (`blurry, low quality, distorted, dark`).

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
