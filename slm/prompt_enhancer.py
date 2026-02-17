"""
Prompt enhancement engine using local SLM models.
Two modes: code prompt generation and voice notes cleanup.
"""

from typing import Optional
from utils.logger import setup_logger
from slm.model_manager import SLMModelManager
from slm.prompt_templates import PromptTemplates

logger = setup_logger(__name__)


CODE_PROMPT_SYSTEM = """You are an expert prompt engineer. Your job is to take rough, spoken descriptions of coding tasks and transform them into clear, detailed, well-structured prompts that will get the best results from AI coding assistants.

Rules:
- Output ONLY the improved prompt, nothing else
- Be specific and actionable
- Include relevant technical details (types, patterns, error handling)
- Keep it concise but comprehensive (3-6 sentences)
- Preserve the user's intent exactly, just make it clearer
- Do not add unnecessary requirements the user didn't mention"""

NOTES_CLEANUP_SYSTEM = """You are a helpful assistant that cleans up spoken text into well-written notes. Your job is to take raw speech-to-text output and produce clean, organized text.

Rules:
- Output ONLY the cleaned up text, nothing else
- Fix grammar, punctuation, and filler words
- Preserve the original meaning and all details
- Organize into clear sentences and paragraphs
- Do not add information that wasn't in the original
- Keep the same tone and style"""


class PromptEnhancer:
    """Enhances voice transcriptions using local SLM models."""

    def __init__(self, model_name: str = "qwen2.5-0.5b", use_slm: bool = True):
        self.use_slm = use_slm
        self.slm: Optional[SLMModelManager] = None

        if use_slm:
            try:
                self.slm = SLMModelManager(model_name=model_name)
                logger.info(f"SLM initialized: {model_name} (will load on first use)")
            except Exception as e:
                logger.warning(f"Failed to init SLM: {e}. Using templates only.")
                self.use_slm = False

        self.templates = PromptTemplates()
        logger.info(f"PromptEnhancer ready (SLM: {self.use_slm})")

    def enhance_code_prompt(self, text: str) -> str:
        """Transform rough voice input into a structured coding prompt."""
        if not text or not text.strip():
            return text

        text = text.strip()
        logger.info(f"Enhancing code prompt: '{text}'")

        if self.use_slm and self.slm is not None:
            try:
                prompt = f"{CODE_PROMPT_SYSTEM}\n\nRaw voice input: \"{text}\"\n\nImproved coding prompt:"
                enhanced = self.slm.generate(prompt, max_new_tokens=300, temperature=0.7)

                if enhanced and len(enhanced) > len(text) * 0.5:
                    logger.info(f"SLM enhanced: '{enhanced[:100]}...'")
                    return enhanced
                else:
                    logger.warning("SLM output too short, falling back to templates")
            except Exception as e:
                logger.error(f"SLM enhancement failed: {e}")

        enhanced = self.templates.build_enhanced_prompt(text)
        logger.info(f"Template enhanced: '{enhanced[:100]}...'")
        return enhanced

    def enhance_voice_note(self, text: str) -> str:
        """Clean up raw voice transcription into polished notes."""
        if not text or not text.strip():
            return text

        text = text.strip()
        logger.info(f"Cleaning voice note: '{text}'")

        if self.use_slm and self.slm is not None:
            try:
                prompt = f"{NOTES_CLEANUP_SYSTEM}\n\nRaw speech: \"{text}\"\n\nCleaned up text:"
                cleaned = self.slm.generate(prompt, max_new_tokens=500, temperature=0.3)

                if cleaned and len(cleaned) > len(text) * 0.3:
                    logger.info(f"SLM cleaned: '{cleaned[:100]}...'")
                    return cleaned
                else:
                    logger.warning("SLM output too short, returning raw text")
            except Exception as e:
                logger.error(f"SLM cleanup failed: {e}")

        return text

    def enhance(self, text: str, mode: str = "code_prompt") -> str:
        """Enhance text based on the current mode."""
        if mode == "voice_notes":
            return self.enhance_voice_note(text)
        return self.enhance_code_prompt(text)

    def load_model(self):
        """Eagerly load the SLM model."""
        if self.slm is not None:
            self.slm.load_model()

    def unload_model(self):
        """Unload the SLM model to free memory."""
        if self.slm is not None:
            self.slm.unload_model()
