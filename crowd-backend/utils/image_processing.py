"""
Image processing utilities
"""
import cv2
import numpy as np
from collections import deque
from typing import Tuple

class FrameEnhancer:
    """Enhance frame quality for better detection"""
    
    @staticmethod
    def enhance(frame: np.ndarray) -> np.ndarray:
        """Apply multi-stage enhancement"""
        enhanced = frame.copy()

        # Denoise
        enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)

        # CLAHE for contrast
        lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

        # Sharpen
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]) / 1.0
        enhanced = cv2.filter2D(enhanced, -1, kernel)

        return enhanced

    @staticmethod
    def analyze_brightness(frame: np.ndarray) -> float:
        """
        Fast brightness analysis (1-2ms).
        Returns brightness in [0, 1] scale.

        Args:
            frame: Input BGR frame

        Returns:
            Brightness value between 0 (dark) and 1 (bright)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return np.mean(gray) / 255.0

    @staticmethod
    def adaptive_enhance(
        frame: np.ndarray,
        brightness_threshold: float = 0.4,
        force_enhance: bool = False
    ) -> Tuple[np.ndarray, bool, float]:
        """
        Conditionally enhance frame based on brightness analysis.

        This method enables intelligent frame enhancement that activates only
        when needed (low-light conditions), avoiding the 60-100ms cost on
        well-lit frames while still improving accuracy in challenging lighting.

        Args:
            frame: Input BGR frame
            brightness_threshold: Threshold below which enhancement is applied (0-1)
                                 Default 0.4 means frames darker than 40% will be enhanced
            force_enhance: If True, skip brightness check and always enhance

        Returns:
            Tuple of (enhanced_frame, was_enhanced, brightness_value)
            - enhanced_frame: The processed frame (enhanced if needed, original otherwise)
            - was_enhanced: Boolean indicating if enhancement was applied
            - brightness_value: The measured brightness (0-1 scale)
        """
        brightness = FrameEnhancer.analyze_brightness(frame)

        if force_enhance or brightness < brightness_threshold:
            # Low-light detected - apply enhancement
            enhanced = FrameEnhancer.enhance(frame)
            return enhanced, True, brightness
        else:
            # Well-lit - skip enhancement to save processing time
            return frame, False, brightness


class TemporalSmoother:
    """Smooth detections across frames"""
    
    def __init__(self, window_size: int = 10, alpha: float = 0.3):
        self.window_size = window_size
        self.alpha = alpha
        self.count_history = deque(maxlen=window_size)
        self.density_history = deque(maxlen=window_size)
    
    def smooth_count(self, current_count: int) -> int:
        """Smooth count using max-jump guard + IQR outlier removal + EMA"""
        # Max-jump guard: clamp frame-to-frame change to ±30% (min ±5)
        # Catches upstream spikes from PET/fusion before they enter history
        if len(self.count_history) >= 3:
            prev = self.count_history[-1]
            max_delta = max(5, int(prev * 0.3))
            current_count = max(prev - max_delta, min(prev + max_delta, current_count))

        self.count_history.append(current_count)

        if len(self.count_history) < 3:
            return current_count

        # Remove outliers
        counts = list(self.count_history)
        q1, q3 = np.percentile(counts, [25, 75])
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        filtered = [c for c in counts if lower <= c <= upper]
        
        if not filtered:
            return current_count
        
        # EMA
        ema = filtered[0]
        for c in filtered[1:]:
            ema = self.alpha * c + (1 - self.alpha) * ema
        
        return int(round(ema))
    
    def smooth_density(self, current_density: np.ndarray) -> np.ndarray:
        """Smooth density map"""
        self.density_history.append(current_density.copy())
        
        if len(self.density_history) < 3:
            return current_density
        
        weights = np.linspace(0.5, 1.0, len(self.density_history))
        weights /= weights.sum()
        
        smoothed = np.zeros_like(current_density)
        for w, density in zip(weights, self.density_history):
            smoothed += w * density
        
        return smoothed
