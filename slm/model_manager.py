"""
SLM model management and loading.
CPU-friendly small language models for prompt enhancement.
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import Optional, Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SLMModelManager:
    """Manages Small Language Model loading and inference."""

    MODELS = {
        "smollm2-360m": "HuggingFaceTB/SmolLM2-360M-Instruct",
        "qwen2.5-0.5b": "Qwen/Qwen2.5-0.5B-Instruct",
        "qwen2.5-1.5b": "Qwen/Qwen2.5-1.5B-Instruct",
    }

    def __init__(self, model_name: str = "qwen2.5-0.5b", device: str = "cpu"):
        if model_name not in self.MODELS:
            raise ValueError(f"Model must be one of {list(self.MODELS.keys())}")

        self.model_name = model_name
        self.model_id = self.MODELS[model_name]
        self.device = self._get_device(device)

        self.tokenizer: Optional[AutoTokenizer] = None
        self.model: Optional[AutoModelForCausalLM] = None

        logger.info(f"SLMModelManager initialized: {model_name} on {self.device}")

    def _get_device(self, device: str) -> str:
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
                logger.info(f"Using CUDA: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                logger.info("Using CPU")
        return device

    def load_model(self):
        """Load the SLM model."""
        if self.model is not None:
            logger.debug("Model already loaded")
            return

        try:
            logger.info(f"Loading {self.model_name} ({self.model_id})...")

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                trust_remote_code=True
            )

            model_kwargs = {
                "trust_remote_code": True,
                "torch_dtype": torch.float16 if self.device == "cuda" else torch.float32,
            }

            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                **model_kwargs
            )

            self.model = self.model.to(self.device)
            self.model.eval()

            logger.info(f"Model loaded: {self.model_name}")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def generate(self,
                 prompt: str,
                 max_new_tokens: int = 256,
                 temperature: float = 0.7,
                 top_p: float = 0.9) -> str:
        """Generate text from a chat-formatted prompt."""
        if self.model is None:
            self.load_model()

        try:
            messages = [{"role": "user", "content": prompt}]

            if hasattr(self.tokenizer, 'apply_chat_template'):
                text = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            else:
                text = prompt

            inputs = self.tokenizer(text, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            input_length = inputs["input_ids"].shape[1]

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                )

            generated_ids = outputs[0][input_length:]
            result = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
            return result.strip()

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return ""

    def get_model_info(self) -> Dict[str, Any]:
        info = {
            "model_name": self.model_name,
            "model_id": self.model_id,
            "device": self.device,
            "loaded": self.model is not None,
        }
        if self.model is not None:
            param_count = sum(p.numel() for p in self.model.parameters())
            info["parameters"] = param_count
            info["parameters_millions"] = param_count / 1_000_000
        return info

    def unload_model(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            logger.info("Model unloaded")
