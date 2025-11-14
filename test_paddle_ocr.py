import time
from paddleocr import PaddleOCR

# petite image simple, par ex. un texte "TEST 123"
img_path = 'debug_ocr/SIMPLE.png'  # vérifie que le fichier existe bien

t0 = time.time()
print("▶ Init (ONNX)...")
ocr = PaddleOCR(
    lang='en',
    use_angle_cls=False,
    cpu_threads=1,
    use_onnx=True,   # ✅ ONNX activé
    det=True,
    rec=True
)
print(f"✅ Modèle (ONNX) chargé en {time.time() - t0:.2f} s")

t1 = time.time()
print("▶ OCR...")
result = ocr.ocr(img_path)
print(f"✅ OCR terminé en {time.time() - t1:.2f} s")

print("\n=== RÉSULTATS ===")
for line in result:
    for box, (text, score) in line:
        print(f"{text}  (score={score:.3f})")