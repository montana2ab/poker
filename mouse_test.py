import time
import pyautogui

print("Le test démarre dans 3 secondes, mets ta fenêtre de poker ou n'importe quelle fenêtre au bon endroit…")
time.sleep(3)

pyautogui.FAILSAFE = True

x, y = 500, 400  # à ajuster
print(f"Je clique à l'écran en ({x}, {y})")
pyautogui.moveTo(x, y, duration=0.5)
pyautogui.click()
print("Clic envoyé ✅")
