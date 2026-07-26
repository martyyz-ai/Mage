import os
import torch
from PIL import Image
from .helper import (
    load_mage_vl_model,
    tensor_to_pil,
    batch_tensor_to_pil_list,
    sample_video_file,
)


class MageVLModelLoader:
    """
    ComfyUI Node to load and cache the Mage-VL model and processor.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_name": ("STRING", {"default": "microsoft/Mage-VL", "multiline": False}),
                "device": (["auto", "cuda", "cpu"], {"default": "auto"}),
                "precision": (["auto", "bfloat16", "float16", "float32"], {"default": "auto"}),
            }
        }

    RETURN_TYPES = ("MAGE_VL_MODEL",)
    RETURN_NAMES = ("mage_vl_model",)
    FUNCTION = "load_model"
    CATEGORY = "MageVL"

    def load_model(self, model_name: str, device: str, precision: str):
        model, processor, model_path = load_mage_vl_model(
            model_name=model_name, device=device, dtype=precision
        )
        return ((model, processor, model_path),)


class MageVL_Describe:
    """
    ComfyUI Node to generate detailed descriptions or answer questions for images or videos using Mage-VL.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "default": "Describe this media in detail.",
                    "multiline": True,
                }),
                "max_new_tokens": ("INT", {
                    "default": 256,
                    "min": 16,
                    "max": 4096,
                    "step": 16,
                }),
                "video_backend": (["frames", "codec"], {"default": "frames"}),
                "num_frames": ("INT", {
                    "default": 32,
                    "min": 1,
                    "max": 256,
                    "step": 1,
                }),
                "max_pixels": ("INT", {
                    "default": 150000,
                    "min": 10000,
                    "max": 2000000,
                    "step": 10000,
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                }),
            },
            "optional": {
                "mage_vl_model": ("MAGE_VL_MODEL",),
                "image": ("IMAGE",),
                "video_path": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "generate_description"
    CATEGORY = "MageVL"

    def generate_description(
        self,
        prompt: str,
        max_new_tokens: int,
        video_backend: str,
        num_frames: int,
        max_pixels: int,
        seed: int,
        mage_vl_model=None,
        image=None,
        video_path=None,
    ):
        # Set random seed for reproducibility if needed
        torch.manual_seed(seed)

        # Retrieve or auto-load default Mage-VL model
        if mage_vl_model is not None:
            model, processor, model_path = mage_vl_model
        else:
            model, processor, model_path = load_mage_vl_model(
                model_name="microsoft/Mage-VL", device="auto", dtype="auto"
            )

        # Determine input media type (image vs video)
        media_type = None
        pil_images = []
        video_file_input = None

        # Check video_path first
        if video_path and isinstance(video_path, str) and video_path.strip():
            v_path = video_path.strip()
            if os.path.isfile(v_path):
                media_type = "video"
                if video_backend == "codec":
                    video_file_input = v_path
                else:
                    pil_images = sample_video_file(v_path, num_frames=num_frames)

        # If no video path, check image tensor input
        if media_type is None and image is not None:
            if image.ndim == 4 and image.shape[0] > 1:
                # Batch of images passed (treated as video frames)
                media_type = "video"
                pil_images = batch_tensor_to_pil_list(image, num_frames=num_frames)
            else:
                # Single image
                media_type = "image"
                pil_images = [tensor_to_pil(image)]

        if media_type is None:
            raise ValueError(
                "[ComfyUI-MageVL] Please provide an 'image' input or a valid 'video_path'."
            )

        # Prepare chat message structure for processor
        messages = [{
            "role": "user",
            "content": [
                {"type": media_type},
                {"type": "text", "text": prompt},
            ],
        }]

        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        if media_type == "image":
            inputs = processor(
                text=[text],
                images=[pil_images[0].convert("RGB")],
                return_tensors="pt",
            )
        elif video_backend == "codec" and video_file_input is not None:
            codec_config = {
                "engine": "hevc",
                "target_canvas": num_frames,
                "patch": 16,
            }
            inputs = processor(
                text=[text],
                videos=[video_file_input],
                video_backend="codec",
                max_pixels=max_pixels,
                codec_config=codec_config,
                return_tensors="pt",
                padding=True,
            )
        else:
            inputs = processor(
                text=[text],
                videos=[pil_images],
                return_tensors="pt",
                padding=True,
            )

        # Move inputs to target model device and dtype
        device = next(model.parameters()).device
        inputs = {k: (v.to(device) if hasattr(v, "to") else v) for k, v in inputs.items()}
        if "pixel_values" in inputs:
            inputs["pixel_values"] = inputs["pixel_values"].to(model.dtype)

        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )

        answer = processor.tokenizer.decode(
            output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )

        return (answer.strip(),)


NODE_CLASS_MAPPINGS = {
    "MageVLModelLoader": MageVLModelLoader,
    "MageVL_Describe": MageVL_Describe,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MageVLModelLoader": "Mage-VL Model Loader",
    "MageVL_Describe": "Mage-VL Describe (Image/Video)",
}
