"""
Whisper model management and transcription engine.
"""

import whisper
import torch
import numpy as np
from typing import Optional, Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)


class WhisperEngine:
    """Manages Whisper model and performs transcription."""
    
    # Available model sizes
    MODELS = ["tiny", "base", "small", "medium", "large"]
    
    def __init__(self, model_name: str = "base", device: str = "auto"):
        """Initialize Whisper engine.
        
        Args:
            model_name: Model size (tiny, base, small, medium, large)
            device: Device to use ('auto', 'cpu', 'cuda')
        """
        if model_name not in self.MODELS:
            raise ValueError(f"Model must be one of {self.MODELS}")
        
        self.model_name = model_name
        self.device = self._get_device(device)
        self.model: Optional[whisper.Whisper] = None
        
        logger.info(f"WhisperEngine initialized: model={model_name}, device={self.device}")
    
    def _get_device(self, device: str) -> str:
        """Determine which device to use.
        
        Args:
            device: Requested device ('auto', 'cpu', 'cuda')
            
        Returns:
            Device string for torch
        """
        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
                logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                logger.info("CUDA not available, using CPU")
        
        return device
    
    def load_model(self):
        """Load the Whisper model (lazy loading)."""
        if self.model is not None:
            logger.debug("Model already loaded")
            return
        
        try:
            logger.info(f"Loading Whisper {self.model_name} model...")
            self.model = whisper.load_model(self.model_name, device=self.device)
            logger.info(f"✓ Whisper {self.model_name} model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe(self, 
                   audio: np.ndarray,
                   language: Optional[str] = None,
                   task: str = "transcribe",
                   **kwargs) -> Dict[str, Any]:
        """Transcribe audio using Whisper.
        
        Args:
            audio: Audio data as float32 numpy array (16kHz)
            language: Language code (None for auto-detect)
            task: 'transcribe' or 'translate'
            **kwargs: Additional Whisper options
            
        Returns:
            Dictionary with 'text' and other metadata
        """
        # Ensure model is loaded
        if self.model is None:
            self.load_model()
        
        try:
            # Whisper expects float32 audio
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            
            # Ensure 1D
            if audio.ndim > 1:
                audio = audio.flatten()
            
            # Transcribe
            logger.debug(f"Transcribing {len(audio)/16000:.2f}s of audio...")
            
            result = self.model.transcribe(
                audio,
                language=language,
                task=task,
                fp16=(self.device == "cuda"),  # Use FP16 on GPU for speed
                **kwargs
            )
            
            text = result["text"].strip()
            logger.info(f"Transcription: '{text}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"text": "", "error": str(e)}
    
    def transcribe_file(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """Transcribe audio from file.
        
        Args:
            audio_path: Path to audio file
            **kwargs: Additional Whisper options
            
        Returns:
            Dictionary with 'text' and other metadata
        """
        if self.model is None:
            self.load_model()
        
        try:
            logger.info(f"Transcribing file: {audio_path}")
            result = self.model.transcribe(audio_path, **kwargs)
            logger.info(f"Transcription: '{result['text']}'")
            return result
        except Exception as e:
            logger.error(f"File transcription failed: {e}")
            return {"text": "", "error": str(e)}
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model.
        
        Returns:
            Dictionary with model information
        """
        if self.model is None:
            return {
                "model_name": self.model_name,
                "loaded": False,
                "device": self.device
            }
        
        # Estimate model size
        param_count = sum(p.numel() for p in self.model.parameters())
        
        return {
            "model_name": self.model_name,
            "loaded": True,
            "device": self.device,
            "parameters": param_count,
            "cuda_available": torch.cuda.is_available(),
        }
    
    def unload_model(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
            
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            logger.info("Model unloaded")
    
    @staticmethod
    def test(model_name: str = "base", duration: float = 3.0):
        """Test Whisper with microphone input.
        
        Args:
            model_name: Model to test
            duration: Recording duration in seconds
        """
        import sounddevice as sd
        
        logger.info(f"Testing Whisper {model_name} model...")
        logger.info(f"Recording {duration} seconds - speak now!")
        
        # Record
        sample_rate = 16000
        audio = sd.rec(int(duration * sample_rate),
                      samplerate=sample_rate,
                      channels=1,
                      dtype=np.float32)
        sd.wait()
        audio = audio.flatten()
        
        # Transcribe
        engine = WhisperEngine(model_name=model_name)
        result = engine.transcribe(audio)
        
        print(f"\n{'='*60}")
        print(f"Transcription: {result['text']}")
        print(f"Language: {result.get('language', 'unknown')}")
        print(f"{'='*60}\n")
        
        return result


if __name__ == "__main__":
    # Test the Whisper engine
    print("Whisper Engine Test")
    print("=" * 60)
    
    # Show available models
    print(f"Available models: {WhisperEngine.MODELS}")
    
    # Check CUDA
    if torch.cuda.is_available():
        print(f"✓ CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        print("✗ CUDA not available (will use CPU)")
    
    print("\nStarting transcription test...")
    WhisperEngine.test(model_name="base", duration=5.0)
