#!/usr/bin/env python3
"""
Script de test manuel pour templates de cartes.
Usage exemple:
  python test_templates.py --templates-dir ./templates --image warped.png --card-region 130 700 160 100 --template Ah.png

Ce script :
 - charge une image "warped" de la table,
 - extrait la région de carte (x,y,w,h),
 - charge un template demandé,
 - prétraite (CLAHE + blur),
 - teste matchTemplate (0° et 180°),
 - affiche et sauvegarde les images et écrit le score.
"""
import cv2
import numpy as np
import argparse
from pathlib import Path

def preprocess_gray(img):
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    return gray

def match_and_report(card_crop, template, name_prefix="out"):
    # normalize sizes
    target_size = (70, 100)  # width, height used in CardRecognizer
    t_resized = cv2.resize(template, target_size)
    c_resized = cv2.resize(card_crop, target_size)
    # preprocess
    t_p = preprocess_gray(t_resized)
    c_p = preprocess_gray(c_resized)
    results = []
    for angle,name in [(0,"0"), (180,"180")]:
        if angle == 180:
            c_test = cv2.rotate(c_p, cv2.ROTATE_180)
        else:
            c_test = c_p
        res = cv2.matchTemplate(c_test, t_p, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        results.append((angle, float(max_val), c_test.copy(), t_p.copy()))
    # choose best
    best = max(results, key=lambda r: r[1])
    angle, score, c_best, t_best = best
    print(f"[{name_prefix}] Best match angle={angle} score={score:.4f}")
    # save visualization
    # >>> PATCH START: handle both gray and BGR inputs
    if len(c_resized.shape) == 2:
        # image en niveaux de gris → on convertit en BGR
        vis = cv2.cvtColor(c_resized, cv2.COLOR_GRAY2BGR)
    else:
        # déjà en BGR (3 canaux) → on garde tel quel
        vis = c_resized.copy()
    # >>> PATCH END
    tpl_vis = cv2.cvtColor(t_p, cv2.COLOR_GRAY2BGR)
    # combine side-by-side and annotate
    combined = np.hstack([vis, tpl_vis])
    cv2.putText(combined, f"score={score:.3f} angle={angle}", (5,15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,255), 1)
    out_path = Path(f"{name_prefix}_match_{score:.3f}.png")
    cv2.imwrite(str(out_path), combined)
    print(f"Saved visualization to {out_path}")
    return score, out_path

def main():
    parser = argparse.ArgumentParser(description="Test card templates manually.")
    parser.add_argument("--templates-dir", required=True, help="Path to templates folder")
    parser.add_argument("--image", required=True, help="Warped table image (PNG/JPG)")
    parser.add_argument("--card-region", nargs=4, type=int, required=True,
                        metavar=('x','y','w','h'), help="Card region to crop from image")
    parser.add_argument("--template", required=True, help="Template filename inside templates-dir to test (e.g. Ah.png)")
    parser.add_argument("--save-crop", action="store_true", help="Save the crop for inspection")
    args = parser.parse_args()

    templates_dir = Path(args.templates_dir)
    img_path = Path(args.image)
    template_path = templates_dir / args.template
    if not img_path.exists():
        raise SystemExit(f"Image not found: {img_path}")
    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")

    img = cv2.imread(str(img_path))
    x,y,w,h = args.card_region
    if y + h > img.shape[0] or x + w > img.shape[1] or w <= 0 or h <= 0:
        raise SystemExit("card-region out of bounds or zero size")

    card_crop = img[y:y+h, x:x+w]
    if args.save_crop:
        crop_path = Path("debug_card_crop.png")
        cv2.imwrite(str(crop_path), card_crop)
        print(f"Saved card crop to {crop_path}")

    template = cv2.imread(str(template_path))
    # Test full card match
    print("Testing full-card match...")
    score_full, vis_full = match_and_report(card_crop, template, name_prefix="fullcard")
    # Test coin ROI match (top-left corner)
    cw = int(w * 0.35)
    ch = int(h * 0.45)
    coin = card_crop[0:ch, 0:cw]  # top-left
    if coin.size > 0:
        print("Testing coin (top-left) ROI match...")
        score_coin, vis_coin = match_and_report(coin, template, name_prefix="coin_topleft")
    else:
        print("Coin ROI empty, skipping.")

    print("Done. Compare scores to your threshold (ex: 0.7-0.8). If scores are low:")
    print("- Inspect saved images, check orientation, borders, background.")
    print("- Try rotating template or crop by 180deg and retesting.")
    print("- Consider extracting dedicated coin templates (rank+suit only).")

if __name__ == "__main__":
    main()