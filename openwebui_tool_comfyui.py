"""
title: ComfyUI Image Generator
author: Steven
description: Generate and transform images with FLUX.1-schnell or SDXL/Juggernaut XL. Methods: generate_image (txt2img), transform_image (IP-Adapter appearance transfer, general use), edit_image (img2img+LoRA, rooms), stage_room (dual ControlNet depth+MLSD staging, 50 steps, MLS watermark), inpaint_room (Fooocus inpaint algorithm + SAM/rect mask, MLS watermark, 1152x768 landscape), transfer_style (IP-Adapter+ControlNet depth).
version: 5.9.2
requirements: aiohttp
"""

# ---------------------------------------------------------------------------
# Model filename constants — update these if you rename files after download
# ---------------------------------------------------------------------------
# CivitAI downloads (manual — requires account):
#   Juggernaut XL v10: https://civitai.com/models/133005
#   Interior-Design-Universal SDXL LoRA: https://civitai.com/models/176807
SDXL_CHECKPOINT   = "juggernautXL_ragnarokBy.safetensors"
INTERIOR_LORA     = "E5AEA4E58685E79A84E7A68FE99FB320E5AEA4E5.fDUS.safetensors"
LORA_STRENGTH     = 0.5   # Reduced from 0.8 — LoRA embeds a watermark at higher strengths

# HuggingFace downloads (auto-downloaded via curl on session start):
SDXL_VAE           = "sdxl-vae-fp16-fix.safetensors"           # madebyollin/sdxl-vae-fp16-fix
CONTROLNET_DEPTH   = "control-lora-depth-rank256.safetensors"   # stabilityai/control-lora
CONTROLNET_CANNY   = "controlnet-canny-sdxl-1.0.safetensors"   # xinsir/controlnet-canny-sdxl-1.0
IPADAPTER_SDXL     = "ip-adapter-plus_sdxl_vit-h.safetensors"  # h94/IP-Adapter sdxl_models/
CLIP_VISION_VIT_H  = "clip_vision_vit-h.safetensors"            # already present

# InstantID (transform_image) — InstantX/InstantID on HuggingFace
INSTANTID_MODEL    = "ip-adapter.bin"                           # models/instantid/
INSTANTID_CONTROLNET = "instantid_controlnet_sdxl.safetensors"  # models/controlnet/ (renamed from ControlNetModel/diffusion_pytorch_model.safetensors)
INSTANTID_BBOX_DETECTOR = "bbox/face_yolov8m.pt"               # models/ultralytics/bbox/ (Bingsu/adetailer)

# SDXL KSampler defaults (DPM++ 2M Karras — community standard for SDXL)
SDXL_SAMPLER   = "dpmpp_2m"
SDXL_SCHEDULER = "karras"
SDXL_STEPS     = 30
SDXL_CFG       = 7

# Standard SDXL negative prompt — active for all methods (MMDiT SD3.5 ignored these; SDXL UNet uses them correctly)
SDXL_NEGATIVE = (
    "blurry, low quality, distorted, dark, heavy shadows, furniture floating, "
    "unrealistic lighting, poor composition, mismatched scale, oversized furniture, "
    "tiny furniture, empty room, bare walls, clutter, messy, outdated decor, "
    "cartoonish, painting, illustration, fisheye distortion, string lights, "
    "hanging lights, Edison bulbs, pendant lights on beams, bistro lights, rope lights, "
    "crown molding, coffered ceiling, tray ceiling, recessed lighting, ceiling fixtures, "
    "curtains, drapes, window treatments, wallpaper, painted walls, "
    "remodeled, renovated, different room, "
    "shelving unit, built-in shelves, built-in bookcase, bookcase wall, entertainment wall, "
    "feature wall, wall panels, decorative panels, panel wall, tile wall, stone tile wall, "
    "herringbone wall, chevron wall, removed fireplace, no fireplace, replaced fireplace, "
    # Floor material protection — block both lightening AND the striped exotic-wood pattern (v5.6 failure)
    "light wood floor, blonde wood floor, light oak floor, pale floor, light hardwood, maple floor, whitewashed floor, "
    "striped hardwood, exotic hardwood, tiger wood floor, multi-tone floor, wood grain stripes, rosewood floor, patterned floor planks, "
    # Outdoor staging prevention — model staged patio furniture through sliding glass doors in T2
    "outdoor furniture, patio furniture, patio chairs, patio table, outdoor seating, deck furniture, backyard furniture, "
    # Tufted/padded focal-wall elements — T2 primary failure: fireplace replaced by tufted panel
    "tufted wall, padded wall, upholstered wall panel, fabric wall panel, headboard wall, tufted headboard, "
    # Storage/console units at hearth level — T1 failure: hearth area replaced by wicker bench/drawer unit
    "storage bench, wicker console, rattan console, storage console, media console, bench unit, drawer unit, "
    # Left wall hallucination — empty wall gets filled with wardrobe/cabinet elements (v5.6 failure)
    "wardrobe, armoire, closet, wall cabinet, built-in cabinet, white cabinetry, wall unit, "
    # Brick texture drift — prevent golden brick shifting to rough limestone/stone-block (v5.6 T2 failure)
    "limestone wall, travertine wall, rough stone wall, stone block wall, rough stone, "
    # Ceiling beam regression — bohemian/coastal vocab (jute, linen, fiddle-leaf) pulls beams toward bamboo/rattan
    "bamboo beam, rattan beam, bamboo ceiling, rattan ceiling, light wood beam, tan beams, "
    "blonde beams, natural beam, cylindrical beam, wrapped beam, whitewashed beam"
)

# Neutral negative prompt for general-purpose image transformation (no real-estate terms)
TRANSFORM_NEGATIVE = (
    "blurry, low quality, distorted, deformed, bad anatomy, extra limbs, "
    "duplicate, watermark, text, signature, ugly, gross, disfigured"
)

import asyncio
import random
import time

import aiohttp
from pydantic import BaseModel


class Tools:
    class Valves(BaseModel):
        comfyui_url: str = "http://host.docker.internal:8189"
        output_base_url: str = "https://stevens-mac-studio.tail7c9d1c.ts.net/comfyui"
        default_denoise: float = 0.45

    def __init__(self):
        self.valves = self.Valves()

    # ------------------------------------------------------------------ helpers

    async def _emit(self, emitter, msg: str):
        if emitter:
            await emitter({"type": "status", "data": {"description": msg, "done": False}})

    async def _emit_done(self, emitter, msg: str):
        if emitter:
            await emitter({"type": "status", "data": {"description": msg, "done": True}})

    async def _submit_workflow(self, workflow: dict) -> str:
        """POST workflow to /prompt, return prompt_id."""
        payload = {"prompt": workflow, "client_id": f"owui-{random.randint(0, 99999)}"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.valves.comfyui_url}/prompt",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"ComfyUI /prompt HTTP {resp.status}: {body[:300]}")
                try:
                    import json as _json
                    data = _json.loads(body)
                except Exception:
                    raise RuntimeError(f"ComfyUI /prompt non-JSON response: {body[:300]}")
                if not data or "prompt_id" not in data:
                    raise RuntimeError(f"ComfyUI /prompt missing prompt_id. Response: {body[:300]}")
                return data["prompt_id"]

    async def _wait_for_output(self, prompt_id: str, timeout: int = 360) -> str:
        """Poll /history/{prompt_id} until the job completes, return output filename."""
        deadline = time.monotonic() + timeout
        async with aiohttp.ClientSession() as session:
            while time.monotonic() < deadline:
                await asyncio.sleep(2)
                try:
                    async with session.get(
                        f"{self.valves.comfyui_url}/history/{prompt_id}",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        import json as _json
                        data = _json.loads(await resp.text())
                        if not data or prompt_id not in data:
                            continue
                        for node_output in data[prompt_id].get("outputs", {}).values():
                            images = node_output.get("images", [])
                            if images:
                                return images[0]["filename"]
                except Exception:
                    pass
        raise TimeoutError(f"ComfyUI did not complete within {timeout}s")

    def _image_url(self, filename: str) -> str:
        return f"{self.valves.output_base_url}/view?filename={filename}&type=output"

    async def _upload_image(self, image_bytes: bytes, filename: str) -> str:
        """Upload image bytes to ComfyUI /upload/image, return uploaded filename."""
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("image", image_bytes, filename=filename, content_type="image/png")
            async with session.post(
                f"{self.valves.comfyui_url}/upload/image",
                data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                return data["name"]

    async def _add_watermark(self, filename: str) -> str:
        """
        Download a generated image from ComfyUI output, stamp 'VIRTUALLY STAGED' in the
        bottom-left corner with a semi-transparent backing, re-upload to ComfyUI input,
        and return the full HTTPS URL of the watermarked image.
        Falls back silently to the original output URL if PIL is unavailable.
        """
        import io as _io
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            # PIL not available in this environment — return original URL unwatermarked
            return self._image_url(filename)

        try:
            # 1. Download from ComfyUI output folder
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.valves.comfyui_url}/view?filename={filename}&type=output",
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if not resp.ok:
                        return self._image_url(filename)
                    img_bytes = await resp.read()

            # 2. Apply watermark overlay
            img = Image.open(_io.BytesIO(img_bytes)).convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            text = "VIRTUALLY STAGED"
            margin = 18
            font = None
            for font_path in [
                # Debian/Ubuntu (OWUI Docker base image)
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                # macOS (local dev)
                "/System/Library/Fonts/Helvetica.ttc",
            ]:
                try:
                    font = ImageFont.truetype(font_path, size=28)
                    break
                except Exception:
                    pass
            if font is None:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x, y = margin, img.height - th - margin * 2
            # Semi-transparent dark backing rectangle for legibility over any floor color
            draw.rectangle([x - 8, y - 6, x + tw + 8, y + th + 6], fill=(0, 0, 0, 160))
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
            img = Image.alpha_composite(img, overlay).convert("RGB")

            # 3. Re-upload watermarked version to ComfyUI input folder
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            wm_filename = f"wm_{filename}"
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("image", buf.read(), filename=wm_filename, content_type="image/png")
                form.add_field("type", "input")
                form.add_field("overwrite", "true")
                async with session.post(
                    f"{self.valves.comfyui_url}/upload/image",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if not resp.ok:
                        return self._image_url(filename)
                    data = await resp.json(content_type=None)
                    uploaded_name = data.get("name", wm_filename)

            return f"{self.valves.output_base_url}/view?filename={uploaded_name}&type=input"

        except Exception:
            # Any failure → return original URL so the user still gets their image
            return self._image_url(filename)

    def _extract_images_from_messages(self, messages: list) -> list:
        """Return list of (bytes, ext) tuples from base64 data URLs in the most recent user message."""
        import base64 as _b64
        for msg in reversed(messages or []):
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not isinstance(content, list):
                continue
            found = []
            for part in content:
                if part.get("type") == "image_url":
                    data_url = part.get("image_url", {}).get("url", "")
                    if data_url.startswith("data:image"):
                        try:
                            header, b64data = data_url.split(",", 1)
                            ext = header.split(";")[0].split("/")[-1]
                            found.append((_b64.b64decode(b64data), ext))
                        except Exception:
                            pass
            if found:
                return found
        return []

    def _sdxl_base(self, with_lora: bool = False):
        """
        Return the shared SDXL checkpoint/VAE/LoRA nodes as a workflow dict fragment.
        Node IDs used: "1" (checkpoint), "4" (VAE), "2" (LoRA — only when with_lora=True).
        MODEL output: ["2", 0] if LoRA, else ["1", 0]
        CLIP output:  ["2", 1] if LoRA, else ["1", 1]
        VAE output:   ["4", 0] always
        """
        nodes = {
            "1": {
                "inputs": {"ckpt_name": SDXL_CHECKPOINT},
                "class_type": "CheckpointLoaderSimple",
            },
            "4": {
                "inputs": {"vae_name": SDXL_VAE},
                "class_type": "VAELoader",
            },
        }
        if with_lora:
            nodes["2"] = {
                "inputs": {
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "lora_name": INTERIOR_LORA,
                    "strength_model": LORA_STRENGTH,
                    "strength_clip": LORA_STRENGTH,
                },
                "class_type": "LoraLoader",
            }
        return nodes

    def _sdxl_clip(self, text_pos: str, text_neg: str, clip_source: list, node_pos="3", node_neg="99"):
        """Return CLIPTextEncodeSDXL node pair for positive and negative conditioning."""
        return {
            node_pos: {
                "inputs": {
                    "clip": clip_source,
                    "width": 1024, "height": 1024,
                    "crop_w": 0, "crop_h": 0,
                    "target_width": 1024, "target_height": 1024,
                    "text_g": text_pos,
                    "text_l": text_pos,
                },
                "class_type": "CLIPTextEncodeSDXL",
            },
            node_neg: {
                "inputs": {
                    "clip": clip_source,
                    "width": 1024, "height": 1024,
                    "crop_w": 0, "crop_h": 0,
                    "target_width": 1024, "target_height": 1024,
                    "text_g": text_neg,
                    "text_l": text_neg,
                },
                "class_type": "CLIPTextEncodeSDXL",
            },
        }

    # --------------------------------------------------------- text-to-image

    async def generate_image(
        self,
        prompt: str,
        model: str = "flux",
        __event_emitter__=None,
    ) -> str:
        """
        Generate a new image from a text description.

        :param prompt: Full description of the image to generate. Be specific about materials, lighting, style, and camera perspective for best real estate results.
        :param model: Which checkpoint to render with. ALWAYS pass this argument explicitly — do not rely on the default. Pass model="sdxl" for any real-estate, listing, MLS, print, interior, or staging work (Juggernaut XL, ~30s, photorealistic detail). Pass model="flux" only for social-media graphics or rapid concept iteration (FLUX.1-schnell, ~24s).
        """
        model = model.lower().strip()
        label = "FLUX.1-schnell" if "flux" in model else "Juggernaut XL"
        await self._emit(__event_emitter__, f"Starting {label} generation...")

        seed = random.randint(0, 2**32 - 1)

        if "flux" in model:
            workflow = {
                "1": {
                    "inputs": {"unet_name": "flux-schnell/flux1-schnell.safetensors", "weight_dtype": "default"},
                    "class_type": "UNETLoader",
                },
                "4": {
                    "inputs": {"vae_name": "flux_vae.safetensors"},
                    "class_type": "VAELoader",
                },
                "5": {
                    "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
                    "class_type": "EmptyLatentImage",
                },
                "8": {
                    "inputs": {
                        "seed": seed,
                        "steps": 4,
                        "cfg": 1,
                        "sampler_name": "euler",
                        "scheduler": "simple",
                        "denoise": 1,
                        "model": ["1", 0],
                        "positive": ["22", 0],
                        "negative": ["21", 0],
                        "latent_image": ["5", 0],
                    },
                    "class_type": "KSampler",
                },
                "9": {
                    "inputs": {"samples": ["8", 0], "vae": ["4", 0]},
                    "class_type": "VAEDecode",
                },
                "10": {
                    "inputs": {"filename_prefix": "FLUX_owui_", "images": ["9", 0]},
                    "class_type": "SaveImage",
                },
                "21": {
                    "inputs": {
                        "clip_l": "blurry, low quality, distorted",
                        "t5xxl": "blurry, low quality, distorted, dark, heavy shadows, poor composition, amateur photography",
                        "guidance": 3.5,
                        "clip": ["26", 0],
                    },
                    "class_type": "CLIPTextEncodeFlux",
                },
                "22": {
                    "inputs": {
                        "clip_l": prompt[:300],
                        "t5xxl": prompt,
                        "guidance": 3.5,
                        "clip": ["26", 0],
                    },
                    "class_type": "CLIPTextEncodeFlux",
                },
                "26": {
                    "inputs": {
                        "clip_name1": "clip_l.safetensors",
                        "clip_name2": "t5xxl_fp16.safetensors",
                        "type": "flux",
                        "device": "default",
                    },
                    "class_type": "DualCLIPLoader",
                },
            }
            eta = "~24 seconds"
        else:
            # Juggernaut XL — general purpose txt2img (no interior LoRA for versatility)
            clip_src = ["1", 1]
            workflow = {
                **self._sdxl_base(with_lora=False),
                **self._sdxl_clip(prompt, SDXL_NEGATIVE, clip_src, node_pos="3", node_neg="99"),
                "5": {
                    "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
                    "class_type": "EmptyLatentImage",
                },
                "6": {
                    "inputs": {
                        "seed": seed,
                        "steps": SDXL_STEPS,
                        "cfg": SDXL_CFG,
                        "sampler_name": SDXL_SAMPLER,
                        "scheduler": SDXL_SCHEDULER,
                        "denoise": 1.0,
                        "model": ["1", 0],
                        "positive": ["3", 0],
                        "negative": ["99", 0],
                        "latent_image": ["5", 0],
                    },
                    "class_type": "KSampler",
                },
                "7": {
                    "inputs": {"samples": ["6", 0], "vae": ["4", 0]},
                    "class_type": "VAEDecode",
                },
                "8": {
                    "inputs": {"filename_prefix": "SDXL_owui_", "images": ["7", 0]},
                    "class_type": "SaveImage",
                },
            }
            eta = "~30 seconds"

        try:
            prompt_id = await self._submit_workflow(workflow)
            await self._emit(__event_emitter__, f"Generating... ({eta})")
            filename = await self._wait_for_output(prompt_id)
            url = self._image_url(filename)
            await self._emit_done(__event_emitter__, "Done")
            return f"Image generated!\n\n![Generated Image]({url})\n\n[Open full size]({url})"
        except Exception as e:
            await self._emit_done(__event_emitter__, f"Failed: {e}")
            return f"Image generation failed: {e}"

    # ------------------------------------------------------------ img2img

    async def edit_image(
        self,
        prompt: str,
        image_url: str = "",
        denoise: float = 0.65,
        __files__: list = [],
        __messages__: list = [],
        __event_emitter__=None,
    ) -> str:
        """
        Digitally stage or restyle a room photo using SDXL img2img with interior LoRA conditioning. Provide a source image either as an attached file or a URL.

        :param prompt: Describe the desired result, e.g. "modern furnished living room with warm ambient lighting, luxury sofa, coffee table, art on walls, professional real estate photography".
        :param image_url: Only provide this if the user explicitly pastes a URL. Leave empty (do not guess or invent a URL) when the user attaches an image to the message — the tool retrieves attached images automatically.
        :param denoise: Controls how much the image changes. 0.5=subtle edits, 0.65=moderate staging (recommended), 0.75=aggressive transformation. Default 0.65.
        """
        await self._emit(__event_emitter__, "Acquiring source image...")

        image_bytes = None
        src_filename = "input_image.png"

        # 1. Try base64 attachments in __messages__ (OWUI primary path)
        found = self._extract_images_from_messages(__messages__)
        if found:
            image_bytes, ext = found[0]
            src_filename = f"input_image.{ext}"

        async with aiohttp.ClientSession() as session:
            # 2. Try attached files (legacy path)
            if not image_bytes:
                for f in (__files__ or []):
                    meta = f.get("meta", {})
                    content_type = meta.get("content_type", "") or f.get("type", "")
                    if "image" not in content_type:
                        continue
                    src_filename = meta.get("name", f.get("filename", src_filename))
                    file_url = f.get("url", "")
                    if not file_url:
                        continue
                    if not file_url.startswith("http"):
                        file_url = f"http://localhost:3000{file_url}"
                    try:
                        async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.ok:
                                image_bytes = await resp.read()
                                break
                    except Exception:
                        pass

            # 3. Fall back to image_url parameter
            if not image_bytes and image_url:
                fetch_url = image_url.replace(
                    "https://stevens-mac-studio.tail7c9d1c.ts.net/comfyui",
                    "http://host.docker.internal:8189",
                )
                try:
                    async with session.get(fetch_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.ok:
                            image_bytes = await resp.read()
                            path_part = fetch_url.split("?")[0].rstrip("/").split("/")[-1]
                            if path_part:
                                src_filename = path_part
                        else:
                            return f"Could not download image from URL (HTTP {resp.status}): {image_url}"
                except Exception as e:
                    return f"Could not download image from URL: {e}"

        if not image_bytes:
            return (
                "No source image found. Please either:\n"
                "1. Attach an image file to your message, or\n"
                "2. Provide a direct image URL in the image_url parameter."
            )

        await self._emit(__event_emitter__, "Uploading image to ComfyUI...")
        uploaded_filename = await self._upload_image(image_bytes, src_filename)

        seed = random.randint(0, 2**32 - 1)
        # Interior LoRA active — append trigger word for maximum style activation
        lora_prompt = f"mrares, {prompt}"
        clip_src = ["2", 1]  # CLIP from LoraLoader
        model_src = ["2", 0]  # MODEL from LoraLoader

        workflow = {
            **self._sdxl_base(with_lora=True),
            **self._sdxl_clip(lora_prompt, SDXL_NEGATIVE, clip_src, node_pos="3", node_neg="99"),
            "10": {
                "inputs": {"image": uploaded_filename, "upload": "image"},
                "class_type": "LoadImage",
            },
            "11": {
                "inputs": {
                    "image": ["10", 0],
                    "width": 1024, "height": 1024,
                    "upscale_method": "lanczos",
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },
            "12": {
                "inputs": {"pixels": ["11", 0], "vae": ["4", 0]},
                "class_type": "VAEEncode",
            },
            "6": {
                "inputs": {
                    "seed": seed,
                    "steps": SDXL_STEPS,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "denoise": denoise,
                    "model": model_src,
                    "positive": ["3", 0],
                    "negative": ["99", 0],
                    "latent_image": ["12", 0],
                },
                "class_type": "KSampler",
            },
            "7": {
                "inputs": {"samples": ["6", 0], "vae": ["4", 0]},
                "class_type": "VAEDecode",
            },
            "8": {
                "inputs": {"filename_prefix": "SDXL_img2img_", "images": ["7", 0]},
                "class_type": "SaveImage",
            },
        }

        try:
            await self._emit(__event_emitter__, f"Staging room (denoise={denoise}, ~35 seconds)...")
            prompt_id = await self._submit_workflow(workflow)
            filename = await self._wait_for_output(prompt_id, timeout=240)
            url = self._image_url(filename)
            await self._emit_done(__event_emitter__, "Staged image ready")
            return (
                f"Room staged successfully!\n\n"
                f"![Staged Image]({url})\n\n"
                f"[Open full size]({url})\n\n"
                f"*Denoise strength used: {denoise} — try 0.75 for more dramatic staging or 0.5 to preserve more of the original room.*"
            )
        except Exception as e:
            await self._emit_done(__event_emitter__, f"Failed: {e}")
            return f"Image editing failed: {e}"

    # ------------------------------------------------------- general-purpose transform

    async def transform_image(
        self,
        prompt: str,
        appearance_strength: float = 0.8,
        image_url: str = "",
        __files__: list = [],
        __messages__: list = [],
        __event_emitter__=None,
    ) -> str:
        """
        Generate a new creative image based on a reference face photo and a text description.
        Uses InstantID (IdentityNet + face landmark ControlNet) to lock the subject's exact
        facial bone structure, eye shape, and micro-features with zero creative liberty —
        then applies a 2-pass FaceDetailer to add photographic skin texture without altering
        the biometric identity.

        The scene, composition, attire, and environment come entirely from the prompt.
        Do NOT describe face characteristics in the prompt (eye color, skin tone, smile) —
        InstantID handles those automatically from the reference photo.

        Use this for: professional headshots, placing a person in a new environment or costume,
        generating full body shots from a face crop. NOT for real estate staging.

        :param prompt: Describe the scene, attire, and environment ONLY — NOT the face.
          Example: "professional corporate headshot, tailored navy suit, studio lighting,
          neutral grey gradient background, 85mm lens, sharp focus, photorealistic".
          Another: "a warrior in medieval plate armor on a misty battlefield, dramatic lighting".
        :param appearance_strength: InstantID identity lock strength.
          0.6=moderate (some creative reinterpretation), 0.8=strong (recommended, near-exact
          biometric fidelity), 1.0=maximum lock (may reduce naturalness).
        :param image_url: Only set this if the user explicitly pastes a URL. Leave empty when
          the user attaches an image — attached images are retrieved automatically.
        """
        await self._emit(__event_emitter__, "Acquiring source image...")

        image_bytes = None
        src_filename = "input_image.png"

        # 1. Try base64 attachments in __messages__ (OWUI primary path)
        found = self._extract_images_from_messages(__messages__)
        if found:
            image_bytes, ext = found[0]
            src_filename = f"input_image.{ext}"

        async with aiohttp.ClientSession() as session:
            # 2. Try attached files (legacy path)
            if not image_bytes:
                for f in (__files__ or []):
                    meta = f.get("meta", {})
                    content_type = meta.get("content_type", "") or f.get("type", "")
                    if "image" not in content_type:
                        continue
                    src_filename = meta.get("name", f.get("filename", src_filename))
                    file_url = f.get("url", "")
                    if not file_url:
                        continue
                    if not file_url.startswith("http"):
                        file_url = f"http://localhost:3000{file_url}"
                    try:
                        async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.ok:
                                image_bytes = await resp.read()
                                break
                    except Exception:
                        pass

            # 3. Fall back to image_url parameter
            if not image_bytes and image_url:
                fetch_url = image_url.replace(
                    "https://stevens-mac-studio.tail7c9d1c.ts.net/comfyui",
                    "http://host.docker.internal:8189",
                )
                try:
                    async with session.get(fetch_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.ok:
                            image_bytes = await resp.read()
                            path_part = fetch_url.split("?")[0].rstrip("/").split("/")[-1]
                            if path_part:
                                src_filename = path_part
                        else:
                            return f"Could not download image from URL (HTTP {resp.status}): {image_url}"
                except Exception as e:
                    return f"Could not download image from URL: {e}"

        if not image_bytes:
            return (
                "No source image found. Please either:\n"
                "1. Attach an image file to your message, or\n"
                "2. Provide a direct image URL in the image_url parameter."
            )

        await self._emit(__event_emitter__, "Uploading image to ComfyUI...")
        uploaded_filename = await self._upload_image(image_bytes, src_filename)

        seed = random.randint(0, 2**32 - 1)

        workflow = {
            # --- SDXL checkpoint (no interior LoRA — InstantID handles appearance) ---
            **self._sdxl_base(with_lora=False),
            **self._sdxl_clip(prompt, TRANSFORM_NEGATIVE, ["1", 1], node_pos="3", node_neg="99"),

            # --- Reference face image loading + scale ---
            "10": {
                "inputs": {"image": uploaded_filename, "upload": "image"},
                "class_type": "LoadImage",
            },
            "11": {
                "inputs": {
                    "image": ["10", 0],
                    "width": 1024, "height": 1024,
                    "upscale_method": "lanczos",
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },

            # --- InstantID: biometric identity lock ---
            # InstantIDModelLoader loads the IP-Adapter weights from models/instantid/
            "35": {
                "inputs": {"instantid_file": INSTANTID_MODEL},
                "class_type": "InstantIDModelLoader",
            },
            # InstantIDFaceAnalysis loads InsightFace antelopev2 for landmark extraction.
            # Provider "CPU" is safe on all platforms; antelopev2 auto-downloads to models/insightface/ on first run.
            "36": {
                "inputs": {"provider": "CPU"},
                "class_type": "InstantIDFaceAnalysis",
            },
            # ControlNetLoader for the InstantID face keypoint ControlNet (SDXL-specific)
            "37": {
                "inputs": {"control_net_name": INSTANTID_CONTROLNET},
                "class_type": "ControlNetLoader",
            },
            # ApplyInstantID: combines face embedding injection (IP-Adapter) + landmark
            # ControlNet conditioning — locks bone structure, eye shape, micro-features.
            # Returns [0]=model, [1]=positive_cond, [2]=negative_cond
            "38": {
                "inputs": {
                    "instantid": ["35", 0],
                    "insightface": ["36", 0],
                    "control_net": ["37", 0],
                    "image": ["11", 0],
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["99", 0],
                    "weight": appearance_strength,
                    "start_at": 0.0,
                    "end_at": 1.0,
                },
                "class_type": "ApplyInstantID",
            },

            # --- Base generation: scene + identity from EmptyLatentImage (not img2img) ---
            "5": {
                "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
                "class_type": "EmptyLatentImage",
            },
            "6": {
                "inputs": {
                    "seed": seed,
                    "steps": SDXL_STEPS,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "denoise": 1.0,
                    "model": ["38", 0],
                    "positive": ["38", 1],
                    "negative": ["38", 2],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "7": {
                "inputs": {"samples": ["6", 0], "vae": ["4", 0]},
                "class_type": "VAEDecode",
            },

            # --- YOLO face bbox detector (shared by both FaceDetailer passes) ---
            "39": {
                "inputs": {"model_name": INSTANTID_BBOX_DETECTOR},
                "class_type": "UltralyticsDetectorProvider",
            },

            # --- FaceDetailer Pass 1: wide crop for lighting harmonization ---
            # bbox_crop_factor=2.8: crops wide to include jaw/neck/lighting context.
            # denoise=0.38: low enough that InstantID geometry is preserved; high enough
            # to fix AI-sheen and blend lighting from generated environment into the face.
            "40": {
                "inputs": {
                    "image": ["7", 0],
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "vae": ["4", 0],
                    "guide_size": 512,
                    "guide_size_for": True,
                    "max_size": 1024,
                    "seed": seed,
                    "steps": SDXL_STEPS,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "positive": ["38", 1],
                    "negative": ["38", 2],
                    "denoise": 0.38,
                    "feather": 5,
                    "noise_mask": True,
                    "force_inpaint": True,
                    "bbox_threshold": 0.5,
                    "bbox_dilation": 10,
                    "bbox_crop_factor": 2.8,
                    "sam_detection_hint": "center-1",
                    "sam_dilation": 0,
                    "sam_threshold": 0.93,
                    "sam_bbox_expansion": 0,
                    "sam_mask_hint_threshold": 0.7,
                    "sam_mask_hint_use_negative": "False",
                    "drop_size": 10,
                    "bbox_detector": ["39", 0],
                    "wildcard": "",
                    "cycle": 1,
                },
                "class_type": "FaceDetailer",
            },

            # --- FaceDetailer Pass 2: tight crop for micro-detail synthesis ---
            # bbox_crop_factor=1.5: zooms into core features (eyes, pores, eyelashes).
            # denoise=0.32: absolute minimum — synthesizes high-freq texture only,
            # not enough freedom to alter biometric identity or geometry.
            "41": {
                "inputs": {
                    "image": ["40", 0],
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "vae": ["4", 0],
                    "guide_size": 512,
                    "guide_size_for": True,
                    "max_size": 1024,
                    "seed": seed,
                    "steps": SDXL_STEPS,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "positive": ["38", 1],
                    "negative": ["38", 2],
                    "denoise": 0.32,
                    "feather": 5,
                    "noise_mask": True,
                    "force_inpaint": True,
                    "bbox_threshold": 0.5,
                    "bbox_dilation": 5,
                    "bbox_crop_factor": 1.5,
                    "sam_detection_hint": "center-1",
                    "sam_dilation": 0,
                    "sam_threshold": 0.93,
                    "sam_bbox_expansion": 0,
                    "sam_mask_hint_threshold": 0.7,
                    "sam_mask_hint_use_negative": "False",
                    "drop_size": 10,
                    "bbox_detector": ["39", 0],
                    "wildcard": "",
                    "cycle": 1,
                },
                "class_type": "FaceDetailer",
            },

            "8": {
                "inputs": {"filename_prefix": "SDXL_transform_", "images": ["41", 0]},
                "class_type": "SaveImage",
            },
        }

        try:
            await self._emit(
                __event_emitter__,
                f"Generating with InstantID face lock (appearance_strength={appearance_strength}) + 2-pass FaceDetailer (~60s)...",
            )
            prompt_id = await self._submit_workflow(workflow)
            filename = await self._wait_for_output(prompt_id, timeout=360)
            url = self._image_url(filename)
            await self._emit_done(__event_emitter__, "Transformation complete")
            return (
                f"Image transformed with InstantID!\n\n"
                f"![Transformed Image]({url})\n\n"
                f"[Open full size]({url})\n\n"
                f"*appearance_strength: {appearance_strength} (0.6=moderate, 0.8=recommended, 1.0=maximum). "
                f"Scene and environment come from your prompt. "
                f"On first run, InsightFace antelopev2 model auto-downloads (~170MB) — expect a longer wait.*"
            )
        except Exception as e:
            await self._emit_done(__event_emitter__, f"Failed: {e}")
            return f"Image transformation failed: {e}"

    # ------------------------------------------------------- dual ControlNet staging

    async def stage_room(
        self,
        prompt: str,
        denoise: float = 0.55,
        controlnet_strength: float = 0.55,
        __messages__: list = [],
        __event_emitter__=None,
    ) -> str:
        """
        Stage a vacant room photo with geometry-aware furniture placement using dual ControlNet conditioning (depth + MLSD line detection).
        Depth ControlNet preserves spatial layout and furniture scale; MLSD ControlNet detects straight architectural lines (walls, door frames, windows) to prevent furniture from clipping through room boundaries.
        Attach the room photo to your message — do not provide an image_url.

        :param prompt: Describe ONLY furniture and décor — never describe wall color, ceiling type,
            floor material, window treatments, or lighting fixtures. ControlNet preserves geometry;
            IP-Adapter anchors material appearance. Text prompt should add furniture only.
            Good: "leather sectional, jute rug, floor lamp, potted plant, side table"
            Bad:  "warm white walls, linen curtains, recessed lighting, crown molding" — causes remodel.
            Warning: avoid words that the model interprets as focal-wall treatments even in a furniture
            context — "shelving/bookcase" → replaces fireplace wall; "canvas/wall art" → replaces
            fireplace wall; "herringbone/chevron" → may be applied as wall tile not rug pattern.
            Describe only freestanding furniture and soft furnishings.
        :param denoise: How much to change the room. 0.5=very light staging, 0.55=full staging (recommended), 0.65=more creative (may alter existing surfaces), 0.75=aggressive transformation. Default 0.55.
        :param controlnet_strength: Depth ControlNet strength — how strictly the original room geometry is preserved.
          0.4 = relaxed (more creative furniture placement),
          0.55 = balanced — recommended,
          0.7 = strict (very faithful to original room structure).
          Default 0.55.
        """
        await self._emit(__event_emitter__, "Acquiring source image...")

        found = self._extract_images_from_messages(__messages__)
        if not found:
            return "No source image found. Please attach a room photo to your message."

        image_bytes, ext = found[0]
        await self._emit(__event_emitter__, "Uploading image to ComfyUI...")
        uploaded_filename = await self._upload_image(image_bytes, f"input_image.{ext}")

        seed = random.randint(0, 2**32 - 1)
        # Interior LoRA active — append trigger word
        lora_prompt = f"mrares, {prompt}"
        clip_src = ["2", 1]
        model_src = ["2", 0]

        workflow = {
            # --- SDXL model + interior LoRA ---
            **self._sdxl_base(with_lora=True),
            **self._sdxl_clip(lora_prompt, SDXL_NEGATIVE, clip_src, node_pos="3", node_neg="99"),

            # --- Image loading + resize to 1024x1024 ---
            "10": {
                "inputs": {"image": uploaded_filename, "upload": "image"},
                "class_type": "LoadImage",
            },
            "11": {
                "inputs": {
                    "image": ["10", 0],
                    "width": 1024, "height": 1024,
                    "upscale_method": "lanczos",
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },

            # --- ControlNet preprocessors ---
            # Depth: extracts distance/surface for furniture scale and spatial layout
            "12": {
                "inputs": {
                    "image": ["11", 0],
                    "ckpt_name": "depth_anything_v2_vitl.pth",
                    "resolution": 1024,
                },
                "class_type": "DepthAnythingV2Preprocessor",
            },
            # MLSD: detects only straight architectural lines (walls, door frames, baseboards)
            # via Hough transforms — ignores carpet fiber, wood grain, and texture noise that
            # Canny would pick up and hallucinate geometry from. Cleaner conditioning map.
            "13": {
                "inputs": {
                    "image": ["11", 0],
                    "score_threshold": 0.1,
                    "dist_threshold": 0.1,
                    "resolution": 1024,
                },
                "class_type": "M-LSDPreprocessor",
            },

            # --- ControlNet loaders ---
            "14": {
                "inputs": {"control_net_name": CONTROLNET_DEPTH},
                "class_type": "ControlNetLoader",
            },
            "15": {
                "inputs": {"control_net_name": CONTROLNET_CANNY},
                "class_type": "ControlNetLoader",
            },

            # --- Dual ControlNet conditioning (chained) ---
            # Depth fires first and stronger, establishing spatial framework.
            # end_percent=0.55: active for steps 1-27 of 50 (just over half). Steps 28-50
            # run free for natural texture/lighting refinement. Previously 0.4 (only 20 steps)
            # — too few, model hallucinated architecture in steps 21-50.
            "16": {
                "inputs": {
                    "positive": ["3", 0],
                    "negative": ["99", 0],
                    "control_net": ["14", 0],
                    "image": ["12", 0],
                    "strength": controlnet_strength,
                    "start_percent": 0.0,
                    "end_percent": 0.55,
                },
                "class_type": "ControlNetApplyAdvanced",
            },
            # MLSD fires with the straight-line map, preventing wall/window/ceiling remodeling.
            # strength=0.35 (was 0.25 — too weak to enforce architectural lines).
            # end_percent=0.55 (was 0.3 — only 15 steps; left 35 steps unguarded).
            "17": {
                "inputs": {
                    "positive": ["16", 0],   # chains from depth output
                    "negative": ["16", 1],
                    "control_net": ["15", 0],
                    "image": ["13", 0],
                    "strength": 0.35,
                    "start_percent": 0.0,
                    "end_percent": 0.55,
                },
                "class_type": "ControlNetApplyAdvanced",
            },

            # --- img2img latent (VAEEncode safe on SDXL/MPS — no NaN risk) ---
            "18": {
                "inputs": {"pixels": ["11", 0], "vae": ["4", 0]},
                "class_type": "VAEEncode",
            },

            # --- IP-Adapter appearance anchor ---
            # Loads the original room image as appearance conditioning at weight=0.45.
            # Anchors color palette, stone/wood material textures, floor material, and
            # ceiling color so the model preserves dark hardwood, dark beams, brick fireplace
            # and other existing surfaces even when the text prompt uses vocabulary the model
            # associates with those zones (shelving, canvas, herringbone, tufted panels, etc.).
            # ControlNet handles geometry; IPAdapter handles appearance identity.
            # Weight=0.45, weight_type="style transfer": front-loads appearance conditioning into
            # the early diffusion steps (1–20 of 50) where the model decides surface material
            # identity (floor grain, brick texture, ceiling color). Later steps add furniture
            # detail with lower IP-Adapter influence. More effective than "linear" at same weight.
            "50": {
                "inputs": {"ipadapter_file": IPADAPTER_SDXL},
                "class_type": "IPAdapterModelLoader",
            },
            "51": {
                "inputs": {"clip_name": CLIP_VISION_VIT_H},
                "class_type": "CLIPVisionLoader",
            },
            "52": {
                "inputs": {
                    "model": ["2", 0],      # LoraLoader output — apply IPAdapter on top of LoRA
                    "ipadapter": ["50", 0],
                    "image": ["11", 0],     # original scaled room image
                    "clip_vision": ["51", 0],
                    "weight": 0.45,
                    "weight_type": "style transfer",
                    "combine_embeds": "concat",
                    "start_at": 0.0,
                    "end_at": 1.0,          # anchor throughout all 50 steps
                    "embeds_scaling": "V only",
                },
                "class_type": "IPAdapterAdvanced",
            },

            # --- KSampler ---
            # steps=50: higher than global default (30) — stage_room is a production output
            # where quality matters more than speed. 50 steps improves furniture texture,
            # lighting accuracy, and LoRA contribution without extreme time cost.
            # model from IPAdapterAdvanced ["52",0] — after LoRA + appearance conditioning.
            "6": {
                "inputs": {
                    "seed": seed,
                    "steps": 50,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "denoise": denoise,
                    "model": ["52", 0],     # IPAdapterAdvanced output (LoRA + appearance anchor)
                    "positive": ["17", 0],  # doubly-conditioned (depth + MLSD)
                    "negative": ["17", 1],
                    "latent_image": ["18", 0],
                },
                "class_type": "KSampler",
            },
            "7": {
                "inputs": {"samples": ["6", 0], "vae": ["4", 0]},
                "class_type": "VAEDecode",
            },
            "8": {
                "inputs": {"filename_prefix": "SDXL_staged_", "images": ["7", 0]},
                "class_type": "SaveImage",
            },
        }

        try:
            await self._emit(
                __event_emitter__,
                f"Staging with dual ControlNet + IPAdapter appearance anchor (denoise={denoise}, ~110s)...",
                # denoise default lowered 0.65→0.55; IPAdapter weight raised 0.25→0.45 (v5.6.0)
            )
            prompt_id = await self._submit_workflow(workflow)
            filename = await self._wait_for_output(prompt_id, timeout=300)
            await self._emit(__event_emitter__, "Adding MLS compliance watermark...")
            url = await self._add_watermark(filename)
            await self._emit_done(__event_emitter__, "Staged image ready")
            return (
                f"Room staged with dual ControlNet geometry preservation!\n\n"
                f"![Staged Room]({url})\n\n"
                f"[Open full size]({url})\n\n"
                f"*Denoise: {denoise} (0.5=very light, 0.55=recommended, 0.65=more creative). "
                f"Depth strength: {controlnet_strength} (0.4=relaxed, 0.7=strict). "
                f"Re-run with adjusted values to tune the result.*"
            )
        except Exception as e:
            await self._emit_done(__event_emitter__, f"Failed: {e}")
            return f"Room staging failed: {e}"

    # ----------------------------------------- inpainting (SAM + GroundingDINO + SDXL)

    async def inpaint_room(
        self,
        prompt: str,
        mask_subject: str = "",
        denoise: float = 0.85,
        threshold: float = 0.25,
        mask_expand: int = 20,
        mask_rect: str = "",
        canvas_size: str = "landscape",
        __messages__: list = [],
        __event_emitter__=None,
    ) -> str:
        """
        Replace a specific area in a room photo using AI inpainting. SDXL Juggernaut XL generates
        new content only within the masked region; everything outside is pixel-perfect original.
        Attach the room photo to your message.

        Two masking modes — use one or the other:

        **mask_rect (recommended for furniture placement in empty rooms):** Provide
        "x1,y1,x2,y2" as 0.0–1.0 image fractions. Creates an exact rectangular mask at those
        coordinates, bypassing SAM entirely. The fireplace, walls, ceiling, and anything outside
        the rectangle are guaranteed to be unchanged. Use this when you know where furniture goes.
        Example: "0.25,0.55,0.85,0.95" targets the center-foreground floor zone.
        For the Lyons Valley room: fireplace is on the left (~x=0.35), use x1≥0.35 to stay clear.

        **mask_subject (automatic, uses SAM + GroundingDINO):** Describe the region to replace
        as a short noun — "floor", "carpet", "sofa". SAM auto-detects the region. Less precise
        than mask_rect for large open rooms; may bleed into nearby features.

        **Prompt tips for furniture placement:**
        - Include orientation: "facing the camera" or "back toward the fireplace wall"
        - Include "area rug under sofa/chairs" — anchors furniture perspective and hides floor seams
        - Example: "neutral linen sofa facing the camera on a jute area rug, warm natural light,
          photorealistic interior photography"

        :param prompt: What to generate inside the mask. Describe furniture and materials only.
        :param mask_subject: SAM detection target (single noun). Only used when mask_rect is empty.
        :param denoise: Inpaint strength 0.5–1.0. Default 0.85. Use 0.85–0.95 for furniture
          placement; 0.65–0.75 for texture swaps.
        :param threshold: GroundingDINO confidence 0.1–0.5. Only used when mask_rect is empty.
          Default 0.25. Raise to 0.4 if too much unrelated area is masked.
        :param mask_expand: Pixel radius to grow the mask. Default 20. Use 20–40 for standard
          furniture; 80+ for tall items.
        :param mask_rect: Optional "x1,y1,x2,y2" as 0.0–1.0 fractions. When provided, bypasses
          SAM/GroundingDINO and uses a precise rectangle. Guarantees fireplace/walls are untouched.
        :param canvas_size: SDXL canvas resolution. "landscape" (default) = 1152×768 for 3:2 MLS
          photos. "portrait" = 768×1024. "square" = 1024×1024.
        """
        await self._emit(__event_emitter__, "Acquiring source image...")

        found = self._extract_images_from_messages(__messages__)
        if not found:
            return "No source image found. Please attach a room photo to your message."

        image_bytes, ext = found[0]
        await self._emit(__event_emitter__, "Uploading image to ComfyUI...")
        uploaded_filename = await self._upload_image(image_bytes, f"input_image.{ext}")

        seed = random.randint(0, 2**32 - 1)
        # Interior LoRA active — append trigger word
        lora_prompt = f"mrares, {prompt}"
        clip_src = ["2", 1]
        model_src = ["2", 0]

        # --- Canvas resolution: SDXL native buckets that match real MLS photo aspect ratios ---
        # "landscape" = 1152×768 matches 3:2 photographer files (6048×4024, 2048×1363)
        _canvas_map = {"landscape": (1152, 768), "portrait": (768, 1024), "square": (1024, 1024)}
        canvas_w, canvas_h = _canvas_map.get(canvas_size, (1152, 768))

        # --- Rectangular mask (bypasses SAM/GroundingDINO) ---
        # When mask_rect is provided, create a PIL image with a white rectangle on black
        # background at the given fractional coordinates and upload it to ComfyUI.
        # This guarantees exact mask boundaries — nothing outside the rectangle can change.
        rect_mask_filename = None
        if mask_rect:
            import io as _io
            from PIL import Image as _Image, ImageDraw as _ImageDraw
            x1r, y1r, x2r, y2r = [float(v.strip()) for v in mask_rect.split(",")]
            px1, py1 = int(x1r * canvas_w), int(y1r * canvas_h)
            px2, py2 = int(x2r * canvas_w), int(y2r * canvas_h)
            mask_img = _Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
            _ImageDraw.Draw(mask_img).rectangle([px1, py1, px2, py2], fill=(255, 255, 255))
            buf = _io.BytesIO()
            mask_img.save(buf, format="PNG")
            rect_mask_filename = await self._upload_image(buf.getvalue(), "rect_mask.png")

        # Mask source wiring: rect path loads the uploaded PNG; SAM path uses GroundingDINO output
        if rect_mask_filename:
            mask_nodes = {
                "28": {
                    "inputs": {"image": rect_mask_filename, "upload": "image"},
                    "class_type": "LoadImage",
                },
                "29": {
                    # channel="red" required — omitting causes ComfyUI 400 validation error
                    "inputs": {"image": ["28", 0], "channel": "red"},
                    "class_type": "ImageToMask",
                },
            }
            grow_mask_src = ["29", 0]
        else:
            mask_nodes = {
                "20": {
                    "inputs": {"model_name": "GroundingDINO_SwinT_OGC (694MB)"},
                    "class_type": "GroundingDinoModelLoader (segment anything)",
                },
                "21": {
                    "inputs": {"model_name": "sam_vit_l (1.25GB)"},
                    "class_type": "SAMModelLoader (segment anything)",
                },
                "22": {
                    "inputs": {
                        "image": ["11", 0],
                        "grounding_dino_model": ["20", 0],
                        "sam_model": ["21", 0],
                        "prompt": mask_subject,
                        "threshold": threshold,
                    },
                    "class_type": "GroundingDinoSAMSegment (segment anything)",
                    # Outputs: [0] = IMAGE (original), [1] = MASK (float, white=detected region)
                },
            }
            grow_mask_src = ["22", 1]

        workflow = {
            # --- SDXL model + interior LoRA ---
            **self._sdxl_base(with_lora=True),
            **self._sdxl_clip(lora_prompt, SDXL_NEGATIVE, clip_src, node_pos="3", node_neg="99"),

            # --- Image loading + scale to canvas resolution (1152×768 landscape default) ---
            "10": {
                "inputs": {"image": uploaded_filename, "upload": "image"},
                "class_type": "LoadImage",
            },
            "11": {
                "inputs": {
                    "image": ["10", 0],
                    "width": canvas_w, "height": canvas_h,
                    "upscale_method": "lanczos",
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },

            # --- Mask source: rect path (nodes 28/29) or SAM/GroundingDINO (nodes 20/21/22) ---
            # mask_nodes and grow_mask_src are set above based on whether mask_rect was provided.
            **mask_nodes,

            # --- Mask dilation: expand mask before encoding ---
            # grow_mask_src points to either ImageToMask[rect] or GroundingDinoSAMSegment[SAM].
            "23": {
                "inputs": {
                    "mask": grow_mask_src,
                    "expand": mask_expand,
                    "tapered_corners": True,
                },
                "class_type": "GrowMask",
            },

            # --- Soft mask blurring: gradient edges prevent hard seam artifacts at inpaint boundary ---
            # MaskToImage → ImageBlur → ImageToMask produces a grayscale gradient mask.
            # blur_radius max is 31 — 12 is safe and sufficient at 1024px.
            "24": {
                "inputs": {"mask": ["23", 0]},
                "class_type": "MaskToImage",
            },
            "25": {
                "inputs": {"image": ["24", 0], "blur_radius": 12, "sigma": 1.0},
                "class_type": "ImageBlur",
            },
            "26": {
                # "channel" is required — omitting it causes ComfyUI 400 validation error.
                "inputs": {"image": ["25", 0], "channel": "red"},
                "class_type": "ImageToMask",
            },

            # --- Fooocus Inpaint: load patch model + apply to SDXL checkpoint ---
            # Replaces VAEEncodeForInpaint + DifferentialDiffusion.
            # LoadFooocusInpaint reads head (.pth) and patch (.fooocus.patch) from models/inpaint/.
            # VAEEncodeInpaintConditioning combines VAE encoding + inpaint conditioning in one node:
            #   output [0]=positive cond, [1]=negative cond, [2]=latent_inpaint, [3]=latent_samples
            # ApplyFooocusInpaint patches the SDXL model with the inpaint head via latent_inpaint[2].
            # KSampler uses the patched model + modified conditioning + latent_samples[3].
            "30": {
                "inputs": {
                    "head": "fooocus_inpaint_head.pth",
                    "patch": "inpaint_v26.fooocus.patch",
                },
                "class_type": "INPAINT_LoadFooocusInpaint",
            },
            "31": {
                "inputs": {
                    "positive": ["3", 0],
                    "negative": ["99", 0],
                    "vae": ["4", 0],
                    "pixels": ["11", 0],
                    "mask": ["26", 0],
                },
                "class_type": "INPAINT_VAEEncodeInpaintConditioning",
            },
            "32": {
                "inputs": {
                    "model": model_src,
                    "patch": ["30", 0],
                    "latent": ["31", 2],  # latent_inpaint output — feeds the Fooocus head
                },
                "class_type": "INPAINT_ApplyFooocusInpaint",
            },

            # --- KSampler ---
            "6": {
                "inputs": {
                    "seed": seed,
                    "steps": SDXL_STEPS,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "denoise": denoise,
                    "model": ["32", 0],           # patched model from ApplyFooocusInpaint
                    "positive": ["31", 0],         # inpaint-conditioned positive
                    "negative": ["31", 1],         # inpaint-conditioned negative
                    "latent_image": ["31", 3],     # latent_samples (not latent_inpaint)
                },
                "class_type": "KSampler",
            },
            "7": {
                "inputs": {"samples": ["6", 0], "vae": ["4", 0]},
                "class_type": "VAEDecode",
            },
            "8": {
                "inputs": {"filename_prefix": "SDXL_inpaint_", "images": ["7", 0]},
                "class_type": "SaveImage",
            },
        }

        try:
            if rect_mask_filename:
                mask_desc = f"rect mask {mask_rect}"
            else:
                mask_desc = f"SAM auto-mask '{mask_subject}' (threshold={threshold})"
            await self._emit(
                __event_emitter__,
                f"Inpainting with {mask_desc}, expand={mask_expand}px (~60s)...",
            )
            prompt_id = await self._submit_workflow(workflow)
            filename = await self._wait_for_output(prompt_id, timeout=360)
            await self._emit(__event_emitter__, "Adding MLS compliance watermark...")
            url = await self._add_watermark(filename)
            await self._emit_done(__event_emitter__, "Inpaint complete")
            return (
                f"Inpainted: replaced **{mask_subject}**.\n\n"
                f"![Inpainted Room]({url})\n\n"
                f"[Open full size]({url})\n\n"
                f"*Denoise: {denoise} — use 0.85–0.95 for furniture placement, 0.65–0.75 for texture swaps.*"
            )
        except Exception as e:
            await self._emit_done(__event_emitter__, f"Failed: {e}")
            return f"Inpainting failed: {e}"

    async def transfer_style(
        self,
        prompt: str,
        style_strength: float = 0.3,
        __messages__: list = [],
        __event_emitter__=None,
    ) -> str:
        """
        Generate a new room image that applies the style, mood, materials, and color palette
        from a reference photo, while preserving the actual room's geometry via ControlNet depth.
        Attach TWO images: FIRST = reference (the style you want),
        SECOND = the room to restyle (depth map extracted to preserve room geometry).

        Room geometry (walls, ceiling, beams, fireplace shape, window layout) is preserved via
        ControlNet depth conditioning — you do NOT need to describe the structural features in
        the prompt. The text prompt drives room type, materials, and mood; IP-Adapter drives
        color palette and style; depth map drives layout.

        :param prompt: Describe the room type and desired look. Keep it concise:
          - Room type: "living room", "master bedroom", "open kitchen/dining"
          - Perspective (optional): "straight-on symmetrical view", "eye-level shot"
          - Style keywords: "warm neutral palette", "Scandinavian minimalist", "rustic farmhouse"
          - End with: "warm natural light, professional real estate photography"
          Example: "living room, warm neutral palette, professional real estate photography"
        :param style_strength: How strongly the reference image's style influences the output.
          0.3–0.4 = subtle tint (recommended), 0.5 = moderate, 0.6 = strong.
          Do NOT exceed 0.6 — higher values produce unrecognizable results.
          Default is 0.3. Only go higher if user explicitly requests stronger style.
        """
        await self._emit(__event_emitter__, "Acquiring images...")

        images = self._extract_images_from_messages(__messages__)
        if not images:
            return (
                "No images found. Please attach TWO images to your message:\n"
                "1. The REFERENCE photo (the style/mood you want)\n"
                "2. The ROOM photo (the space to restyle)"
            )
        if len(images) < 2:
            return (
                "Only one image found. Please attach TWO images:\n"
                "1. First image = REFERENCE (the style you want)\n"
                "2. Second image = ROOM to restyle"
            )

        ref_bytes, ref_ext = images[0]
        room_bytes, room_ext = images[1]

        await self._emit(__event_emitter__, "Uploading images to ComfyUI...")
        uploaded_ref = await self._upload_image(ref_bytes, f"reference_image.{ref_ext}")
        uploaded_room = await self._upload_image(room_bytes, f"room_image.{room_ext}")

        # Hard cap: above 0.6 destroys room structure
        style_strength = min(style_strength, 0.6)

        seed = random.randint(0, 2**32 - 1)
        clip_src = ["1", 1]  # no LoRA — IP-Adapter drives style instead

        workflow = {
            # --- SDXL checkpoint (no interior LoRA — IP-Adapter handles style) ---
            **self._sdxl_base(with_lora=False),
            **self._sdxl_clip(prompt, SDXL_NEGATIVE, clip_src, node_pos="3", node_neg="99"),

            # --- IP-Adapter Plus SDXL (comfyui_ipadapter_plus) ---
            # IPAdapterModelLoader loads the IP-Adapter weights
            "30": {
                "inputs": {"ipadapter_file": IPADAPTER_SDXL},
                "class_type": "IPAdapterModelLoader",
            },
            # CLIPVisionLoader loads CLIP ViT-H (already present, NOT SigLIP — that was SD3.5 only)
            "31": {
                "inputs": {"clip_name": CLIP_VISION_VIT_H},
                "class_type": "CLIPVisionLoader",
            },
            # Reference image: load + scale
            "32": {
                "inputs": {"image": uploaded_ref, "upload": "image"},
                "class_type": "LoadImage",
            },
            "33": {
                "inputs": {
                    "image": ["32", 0],
                    "width": 1024, "height": 1024,
                    "upscale_method": "lanczos",
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },
            # IPAdapterAdvanced: applies style from reference to model
            # clip_vision is optional here — passed explicitly to override any bundled encoder
            "34": {
                "inputs": {
                    "model": ["1", 0],
                    "ipadapter": ["30", 0],
                    "image": ["33", 0],
                    "clip_vision": ["31", 0],
                    "weight": style_strength,
                    "weight_type": "linear",
                    "combine_embeds": "concat",
                    "start_at": 0.0,
                    "end_at": 1.0,
                    "embeds_scaling": "V only",
                },
                "class_type": "IPAdapterAdvanced",
                # Output [0] = MODEL (modified with IP-Adapter style conditioning)
            },

            # --- Room photo → depth map for geometry conditioning ---
            "35": {
                "inputs": {"image": uploaded_room, "upload": "image"},
                "class_type": "LoadImage",
            },
            "36": {
                "inputs": {
                    "image": ["35", 0],
                    "width": 1024, "height": 1024,
                    "upscale_method": "lanczos",
                    "crop": "disabled",
                },
                "class_type": "ImageScale",
            },
            "37": {
                "inputs": {
                    "image": ["36", 0],
                    "ckpt_name": "depth_anything_v2_vitl.pth",
                    "resolution": 1024,
                },
                "class_type": "DepthAnythingV2Preprocessor",
            },
            "38": {
                "inputs": {"control_net_name": CONTROLNET_DEPTH},
                "class_type": "ControlNetLoader",
            },
            # Depth strength 0.65: slightly below stage_room (0.55 base) so IP-Adapter
            # can influence surface details while depth locks in walls/ceiling/major geometry.
            "39": {
                "inputs": {
                    "positive": ["3", 0],
                    "negative": ["99", 0],
                    "control_net": ["38", 0],
                    "image": ["37", 0],
                    "strength": 0.65,
                    "start_percent": 0.0,
                    "end_percent": 1.0,
                },
                "class_type": "ControlNetApplyAdvanced",
            },

            # --- Pure generation (EmptyLatentImage + denoise=1.0) ---
            # Geometry from depth ControlNet; style from IP-Adapter; content from text prompt.
            # Note: VAEEncode is safe on SDXL/MPS, but EmptyLatentImage + denoise=1.0 gives
            # cleaner results for style transfer (no img2img content leakage).
            "40": {
                "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
                "class_type": "EmptyLatentImage",
            },
            "6": {
                "inputs": {
                    "seed": seed,
                    "steps": SDXL_STEPS,
                    "cfg": SDXL_CFG,
                    "sampler_name": SDXL_SAMPLER,
                    "scheduler": SDXL_SCHEDULER,
                    "denoise": 1.0,
                    "model": ["34", 0],       # IP-Adapter conditioned model
                    "positive": ["39", 0],    # ControlNet-conditioned positive
                    "negative": ["39", 1],    # ControlNet-conditioned negative
                    "latent_image": ["40", 0],
                },
                "class_type": "KSampler",
            },
            "7": {
                "inputs": {"samples": ["6", 0], "vae": ["4", 0]},
                "class_type": "VAEDecode",
            },
            "8": {
                "inputs": {"filename_prefix": "SDXL_style_", "images": ["7", 0]},
                "class_type": "SaveImage",
            },
        }

        try:
            await self._emit(
                __event_emitter__,
                f"Transferring style (strength={style_strength}) with SDXL + IP-Adapter + ControlNet depth (~3–4 min)...",
            )
            prompt_id = await self._submit_workflow(workflow)
            filename = await self._wait_for_output(prompt_id, timeout=360)
            url = self._image_url(filename)
            await self._emit_done(__event_emitter__, "Style transfer complete")
            return (
                f"Style transfer complete.\n\n"
                f"![Restyled Room]({url})\n\n"
                f"[Open full size]({url})\n\n"
                f"*Style strength: {style_strength}. Room geometry preserved from depth map. "
                f"For subtler style try 0.3–0.4; stronger try 0.6 (do not exceed 0.6). "
                f"If geometry feels rigid lower depth strength; if it drifts raise it.*"
            )
        except Exception as e:
            await self._emit_done(__event_emitter__, f"Failed: {e}")
            return f"Style transfer failed: {e}"
