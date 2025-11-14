import easyocr

# 'en' pour HUD PokerStars (lettres + chiffres)
reader = easyocr.Reader(['en'])

img_path = 'debug_ocr/SIMPLE.png'  # ou un crop de ta table

results = reader.readtext(img_path, detail=1)

for bbox, text, score in results:
    print(f"{text}  (score={score:.3f})")