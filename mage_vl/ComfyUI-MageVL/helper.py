import os
import base64
import mimetypes
from pathlib import Path
import numpy as np
import torch
from PIL import Image

try:
    import folder_paths
    HAS_COMFY = True
except ImportError:
    HAS_COMFY = False

# Global cache for loaded model and processor
_MODEL_CACHE = {}


def get_model_path(model_name: str = "microsoft/Mage-VL") -> str:
    """
    Resolve model path. Checks ComfyUI models directory, local folder, or Hugging Face repo ID.
    If the model isn't present locally and is a HF repo ID, snapshot_download is used to download it.
    """
    if os.path.exists(model_name):
        return model_name

    # Check ComfyUI LLM/MageVL folders if available
    if HAS_COMFY:
        custom_llm_dir = os.path.join(folder_paths.models_dir, "LLM", os.path.basename(model_name))
        if os.path.exists(custom_llm_dir):
            return custom_llm_dir
        custom_mage_dir = os.path.join(folder_paths.models_dir, "mage_vl", os.path.basename(model_name))
        if os.path.exists(custom_mage_dir):
            return custom_mage_dir

    # Download or return Hugging Face repo ID
    return model_name


def load_mage_vl_model(model_name: str = "microsoft/Mage-VL", device: str = "auto", dtype: str = "auto"):
    """
    Load or retrieve cached Mage-VL model and processor.
    """
    from transformers import AutoModelForCausalLM, AutoProcessor
    from huggingface_hub import snapshot_download

    resolved_path = get_model_path(model_name)

    # Determine torch dtype
    if dtype == "float16":
        torch_dtype = torch.float16
    elif dtype == "bfloat16":
        torch_dtype = torch.bfloat16
    elif dtype == "float32":
        torch_dtype = torch.float32
    else:
        torch_dtype = "auto"

    cache_key = (resolved_path, device, str(torch_dtype))
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    print(f"[ComfyUI-MageVL] Loading Mage-VL model from: '{resolved_path}' (device={device}, dtype={dtype})...")

    # Download snapshot if codec engine neural requires local path and resolved_path is HF model ID
    if not os.path.isdir(resolved_path):
        try:
            print(f"[ComfyUI-MageVL] Downloading model snapshot for '{resolved_path}' from Hugging Face...")
            resolved_path = snapshot_download(repo_id=resolved_path)
        except Exception as e:
            print(f"[ComfyUI-MageVL] Note: snapshot_download notice: {e}")

    processor = AutoProcessor.from_pretrained(resolved_path, trust_remote_code=True)

    load_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch_dtype,
    }
    if device == "auto":
        load_kwargs["device_map"] = "auto"
    
    model = AutoModelForCausalLM.from_pretrained(resolved_path, **load_kwargs).eval()

    if device != "auto":
        model = model.to(device)

    _MODEL_CACHE[cache_key] = (model, processor, resolved_path)
    print("[ComfyUI-MageVL] Model successfully loaded and cached.")
    return model, processor, resolved_path


def tensor_to_pil(image_tensor: torch.Tensor) -> Image.Image:
    """
    Convert a single ComfyUI image tensor [H, W, C] or [1, H, W, C] (float 0..1) to PIL Image.
    """
    if image_tensor.ndim == 4:
        image_tensor = image_tensor[0]
    
    np_img = (255.0 * image_tensor.cpu().numpy()).clip(0, 255).astype(np.uint8)
    return Image.fromarray(np_img)


def batch_tensor_to_pil_list(image_tensor: torch.Tensor, num_frames: int = 32) -> list[Image.Image]:
    """
    Convert a batch of ComfyUI image tensors [N, H, W, C] to a list of PIL Images, sampled down to num_frames.
    """
    if image_tensor.ndim == 3:
        return [tensor_to_pil(image_tensor)]

    total_frames = image_tensor.shape[0]
    indices = np.linspace(0, total_frames - 1, min(num_frames, total_frames), dtype=int)
    
    frames = []
    for idx in indices:
        frames.append(tensor_to_pil(image_tensor[idx]))
    return frames


def sample_video_file(video_path: str, num_frames: int = 32) -> list[Image.Image]:
    """
    Sample frames uniformly from a video file using OpenCV.
    """
    import cv2

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    capture = cv2.VideoCapture(video_path)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        capture.release()
        raise ValueError(f"Could not read video or frame count is 0: {video_path}")

    indices = np.linspace(0, frame_count - 1, min(num_frames, frame_count), dtype=int)
    frames = []
    for index in indices:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(index))
        ok, frame = capture.read()
        if not ok:
            capture.release()
            raise ValueError(f"Could not decode frame {index} from: {video_path}")
        frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    capture.release()
    return frames
