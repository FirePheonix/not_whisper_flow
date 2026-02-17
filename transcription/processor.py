"""
Transcription processing pipeline.
Coordinates audio capture, VAD, and Whisper transcription.
"""

import numpy as np
from typing import Optional, Callable
from queue import Queue
from threading import Thread, Event
from utils.logger import setup_logger
from audio import AudioCapture, VoiceActivityDetector, preprocess_audio
from transcription.whisper_engine import WhisperEngine

logger = setup_logger(__name__)


class TranscriptionProcessor:
    """Processes audio chunks and produces transcriptions."""
    
    def __init__(self,
                 whisper_model: str = "base",
                 sample_rate: int = 16000,
                 use_vad: bool = True,
                 vad_aggressiveness: int = 2):
        """Initialize transcription processor.
        
        Args:
            whisper_model: Whisper model size
            sample_rate: Audio sample rate
            use_vad: Whether to use voice activity detection
            vad_aggressiveness: VAD aggressiveness (0-3)
        """
        self.sample_rate = sample_rate
        self.use_vad = use_vad
        
        # Initialize components
        self.whisper = WhisperEngine(model_name=whisper_model)
        self.whisper.load_model()  # Pre-load for faster first transcription
        
        if use_vad:
            self.vad = VoiceActivityDetector(
                sample_rate=sample_rate,
                aggressiveness=vad_aggressiveness
            )
        else:
            self.vad = None
        
        # Callback for transcription results
        self.on_transcription: Optional[Callable[[str], None]] = None
        
        logger.info("TranscriptionProcessor initialized")
    
    def process_audio(self, audio: np.ndarray) -> Optional[str]:
        """Process audio chunk and return transcription.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            Transcribed text, or None if no speech detected
        """
        if len(audio) == 0:
            logger.debug("Empty audio chunk")
            return None
        
        # Preprocess audio
        processed = preprocess_audio(
            audio,
            sample_rate=self.sample_rate,
            target_sample_rate=16000,
            normalize=True
        )
        
        # Apply VAD if enabled
        if self.vad is not None:
            speech_audio = self.vad.get_speech_audio(processed)
            
            if len(speech_audio) == 0:
                logger.debug("No speech detected in audio")
                return None
            
            # Check if we have enough speech
            speech_duration = len(speech_audio) / self.sample_rate
            if speech_duration < 0.3:  # Minimum 300ms
                logger.debug(f"Speech too short: {speech_duration:.2f}s")
                return None
            
            processed = speech_audio
        
        # Transcribe
        try:
            result = self.whisper.transcribe(processed)
            text = result.get("text", "").strip()
            
            if text:
                logger.info(f"✓ Transcribed: '{text}'")
                
                # Call callback if set
                if self.on_transcription:
                    self.on_transcription(text)
                
                return text
            else:
                logger.debug("Empty transcription")
                return None
                
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
    
    def process_audio_async(self, audio: np.ndarray):
        """Process audio asynchronously in background thread.
        
        Args:
            audio: Audio data as numpy array
        """
        def _process():
            self.process_audio(audio)
        
        thread = Thread(target=_process, daemon=True)
        thread.start()
    
    def set_transcription_callback(self, callback: Callable[[str], None]):
        """Set callback function for transcription results.
        
        Args:
            callback: Function that takes transcribed text as argument
        """
        self.on_transcription = callback
        logger.debug("Transcription callback set")


class ContinuousTranscriber:
    """Continuously captures and transcribes audio."""
    
    def __init__(self,
                 whisper_model: str = "base",
                 sample_rate: int = 16000,
                 buffer_duration_s: float = 3.0):
        """Initialize continuous transcriber.
        
        Args:
            whisper_model: Whisper model size
            sample_rate: Audio sample rate
            buffer_duration_s: How long to buffer audio before transcribing
        """
        self.sample_rate = sample_rate
        self.buffer_duration_s = buffer_duration_s
        self.buffer_size = int(sample_rate * buffer_duration_s)
        
        # Components
        self.audio_capture = AudioCapture(sample_rate=sample_rate)
        self.processor = TranscriptionProcessor(
            whisper_model=whisper_model,
            sample_rate=sample_rate
        )
        
        # State
        self.is_running = Event()
        self.worker_thread: Optional[Thread] = None
        self.audio_buffer = []
        
        logger.info(f"ContinuousTranscriber initialized (buffer: {buffer_duration_s}s)")
    
    def _worker(self):
        """Worker thread that processes audio continuously."""
        logger.info("Transcription worker started")
        
        while self.is_running.is_set():
            # Get audio chunk
            chunk = self.audio_capture.get_audio_chunk(timeout=0.5)
            
            if chunk is None:
                continue
            
            # Add to buffer
            self.audio_buffer.append(chunk)
            
            # Calculate total buffered samples
            total_samples = sum(len(c) for c in self.audio_buffer)
            
            # Process when buffer is full
            if total_samples >= self.buffer_size:
                # Concatenate buffer
                audio = np.concatenate(self.audio_buffer, axis=0).flatten()
                
                # Process asynchronously
                self.processor.process_audio_async(audio)
                
                # Clear buffer
                self.audio_buffer = []
        
        logger.info("Transcription worker stopped")
    
    def start(self):
        """Start continuous transcription."""
        if self.is_running.is_set():
            logger.warning("Already running")
            return
        
        # Start audio capture
        self.audio_capture.start()
        
        # Start worker thread
        self.is_running.set()
        self.worker_thread = Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        logger.info("Continuous transcription started")
    
    def stop(self):
        """Stop continuous transcription."""
        if not self.is_running.is_set():
            return
        
        # Stop worker
        self.is_running.clear()
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        
        # Stop audio capture
        self.audio_capture.stop()
        
        # Process remaining buffer
        if self.audio_buffer:
            audio = np.concatenate(self.audio_buffer, axis=0).flatten()
            self.processor.process_audio(audio)
            self.audio_buffer = []
        
        logger.info("Continuous transcription stopped")
    
    def set_transcription_callback(self, callback: Callable[[str], None]):
        """Set callback for transcription results.
        
        Args:
            callback: Function that takes transcribed text
        """
        self.processor.set_transcription_callback(callback)


if __name__ == "__main__":
    # Test continuous transcription
    print("Continuous Transcription Test")
    print("=" * 60)
    print("Speak for a few seconds, then press Ctrl+C to stop")
    print("=" * 60)
    
    def on_transcription(text):
        print(f"\n>>> {text}\n")
    
    transcriber = ContinuousTranscriber(
        whisper_model="base",
        buffer_duration_s=3.0
    )
    transcriber.set_transcription_callback(on_transcription)
    
    try:
        transcriber.start()
        
        # Keep running
        import time
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        transcriber.stop()
        print("Done!")
