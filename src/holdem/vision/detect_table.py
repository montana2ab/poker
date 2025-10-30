"""Table detection using feature matching."""

import cv2
import numpy as np
from typing import Optional, Tuple
from holdem.vision.calibrate import TableProfile
from holdem.utils.logging import get_logger

logger = get_logger("vision.detect_table")


class TableDetector:
    """Detects and warps poker table using feature matching."""
    
    def __init__(self, profile: TableProfile, method: str = "orb"):
        self.profile = profile
        self.method = method.lower()
        
        if self.method == "orb":
            self.detector = cv2.ORB_create(nfeatures=1000)
        elif self.method == "akaze":
            self.detector = cv2.AKAZE_create()
        else:
            raise ValueError(f"Unknown detection method: {method}")
        
        # Compute reference features if not already done
        if profile.reference_image is not None and profile.descriptors is None:
            gray = cv2.cvtColor(profile.reference_image, cv2.COLOR_BGR2GRAY)
            profile.keypoints, profile.descriptors = self.detector.detectAndCompute(gray, None)
    
    def detect(self, screenshot: np.ndarray) -> Optional[np.ndarray]:
        """Detect table and return warped image."""
        if self.profile.reference_image is None or self.profile.descriptors is None:
            logger.warning("No reference image/descriptors in profile")
            return screenshot  # Return unwarped
        
        # Detect features in current screenshot
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        kp2, des2 = self.detector.detectAndCompute(gray, None)
        
        if des2 is None or len(kp2) < 4:
            logger.warning("Not enough features detected in screenshot")
            return screenshot
        
        # Match features
        try:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(self.profile.descriptors, des2, k=2)
            
            # Apply ratio test (Lowe's test)
            good_matches = []
            for m_n in matches:
                if len(m_n) == 2:
                    m, n = m_n
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)
            
            if len(good_matches) < 10:
                logger.warning(f"Not enough good matches: {len(good_matches)}")
                return screenshot
            
            # Find homography
            src_pts = np.float32([self.profile.keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
            
            if H is None:
                logger.warning("Failed to compute homography")
                return screenshot
            
            # Warp screenshot to match reference
            h, w = self.profile.reference_image.shape[:2]
            warped = cv2.warpPerspective(screenshot, H, (w, h))
            
            logger.debug(f"Table detected with {len(good_matches)} matches")
            return warped
            
        except Exception as e:
            logger.error(f"Error during table detection: {e}")
            return screenshot
    
    def get_transform(self, screenshot: np.ndarray) -> Optional[np.ndarray]:
        """Get homography transformation matrix."""
        if self.profile.reference_image is None or self.profile.descriptors is None:
            return None
        
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        kp2, des2 = self.detector.detectAndCompute(gray, None)
        
        if des2 is None or len(kp2) < 4:
            return None
        
        try:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            matches = bf.knnMatch(self.profile.descriptors, des2, k=2)
            
            good_matches = []
            for m_n in matches:
                if len(m_n) == 2:
                    m, n = m_n
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)
            
            if len(good_matches) < 10:
                return None
            
            src_pts = np.float32([self.profile.keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
            return H
            
        except Exception as e:
            logger.error(f"Error computing transform: {e}")
            return None
