"""Table detection using feature matching."""

import cv2
import numpy as np
import os
from pathlib import Path
from PIL import Image
from typing import Optional, Tuple
from holdem.vision.calibrate import TableProfile
from holdem.utils.logging import get_logger

logger = get_logger("vision.detect_table")


def _load_refs_from_paths(profile: TableProfile, profile_path: Optional[Path] = None):
    """
    Load reference image and descriptors from file paths.
    
    Handles:
    - reference_image as path (str) → loads as ndarray (BGR)
    - descriptors as path (str) → loads from .npy or .npz file
    - Converts relative paths to absolute using profile_path as base
    
    Args:
        profile: TableProfile to update
        profile_path: Optional path to the profile JSON file (for resolving relative paths)
    """
    # Determine base directory for resolving relative paths
    base_dir = profile_path.parent if profile_path else Path.cwd()
    
    # Load reference_image if it's a path
    ref_img = getattr(profile, "reference_image", None)
    if isinstance(ref_img, str):
        # Convert to absolute path if relative
        ref_path = Path(ref_img)
        if not ref_path.is_absolute():
            ref_path = base_dir / ref_path
        
        if ref_path.exists():
            try:
                # Try cv2 first (handles more formats)
                img = cv2.imread(str(ref_path))
                if img is None:
                    # Fallback to PIL
                    img = cv2.cvtColor(
                        np.array(Image.open(ref_path).convert("RGB")), 
                        cv2.COLOR_RGB2BGR
                    )
                profile.reference_image = img
                logger.info(f"Loaded reference image from {ref_path}")
            except Exception as e:
                logger.error(f"Failed to load reference image from {ref_path}: {e}")
                profile.reference_image = None
        else:
            logger.warning(f"Reference image path does not exist: {ref_path}")
            profile.reference_image = None
    
    # Load descriptors if it's a path
    desc_path_attr = getattr(profile, "descriptors", None)
    if isinstance(desc_path_attr, str):
        # Convert to absolute path if relative
        desc_path = Path(desc_path_attr)
        if not desc_path.is_absolute():
            desc_path = base_dir / desc_path
        
        if desc_path.exists():
            try:
                # Load .npz or .npy file
                z = np.load(str(desc_path))
                
                # Handle .npz files (dictionary-like)
                if isinstance(z, np.lib.npyio.NpzFile):
                    # Try common keys in order of preference
                    if "des" in z:
                        profile.descriptors = z["des"]
                        logger.info(f"Loaded descriptors from {desc_path} (key: 'des')")
                    elif "descriptors" in z:
                        profile.descriptors = z["descriptors"]
                        logger.info(f"Loaded descriptors from {desc_path} (key: 'descriptors')")
                    else:
                        # Use first array in file
                        first_key = list(z.keys())[0]
                        profile.descriptors = z[first_key]
                        logger.warning(f"Using first array from {desc_path} (key: '{first_key}')")
                else:
                    # .npy file (direct array)
                    profile.descriptors = z
                
                logger.info(f"Loaded descriptors from {desc_path}")
            except Exception as e:
                logger.error(f"Failed to load descriptors from {desc_path}: {e}")
                profile.descriptors = None
        else:
            logger.warning(f"Descriptors path does not exist: {desc_path}")
            profile.descriptors = None


class TableDetector:
    """Detects and warps poker table using feature matching."""
    
    def __init__(self, profile: TableProfile, method: str = "orb", profile_path: Optional[Path] = None):
        """
        Initialize table detector.
        
        Args:
            profile: TableProfile with reference image and descriptors
            method: Feature detection method ("orb" or "akaze")
            profile_path: Optional path to profile JSON (for resolving relative paths in references)
        """
        self.profile = profile
        self.method = method.lower()
        
        # Load references from paths if they are strings
        _load_refs_from_paths(profile, profile_path)
        
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
            logger.info("Computed reference descriptors from reference image")
        elif profile.reference_image is not None and profile.descriptors is not None and not profile.keypoints:
            # Descriptors loaded from file but keypoints missing - recompute keypoints
            gray = cv2.cvtColor(profile.reference_image, cv2.COLOR_BGR2GRAY)
            profile.keypoints, _ = self.detector.detectAndCompute(gray, None)
            logger.info("Computed keypoints from reference image (descriptors loaded from file)")
    
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
            
            # Check if matches is valid
            if matches is None or len(matches) == 0:
                logger.warning("No matches found")
                return screenshot
            
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
            
            # Validate homography quality before applying transformation
            if not self._is_homography_valid(H, dst_pts, src_pts, mask):
                logger.warning("Homography quality check failed - using original screenshot")
                return screenshot
            
            # Warp screenshot to match reference
            h, w = self.profile.reference_image.shape[:2]
            warped = cv2.warpPerspective(screenshot, H, (w, h))
            
            logger.debug(f"Table detected with {len(good_matches)} matches")
            return warped
            
        except Exception as e:
            logger.error(f"Error during table detection: {e}")
            return screenshot
    
    def _is_homography_valid(self, H: np.ndarray, src_pts: np.ndarray, 
                             dst_pts: np.ndarray, mask: Optional[np.ndarray] = None) -> bool:
        """
        Validate homography quality to avoid distorted transformations.
        
        Args:
            H: Homography matrix (3x3)
            src_pts: Source points used to compute H
            dst_pts: Destination points used to compute H
            mask: RANSAC inlier mask (optional)
        
        Returns:
            True if homography is reliable, False otherwise
        """
        if H is None:
            return False
        
        # Check 1: Determinant should not be too close to zero (non-singular matrix)
        det = np.linalg.det(H)
        if abs(det) < 1e-6:
            logger.debug(f"Homography rejected: singular matrix (det={det:.2e})")
            return False
        
        # Check 2: Condition number (ratio of largest to smallest singular value)
        # High condition number indicates ill-conditioned transformation
        try:
            _, s, _ = np.linalg.svd(H)
            if s[-1] == 0:
                logger.debug("Homography rejected: zero singular value")
                return False
            condition_number = s[0] / s[-1]
            if condition_number > 100:
                logger.debug(f"Homography rejected: poor condition number ({condition_number:.1f})")
                return False
        except Exception as e:
            logger.debug(f"Homography rejected: SVD failed ({e})")
            return False
        
        # Check 3: Reprojection error - transform source points and check distance to destination
        if src_pts is not None and dst_pts is not None and len(src_pts) > 0:
            try:
                # Use only inlier points if mask is available
                if mask is not None:
                    inlier_mask = mask.ravel() == 1
                    if not any(inlier_mask):
                        logger.debug("Homography rejected: no inliers")
                        return False
                    src_pts_to_check = src_pts[inlier_mask]
                    dst_pts_to_check = dst_pts[inlier_mask]
                else:
                    src_pts_to_check = src_pts
                    dst_pts_to_check = dst_pts
                
                # Transform source points using homography
                src_pts_2d = src_pts_to_check.reshape(-1, 2)
                src_pts_h = np.concatenate([src_pts_2d, np.ones((len(src_pts_2d), 1))], axis=1)
                transformed = (H @ src_pts_h.T).T
                
                # Convert from homogeneous coordinates
                transformed[:, 0] /= transformed[:, 2]
                transformed[:, 1] /= transformed[:, 2]
                
                # Calculate reprojection error
                dst_pts_2d = dst_pts_to_check.reshape(-1, 2)
                errors = np.linalg.norm(transformed[:, :2] - dst_pts_2d, axis=1)
                mean_error = np.mean(errors)
                max_error = np.max(errors)
                
                # Reject if average error is too high (indicates poor fit)
                if mean_error > 10.0:
                    logger.debug(f"Homography rejected: high mean reprojection error ({mean_error:.2f} px)")
                    return False
                
                # Also check max error to catch outliers
                if max_error > 50.0:
                    logger.debug(f"Homography rejected: high max reprojection error ({max_error:.2f} px)")
                    return False
                
                logger.debug(f"Homography validated: mean_error={mean_error:.2f}px, "
                           f"max_error={max_error:.2f}px, condition={condition_number:.1f}")
                
            except Exception as e:
                logger.debug(f"Homography rejected: reprojection check failed ({e})")
                return False
        
        return True
    
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
            
            # Check if matches is valid
            if matches is None or len(matches) == 0:
                logger.warning("No matches found in get_transform")
                return None
            
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
            
            # Validate homography before returning
            if H is not None and not self._is_homography_valid(H, dst_pts, src_pts, mask):
                logger.debug("get_transform: homography validation failed")
                return None
            
            return H
            
        except Exception as e:
            logger.error(f"Error computing transform: {e}")
            return None
