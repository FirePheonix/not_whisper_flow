"""
Real-time audio capture from microphone.
"""

import sounddevice as sd
import numpy as np
from queue import Queue
from threading import Thread, Event
from typing import Optional, Callable
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AudioCapture:
    """Captures audio from microphone in real-time."""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, 
                 chunk_size: int = 1024):
        """Initialize audio capture.
        
        Args:
            sample_rate: Audio sample rate in Hz (16000 for Whisper)
            channels: Number of audio channels (1 for mono)
            chunk_size: Number of frames per buffer
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        
        self.audio_queue = Queue()
        self.is_recording = Event()
        self.stream: Optional[sd.InputStream] = None
        
        logger.info(f"AudioCapture initialized: {sample_rate}Hz, {channels}ch")
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream. Called by sounddevice in background thread.
        
        Args:
            indata: Input audio data as numpy array
            frames: Number of frames
            time_info: Time information
            status: Status flags
        """
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        if self.is_recording.is_set():
            # Copy audio data to queue (indata is reused by sounddevice)
            audio_chunk = indata.copy()
            self.audio_queue.put(audio_chunk)

        # Always track live RMS for waveform visualisation
        self._current_rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
    
    def start(self):
        """Start audio capture."""
        if self.stream is not None:
            logger.warning("Audio capture already running")
            return
        
        try:
            self.is_recording.set()
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                blocksize=self.chunk_size,
                dtype=np.float32
            )
            self.stream.start()
            logger.info("Audio capture started")
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            self.is_recording.clear()
            raise
    
    def stop(self):
        """Stop audio capture."""
        if self.stream is None:
            return
        
        self.is_recording.clear()
        
        try:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            logger.info("Audio capture stopped")
        except Exception as e:
            logger.error(f"Error stopping audio capture: {e}")
    
    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Get next audio chunk from queue.
        
        Args:
            timeout: Maximum time to wait for audio chunk
            
        Returns:
            Audio chunk as numpy array, or None if timeout
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except:
            return None
    
    def get_all_audio(self) -> np.ndarray:
        """Get all buffered audio and concatenate.
        
        Returns:
            Concatenated audio as numpy array
        """
        chunks = []
        while not self.audio_queue.empty():
            chunk = self.audio_queue.get_nowait()
            chunks.append(chunk)
        
        if chunks:
            # Concatenate along time axis
            return np.concatenate(chunks, axis=0)
        else:
            return np.array([], dtype=np.float32)
    
    @property
    def current_rms(self) -> float:
        """Latest RMS level from the mic (0.0–1.0). Safe to call from any thread."""
        return getattr(self, '_current_rms', 0.0)

    def clear_buffer(self):
        """Clear the audio queue."""
        while not self.audio_queue.empty():
            self.audio_queue.get_nowait()
        logger.debug("Audio buffer cleared")
    
    @staticmethod
    def list_devices():
        """List available audio input devices."""
        devices = sd.query_devices()
        logger.info("Available audio devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                logger.info(f"  [{i}] {device['name']} - {device['max_input_channels']} channels")
        return devices
    
    @staticmethod
    def test_microphone(duration: float = 3.0, sample_rate: int = 16000):
        """Test microphone by recording and playing back.
        
        Args:
            duration: Recording duration in seconds
            sample_rate: Sample rate in Hz
        """
        logger.info(f"Testing microphone for {duration} seconds...")
        logger.info("Speak now!")
        
        try:
            # Record
            recording = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype=np.float32
            )
            sd.wait()
            
            # Calculate volume
            volume = np.abs(recording).mean()
            max_volume = np.abs(recording).max()
            
            logger.info(f"Recording complete!")
            logger.info(f"Average volume: {volume:.4f}")
            logger.info(f"Peak volume: {max_volume:.4f}")
            
            if max_volume < 0.01:
                logger.warning("Volume very low - check microphone connection")
            elif max_volume > 0.95:
                logger.warning("Volume very high - may cause clipping")
            else:
                logger.info("✓ Microphone working correctly!")
            
            return recording
            
        except Exception as e:
            logger.error(f"Microphone test failed: {e}")
            return None


if __name__ == "__main__":
    # Test the audio capture
    print("Listing audio devices:")
    AudioCapture.list_devices()
    
    print("\nTesting microphone:")
    AudioCapture.test_microphone(duration=3.0)
