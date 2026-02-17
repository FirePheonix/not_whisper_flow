"""
Voice Activity Detection (VAD) to detect when user is speaking.
"""

import webrtcvad
import numpy as np
from collections import deque
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VoiceActivityDetector:
    """Detects voice activity in audio stream using WebRTC VAD."""
    
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2,
                 frame_duration_ms: int = 30):
        """Initialize VAD.
        
        Args:
            sample_rate: Audio sample rate (must be 8000, 16000, 32000, or 48000)
            aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
            frame_duration_ms: Frame duration in ms (10, 20, or 30)
        """
        if sample_rate not in [8000, 16000, 32000, 48000]:
            raise ValueError("Sample rate must be 8000, 16000, 32000, or 48000")
        
        if aggressiveness not in [0, 1, 2, 3]:
            raise ValueError("Aggressiveness must be 0-3")
        
        if frame_duration_ms not in [10, 20, 30]:
            raise ValueError("Frame duration must be 10, 20, or 30 ms")
        
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms
        
        # Calculate frame size in samples
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Initialize WebRTC VAD
        self.vad = webrtcvad.Vad(aggressiveness)
        
        # Buffering for smoothing
        self.num_padding_frames = 10  # Frames to pad before/after speech
        self.ring_buffer = deque(maxlen=self.num_padding_frames)
        self.triggered = False
        
        logger.info(f"VAD initialized: {sample_rate}Hz, aggressiveness={aggressiveness}")
    
    def _frame_generator(self, audio: np.ndarray):
        """Generate fixed-size frames from audio.
        
        Args:
            audio: Audio data as float32 numpy array
            
        Yields:
            Audio frames of fixed size
        """
        # Convert float32 to int16 for WebRTC VAD
        audio_int16 = (audio * 32768).astype(np.int16)
        
        n = len(audio_int16)
        offset = 0
        
        while offset + self.frame_size <= n:
            frame = audio_int16[offset:offset + self.frame_size]
            yield frame.tobytes()
            offset += self.frame_size
    
    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Check if audio chunk contains speech.
        
        Args:
            audio_chunk: Audio data as float32 numpy array
            
        Returns:
            True if speech detected, False otherwise
        """
        # Process each frame
        speech_frames = 0
        total_frames = 0
        
        for frame in self._frame_generator(audio_chunk):
            total_frames += 1
            if self.vad.is_speech(frame, self.sample_rate):
                speech_frames += 1
        
        if total_frames == 0:
            return False
        
        # Consider it speech if >30% of frames contain speech
        return (speech_frames / total_frames) > 0.3
    
    def detect_speech_segments(self, audio: np.ndarray, 
                              padding_duration_ms: int = 300) -> list:
        """Detect speech segments in audio with padding.
        
        Args:
            audio: Audio data as float32 numpy array
            padding_duration_ms: Padding to add before/after speech (ms)
            
        Returns:
            List of (start_idx, end_idx) tuples for speech segments
        """
        num_padding_frames = int(padding_duration_ms / self.frame_duration_ms)
        ring_buffer = deque(maxlen=num_padding_frames)
        triggered = False
        
        segments = []
        speech_frames = []
        
        for i, frame in enumerate(self._frame_generator(audio)):
            is_speech = self.vad.is_speech(frame, self.sample_rate)
            
            if not triggered:
                ring_buffer.append((i, is_speech))
                num_voiced = len([f for f, speech in ring_buffer if speech])
                
                # Start of speech segment
                if num_voiced > 0.8 * ring_buffer.maxlen:
                    triggered = True
                    # Add buffered frames
                    speech_frames.extend([f for f, _ in ring_buffer])
                    ring_buffer.clear()
            else:
                speech_frames.append(i)
                ring_buffer.append((i, is_speech))
                num_unvoiced = len([f for f, speech in ring_buffer if not speech])
                
                # End of speech segment
                if num_unvoiced > 0.8 * ring_buffer.maxlen:
                    triggered = False
                    
                    # Calculate segment boundaries
                    start_idx = speech_frames[0] * self.frame_size
                    end_idx = speech_frames[-1] * self.frame_size + self.frame_size
                    segments.append((start_idx, end_idx))
                    
                    ring_buffer.clear()
                    speech_frames = []
        
        # Handle ongoing speech at end
        if speech_frames:
            start_idx = speech_frames[0] * self.frame_size
            end_idx = len(audio)
            segments.append((start_idx, end_idx))
        
        logger.debug(f"Detected {len(segments)} speech segment(s)")
        return segments
    
    def get_speech_audio(self, audio: np.ndarray) -> np.ndarray:
        """Extract only speech portions from audio.
        
        Args:
            audio: Audio data as float32 numpy array
            
        Returns:
            Audio containing only speech segments
        """
        segments = self.detect_speech_segments(audio)
        
        if not segments:
            logger.debug("No speech detected")
            return np.array([], dtype=np.float32)
        
        # Concatenate all speech segments
        speech_chunks = []
        for start, end in segments:
            speech_chunks.append(audio[start:end])
        
        return np.concatenate(speech_chunks)


if __name__ == "__main__":
    # Test VAD
    import sounddevice as sd
    
    print("Testing Voice Activity Detection...")
    print("Recording 5 seconds - try speaking and being silent...")
    
    sample_rate = 16000
    duration = 5
    
    audio = sd.rec(int(duration * sample_rate), 
                   samplerate=sample_rate, 
                   channels=1, 
                   dtype=np.float32)
    sd.wait()
    
    audio = audio.flatten()
    
    vad = VoiceActivityDetector(sample_rate=sample_rate, aggressiveness=2)
    segments = vad.detect_speech_segments(audio)
    
    print(f"\nDetected {len(segments)} speech segment(s):")
    for i, (start, end) in enumerate(segments):
        duration_s = (end - start) / sample_rate
        print(f"  Segment {i+1}: {start/sample_rate:.2f}s - {end/sample_rate:.2f}s ({duration_s:.2f}s)")
    
    speech_audio = vad.get_speech_audio(audio)
    print(f"\nTotal speech duration: {len(speech_audio)/sample_rate:.2f}s")
