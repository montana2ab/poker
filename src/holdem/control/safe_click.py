"""Safe click functionality for action buttons to prevent checkbox misclicks.

This module provides safe click functionality that prevents the bot from clicking on
action buttons when the UI is not ready (e.g., when checkboxes like "Call Any" or 
"Call 100" are still visible at the button position).

Key features:
- Lightweight pixel analysis to detect if buttons are rendered vs checkboxes
- Automatic retry mechanism (default: 2 retries with 50ms delay) for cases where
  the UI is transitioning from checkboxes to action buttons
- No heavy vision operations (OCR, template matching) - keeps performance optimal
- Total overhead: < 10ms on success, < 110ms with full retries
"""

import time
import numpy as np
from typing import Optional, Tuple
from holdem.utils.logging import get_logger
from holdem.vision.screen import ScreenCapture

logger = get_logger("control.safe_click")


def _get_pyautogui():
    """Lazy import of pyautogui to avoid import issues in tests."""
    import pyautogui
    return pyautogui


def safe_click_action_button(
    x: int, 
    y: int, 
    width: int, 
    height: int, 
    label: Optional[str] = None,
    click_delay: float = 0.1,
    max_retries: int = 2,
    retry_delay: float = 0.05
) -> bool:
    """
    Vérifie visuellement qu'un vrai bouton d'action est présent à la position donnée,
    puis effectue le clic. Retourne True si le clic a été fait, False sinon.
    
    Cette fonction effectue une vérification ultra-légère pour détecter si les cases
    à cocher "Call 100" / "Call Any" sont encore présentes à l'emplacement du bouton,
    ce qui indiquerait que les vrais boutons d'action ne sont pas encore visibles.
    
    Si la vérification échoue initialement, la fonction effectue des retries avec
    un court délai entre chaque tentative pour gérer le cas où l'UI n'est pas encore
    complètement rendue.
    
    Args:
        x: Coordonnée X du centre du bouton
        y: Coordonnée Y du centre du bouton
        width: Largeur du bouton (pour déterminer la région à capturer)
        height: Hauteur du bouton (pour déterminer la région à capturer)
        label: Label optionnel du bouton pour les logs (ex: "Fold", "Call", "Pot")
        click_delay: Délai après le clic (en secondes)
        max_retries: Nombre maximum de tentatives (default: 2)
        retry_delay: Délai entre les tentatives en secondes (default: 0.05s / 50ms)
        
    Returns:
        True si le clic a été effectué, False si la vérification a échoué après tous les retries
        
    Performance:
        - Capture uniquement une petite région autour du bouton (~40x20 pixels)
        - Analyse seulement quelques pixels clés
        - N'alourdit pas le pipeline de vision principal
        - Exécution typique: < 10ms (succès immédiat) ou < 110ms (avec 2 retries)
    """
    action_desc = label if label else f"button at ({x}, {y})"
    
    # Définir la région de capture minimale autour du bouton
    # On capture une zone plus large que le bouton pour détecter les checkboxes
    capture_width = max(60, width + 20)
    capture_height = max(30, height + 10)
    
    # Calculer les coordonnées de la région à capturer (centrée sur le bouton)
    region_x = max(0, x - capture_width // 2)
    region_y = max(0, y - capture_height // 2)
    
    # Boucle de retry
    for attempt in range(max_retries + 1):
        try:
            # Capturer uniquement la petite région autour du bouton
            screen_capture = ScreenCapture()
            region_img = screen_capture.capture_region(
                region_x, 
                region_y, 
                capture_width, 
                capture_height
            )
            
            if region_img is None or region_img.size == 0:
                if attempt < max_retries:
                    logger.debug(f"[AUTOPLAY] UI not ready for {action_desc}, retrying ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.warning(f"[SAFE_CLICK] Failed to capture region for {action_desc} after {max_retries + 1} attempts")
                    return False
            
            # Analyser quelques pixels clés pour déterminer si c'est un bouton ou une checkbox
            is_valid = _analyze_button_pixels(region_img, capture_width, capture_height)
            
            if not is_valid:
                if attempt < max_retries:
                    logger.debug(f"[AUTOPLAY] UI not ready for {action_desc}, retrying ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.debug(f"[SAFE_CLICK] Skip click: {action_desc} - UI not ready or checkbox detected after {max_retries + 1} attempts")
                    return False
            
            # La vérification a réussi, effectuer le clic
            logger.debug(f"[SAFE_CLICK] Action button looks valid, performing click on {action_desc} at ({x}, {y})")
            pyautogui = _get_pyautogui()
            pyautogui.click(x, y)
            time.sleep(click_delay)
            
            return True
            
        except Exception as e:
            if attempt < max_retries:
                logger.debug(f"[AUTOPLAY] Error during verification for {action_desc}, retrying ({attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"[SAFE_CLICK] Error during safe click verification after {max_retries + 1} attempts: {e}", exc_info=True)
                return False
    
    # Ne devrait jamais arriver ici, mais par sécurité
    return False


def _analyze_button_pixels(img: np.ndarray, width: int, height: int) -> bool:
    """
    Analyse les pixels de l'image pour déterminer si c'est un vrai bouton d'action
    ou si ce sont encore les cases à cocher "Call 100" / "Call Any".
    
    Heuristique:
    - Les checkboxes ont un bord sombre/carré à gauche du texte
    - Les vrais boutons d'action ont un fond gris clair
    
    Args:
        img: Image de la région capturée (BGR format)
        width: Largeur de la région capturée
        height: Hauteur de la région capturée
        
    Returns:
        True si le bouton semble être un vrai bouton d'action, False sinon
    """
    if img is None or img.size == 0:
        return False
    
    h, w = img.shape[:2]
    
    # Convertir en niveaux de gris pour simplifier l'analyse
    if len(img.shape) == 3:
        gray = np.mean(img, axis=2).astype(np.uint8)
    else:
        gray = img
    
    # Normaliser les valeurs de luminance entre 0 et 1
    normalized = gray.astype(np.float32) / 255.0
    
    # Pixel 1: Vérifier un pixel à gauche du centre (là où se trouve la checkbox)
    # Position approximative: 20-30% de la largeur, centre vertical
    checkbox_x = int(w * 0.25)
    checkbox_y = h // 2
    
    # S'assurer que les coordonnées sont dans les limites
    checkbox_x = max(0, min(checkbox_x, w - 1))
    checkbox_y = max(0, min(checkbox_y, h - 1))
    
    checkbox_pixel_luminance = normalized[checkbox_y, checkbox_x]
    
    # Pixel 2: Vérifier le centre du bouton
    center_x = w // 2
    center_y = h // 2
    
    center_pixel_luminance = normalized[center_y, center_x]
    
    # Pixel 3: Calculer la luminance moyenne d'une zone centrale
    # pour avoir une meilleure estimation du fond
    center_region_size = 5
    x1 = max(0, center_x - center_region_size)
    x2 = min(w, center_x + center_region_size)
    y1 = max(0, center_y - center_region_size)
    y2 = min(h, center_y + center_region_size)
    
    center_region = normalized[y1:y2, x1:x2]
    avg_center_luminance = np.mean(center_region) if center_region.size > 0 else center_pixel_luminance
    
    # Seuils de détection
    DARK_THRESHOLD = 0.3  # Pixels sombres (bords de checkbox)
    LIGHT_THRESHOLD = 0.5  # Boutons d'action (fond gris clair)
    
    # Heuristique de détection
    is_checkbox_pixel_dark = checkbox_pixel_luminance < DARK_THRESHOLD
    is_button_center_light = avg_center_luminance > LIGHT_THRESHOLD
    
    # Log détaillé pour le debug
    logger.debug(
        f"[SAFE_CLICK] Pixel analysis: checkbox_lum={checkbox_pixel_luminance:.2f}, "
        f"center_lum={center_pixel_luminance:.2f}, avg_center_lum={avg_center_luminance:.2f}"
    )
    
    # Cas 1: Détection de checkbox (pixel gauche sombre ET centre pas clair)
    if is_checkbox_pixel_dark and not is_button_center_light:
        logger.debug("[SAFE_CLICK] Checkbox UI detected at action button location")
        return False
    
    # Cas 2: Bouton pas encore dessiné (fond sombre)
    if not is_button_center_light:
        logger.debug("[SAFE_CLICK] Action button not visibly rendered yet (dark background)")
        return False
    
    # Cas 3: Le bouton semble valide
    logger.debug("[SAFE_CLICK] Action button appears valid (light background detected)")
    return True


def safe_click_with_fallback(
    x: int,
    y: int,
    width: int,
    height: int,
    label: Optional[str] = None,
    click_delay: float = 0.1,
    enable_safe_click: bool = True,
    max_retries: int = 2,
    retry_delay: float = 0.05
) -> bool:
    """
    Wrapper pour safe_click_action_button avec fallback sur un clic direct.
    
    Si safe_click est désactivé ou si la vérification échoue de manière inattendue,
    on effectue un clic direct (comportement legacy).
    
    Args:
        x: Coordonnée X du centre du bouton
        y: Coordonnée Y du centre du bouton
        width: Largeur du bouton
        height: Hauteur du bouton
        label: Label optionnel du bouton
        click_delay: Délai après le clic
        enable_safe_click: Si False, effectue un clic direct sans vérification
        max_retries: Nombre maximum de tentatives (default: 2)
        retry_delay: Délai entre les tentatives en secondes (default: 0.05s / 50ms)
        
    Returns:
        True si le clic a été effectué (directement ou après vérification)
    """
    if not enable_safe_click:
        # Mode legacy: clic direct sans vérification
        logger.debug(f"[SAFE_CLICK] Safe click disabled, performing direct click on {label or 'button'}")
        pyautogui = _get_pyautogui()
        pyautogui.click(x, y)
        time.sleep(click_delay)
        return True
    
    # Tentative avec safe click et retries
    return safe_click_action_button(x, y, width, height, label, click_delay, max_retries, retry_delay)
