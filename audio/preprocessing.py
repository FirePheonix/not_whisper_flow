"""
Audio preprocessing for optimal Whisper performance.
"""

import numpy as np
from scipy import signal
from utils.logger import setup_logger

logger = setup_logger(__name__)


def preprocess_audio(audio: np.ndarray, 
                     sample_rate: int = 16000,
                     target_sample_rate: int = 16000,
                     normalize: bool = True,
                     remove_dc: bool = True) -> np.ndarray:
    """Preprocess audio for Whisper.
    
    Args:
        audio: Input audio as numpy array
        sample_rate: Current sample rate
        target_sample_rate: Target sample rate (Whisper uses 16000)
        normalize: Whether to normalize volume
        remove_dc: Whether to remove DC offset
        
    Returns:
        Preprocessed audio
    """
    # Ensure 1D array
    if audio.ndim > 1:
        audio = audio.flatten()
    
    # Remove DC offset (mean)
    if remove_dc:
        audio = audio - np.mean(audio)
    
    # Resample if needed
    if sample_rate != target_sample_rate:
        num_samples = int(len(audio) * target_sample_rate / sample_rate)
        audio = signal.resample(audio, num_samples)
        logger.debug(f"Resampled from {sample_rate}Hz to {target_sample_rate}Hz")
    
    # Normalize volume
    if normalize:
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = audio / max_val * 0.95  # Leave some headroom
            logger.debug(f"Normalized audio (max: {max_val:.4f})")
    
    # Ensure float32
    audio = audio.astype(np.float32)
    
    return audio


def apply_noise_gate(audio: np.ndarray, 
                     threshold: float = 0.01,
                     sample_rate: int = 16000) -> np.ndarray:
    """Apply simple noise gate to reduce background noise.
    
    Args:
        audio: Input audio
        threshold: Volume threshold below which audio is muted
        sample_rate: Sample rate
        
    Returns:
        Audio with noise gate applied
    """
    # Calculate envelope (moving average of absolute values)
    window_size = int(sample_rate * 0.02)  # 20ms window
    envelope = np.convolve(np.abs(audio), 
                          np.ones(window_size) / window_size, 
                          mode='same')
    
    # Create gate mask
    gate = envelope > threshold
    
    # Apply with smoothing to avoid clicks
    smoothed_gate = np.convolve(gate.astype(float), 
                                np.ones(window_size) / window_size, 
                                mode='same')
    
    return audio * smoothed_gate


def trim_silence(audio: np.ndarray, 
                 threshold: float = 0.01,
                 sample_rate: int = 16000,
                 padding_ms: int = 100) -> np.ndarray:
    """Trim silence from start and end of audio.
    
    Args:
        audio: Input audio
        threshold: Volume threshold for silence detection
        sample_rate: Sample rate
        padding_ms: Padding to keep at start/end (ms)
        
    Returns:
        Trimmed audio
    """
    # Find non-silent regions
    non_silent = np.abs(audio) > threshold
    
    if not non_silent.any():
        logger.warning("Audio is completely silent")
        return audio
    
    # Find first and last non-silent sample
    non_silent_indices = np.where(non_silent)[0]
    start = non_silent_indices[0]
    end = non_silent_indices[-1]
    
    # Add padding
    padding_samples = int(padding_ms * sample_rate / 1000)
    start = max(0, start - padding_samples)
    end = min(len(audio), end + padding_samples)
    
    trimmed = audio[start:end]
    logger.debug(f"Trimmed {start} samples from start, {len(audio)-end} from end")
    
    return trimmed


def ensure_minimum_length(audio: np.ndarray, 
                         min_duration_s: float = 0.1,
                         sample_rate: int = 16000) -> np.ndarray:
    """Ensure audio meets minimum length requirement.
    
    Args:
        audio: Input audio
        min_duration_s: Minimum duration in seconds
        sample_rate: Sample rate
        
    Returns:
        Audio padded to minimum length if needed
    """
    min_samples = int(min_duration_s * sample_rate)
    
    if len(audio) < min_samples:
        # Pad with zeros
        padding = np.zeros(min_samples - len(audio), dtype=audio.dtype)
        audio = np.concatenate([audio, padding])
        logger.debug(f"Padded audio to {min_duration_s}s")
    
    return audio


if __name__ == "__main__":
    # Test preprocessing
    import sounddevice as sd
    
    print("Recording 3 seconds for preprocessing test...")
    sample_rate = 16000
    audio = sd.rec(int(3 * sample_rate), 
                   samplerate=sample_rate, 
                   channels=1, 
                   dtype=np.float32)
    sd.wait()
    audio = audio.flatten()
    
    print(f"Original: {len(audio)} samples, max: {np.abs(audio).max():.4f}")
    
    processed = preprocess_audio(audio, sample_rate)
    print(f"Processed: {len(processed)} samples, max: {np.abs(processed).max():.4f}")
    
    trimmed = trim_silence(processed, sample_rate=sample_rate)
    print(f"Trimmed: {len(trimmed)} samples ({len(trimmed)/sample_rate:.2f}s)")
