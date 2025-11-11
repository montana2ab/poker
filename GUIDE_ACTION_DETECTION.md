# Guide: Action Detection and Real-Time Overlay

## Vue d'ensemble

Cette fonctionnalité permet de capturer de façon robuste et en temps réel toutes les informations de table, incluant:

✅ **Informations déjà disponibles:**
- Noms des joueurs (OCR)
- Montants des stacks
- Pot (montant au centre)
- Cartes du board (flop/turn/river)
- Cartes du héros

🆕 **Nouvelles fonctionnalités:**
- **Actions des joueurs**: CALL, CHECK, BET, RAISE, FOLD, ALL-IN
- **Détection du bouton dealer**: Pour calculer les positions (BTN/SB/BB/UTG/MP/CO)
- **Overlay visuel**: Affichage aligné des actions et mises sur les ROI des joueurs
- **Liaison robuste**: Maintien du lien nom↔action↔mise même quand le nom s'atténue

## Architecture

### 1. Détection des Actions

**Fichier**: `src/holdem/vision/ocr.py`

La méthode `detect_action()` détecte les actions via OCR avec:
- Reconnaissance robuste des mots-clés (CALL, CHECK, BET, RAISE, FOLD, ALL-IN)
- Support des variations (CALLS, FOLDED, RAISES, etc.)
- Matching partiel pour gérer les erreurs OCR
- Normalisation du texte (majuscules, espaces)

```python
from holdem.vision.ocr import OCREngine

ocr = OCREngine()
action = ocr.detect_action(action_image)  # Returns "CALL", "RAISE", etc.
```

### 2. Détection du Bouton Dealer

**Fichier**: `src/holdem/vision/parse_state.py`

La méthode `_parse_button_position()` supporte deux modes:

**Mode 1: dealer_button_regions (recommandé)**
- Liste de régions, une par position de joueur
- Détecte quelle région contient le bouton
- Utilise plusieurs heuristiques:
  - Luminosité (boutons souvent clairs)
  - Contraste
  - OCR ("D", "DEALER", "BTN")

**Mode 2: dealer_button_region (legacy)**
- Une seule région
- OCR uniquement

### 3. État du Joueur Étendu

**Fichier**: `src/holdem/types.py`

`PlayerState` maintenant inclut:
```python
@dataclass
class PlayerState:
    name: str
    stack: float
    bet_this_round: float = 0.0
    folded: bool = False
    all_in: bool = False
    position: int = 0
    hole_cards: Optional[List[Card]] = None
    last_action: Optional[ActionType] = None  # 🆕 Nouvelle
```

### 4. Système d'Overlay

**Fichier**: `src/holdem/vision/overlay.py`

La classe `GameOverlay` gère l'affichage visuel:
- Affiche les actions alignées avec les noms des joueurs
- Utilise le centre de la `name_region` comme point d'ancrage
- Semi-transparent pour ne pas cacher les informations
- Code couleur par type d'action:
  - CALL: Vert
  - BET/RAISE: Rouge
  - CHECK: Bleu
  - FOLD: Gris
  - ALL-IN: Rouge vif

## Configuration du Profil

### Structure des Régions Joueur

Chaque `player_region` doit maintenant inclure (optionnel):

```json
{
  "position": 0,
  "name_region": {
    "x": 456,
    "y": 162,
    "width": 100,
    "height": 20
  },
  "stack_region": {
    "x": 456,
    "y": 192,
    "width": 100,
    "height": 20
  },
  "bet_region": {
    "x": 456,
    "y": 215,
    "width": 100,
    "height": 20
  },
  "action_region": {
    "x": 456,
    "y": 140,
    "width": 100,
    "height": 18
  },
  "card_region": {
    "x": 466,
    "y": 235,
    "width": 80,
    "height": 60
  }
}
```

**Nouveau**: `action_region` - Zone où apparaît le texte de l'action (ex: "CALLS", "RAISES")

### Configuration du Bouton Dealer

**Option 1: Régions multiples (recommandé)**

```json
{
  "dealer_button_regions": [
    {"x": 520, "y": 150, "width": 25, "height": 25},
    {"x": 420, "y": 270, "width": 25, "height": 25},
    {"x": 210, "y": 270, "width": 25, "height": 25},
    {"x": 110, "y": 150, "width": 25, "height": 25},
    {"x": 210, "y": 35, "width": 25, "height": 25},
    {"x": 420, "y": 35, "width": 25, "height": 25}
  ]
}
```

Une région par position de joueur, dans le même ordre que `player_regions`.

**Option 2: Région unique (legacy)**

```json
{
  "dealer_button_region": {
    "x": 250,
    "y": 150,
    "width": 100,
    "height": 100
  }
}
```

## Utilisation

### 1. Script de Démonstration

```bash
python demo_action_detection.py \
    --profile assets/table_profiles/pokerstars.json \
    --interval 1.0 \
    --save-images /tmp/overlay_demo \
    --max-captures 20
```

Options:
- `--profile`: Profil de table (requis)
- `--interval`: Intervalle entre captures en secondes (défaut: 1.0)
- `--save-images`: Répertoire pour sauvegarder les images avec overlay
- `--max-captures`: Nombre maximum de captures (0 = illimité)

### 2. Intégration dans le Code

```python
from pathlib import Path
from holdem.vision.screen import ScreenCapture
from holdem.vision.calibrate import TableProfile
from holdem.vision.detect_table import TableDetector, _load_refs_from_paths
from holdem.vision.cards import CardRecognizer
from holdem.vision.ocr import OCREngine
from holdem.vision.parse_state import StateParser
from holdem.vision.overlay import GameOverlay

# Charger le profil
profile = TableProfile.load(Path("assets/table_profiles/pokerstars.json"))
_load_refs_from_paths(profile, Path("assets/table_profiles/pokerstars.json"))

# Initialiser les composants
screen_capture = ScreenCapture()
table_detector = TableDetector(profile)
card_recognizer = CardRecognizer(
    templates_dir=Path("assets/templates"),
    hero_templates_dir=Path("assets/hero_templates"),
    method="template"
)
ocr_engine = OCREngine()
state_parser = StateParser(profile, card_recognizer, ocr_engine)
overlay_manager = GameOverlay(profile, alpha=0.7)

# Capturer et parser
screenshot = screen_capture.capture(profile.window_title, profile.owner_name)
warped = table_detector.detect_and_warp(screenshot)
state = state_parser.parse(warped)

# Afficher les informations
if state:
    print(f"Street: {state.street.name}")
    print(f"Pot: ${state.pot:.2f}")
    print(f"Button: Position {state.button_position}")
    
    for player in state.players:
        if player.last_action:
            print(f"{player.name}: {player.last_action.value.upper()}")
    
    # Créer l'overlay
    overlay_img = overlay_manager.draw_state(warped, state)
```

## Gestion de l'Atténuation des Noms

### Problème

Pendant les animations d'action, le nom du joueur peut s'atténuer ou disparaître temporairement. Comment maintenir la liaison nom↔action↔mise?

### Solution Implémentée

1. **Ancrage sur les Régions**: Les régions (`name_region`, `action_region`, `bet_region`) sont définies en coordonnées fixes dans le profil. Même si le nom disparaît visuellement, la région reste valide.

2. **Overlay Aligné**: L'overlay utilise le **centre de la `name_region`** comme point d'ancrage. Les actions et mises s'affichent toujours au même endroit, relativement à ce centre.

3. **Détection Indépendante**: Chaque information (nom, action, mise) est détectée dans sa propre région. Si le nom s'atténue mais l'action apparaît, on capture quand même l'action.

4. **Cache de Position**: Le `position` du joueur dans `PlayerState` assure la correspondance. Même si le nom change ou disparaît temporairement, la position reste fixe.

### Exemple de Configuration Robuste

Pour un joueur à la position 0:

```json
{
  "position": 0,
  "name_region": {
    "x": 456,
    "y": 162,
    "width": 100,
    "height": 20
  },
  "action_region": {
    "x": 456,     // Même x que name_region
    "y": 140,     // Au-dessus du nom (y plus petit)
    "width": 100, // Même largeur
    "height": 18
  },
  "bet_region": {
    "x": 456,     // Même x que name_region
    "y": 215,     // En-dessous du nom et action
    "width": 100,
    "height": 20
  }
}
```

L'overlay affiche:
- Action à y=140 (au-dessus)
- Nom à y=162 (centre de référence)
- Mise à y=215 (en-dessous)

Tous alignés sur le même axe x, créant une colonne verticale cohérente.

## Tests

### Exécuter les Tests

```bash
python tests/test_action_detection.py
```

Les tests couvrent:
- ✅ Détection d'action (tous les types)
- ✅ Détection du bouton dealer
- ✅ État du joueur avec actions
- ✅ Fonctionnalité overlay
- ✅ Sérialisation du profil

### Test Manuel

1. **Configurer les régions**: Utilisez `profile_wizard` pour définir les régions
2. **Capturer des exemples**: Jouez quelques mains et capturez
3. **Vérifier l'overlay**: Exécutez `demo_action_detection.py`
4. **Ajuster**: Affinez les positions de `action_region` et `dealer_button_regions`

## Calibration des Régions

### Trouver les Bonnes Coordonnées

1. **Capturer une Image de Référence**
```bash
python -c "
from holdem.vision.screen import ScreenCapture
import cv2
sc = ScreenCapture()
img = sc.capture('Hold\\'em', 'PokerStars')
cv2.imwrite('reference.png', img)
print('Saved reference.png')
"
```

2. **Ouvrir dans un Éditeur d'Image**
- Utilisez GIMP, Photoshop, ou Paint
- Notez les coordonnées (x, y) et dimensions (width, height)
- Le coin supérieur gauche est (0, 0)

3. **Définir les Régions**

Pour l'action (généralement au-dessus du nom):
```json
"action_region": {
  "x": [x du nom],
  "y": [y du nom - 25],  // 25 pixels au-dessus
  "width": [même largeur que nom],
  "height": 18
}
```

Pour le bouton dealer (près du nom):
```json
"dealer_button_regions": [
  {
    "x": [x du nom - 30],  // 30 pixels à gauche
    "y": [y du nom + 5],   // Légèrement en-dessous
    "width": 25,
    "height": 25
  }
]
```

### Conseils de Calibration

1. **Action Region**:
   - Placez au-dessus ou à côté du nom
   - Assez large pour capturer le texte complet
   - Hauteur ~18-20 pixels pour le texte
   - Alignez sur le même x que `name_region`

2. **Dealer Button Regions**:
   - Une région par position de joueur
   - Taille ~25x25 pixels (taille typique du bouton)
   - Positionnez où le bouton "D" apparaît
   - Testez chaque position en tournant le bouton

3. **Validation**:
   - Utilisez `--save-images` pour vérifier visuellement
   - L'overlay montre si les détections sont correctes
   - Ajustez les régions si nécessaire

## Dépannage

### Actions Non Détectées

**Symptôme**: `No actions detected in this frame`

**Solutions**:
1. Vérifiez que `action_region` est défini dans le profil
2. Capturez une image et vérifiez que l'action est visible
3. Ajustez les coordonnées de `action_region`
4. Vérifiez les logs OCR pour voir le texte détecté
5. Testez avec différents backends OCR (PaddleOCR vs pytesseract)

### Bouton Dealer Incorrect

**Symptôme**: Bouton toujours à la position 0

**Solutions**:
1. Ajoutez `dealer_button_regions` au profil (un par joueur)
2. Vérifiez que les régions couvrent bien les boutons
3. Testez avec une image où le bouton est clairement visible
4. Vérifiez les scores de détection dans les logs
5. Ajustez le seuil de confiance si nécessaire

### Overlay Mal Aligné

**Symptôme**: Actions/mises affichées au mauvais endroit

**Solutions**:
1. Vérifiez que `name_region` est correct
2. L'overlay utilise le centre de `name_region` comme ancrage
3. Ajustez les coordonnées dans le profil
4. Sauvegardez les images avec `--save-images` pour déboguer visuellement

### Performance

**Symptôme**: Captures trop lentes

**Solutions**:
1. Augmentez `--interval` (ex: 2.0 secondes)
2. Réduisez la taille des régions
3. Utilisez PaddleOCR (plus rapide que pytesseract)
4. Désactivez le debug logging

## Limites et Améliorations Futures

### Limites Actuelles

1. **OCR Dépendant**: La qualité dépend de la résolution et de la clarté du texte
2. **Animations**: Les animations rapides peuvent causer des faux négatifs
3. **Templates Requis**: Les régions doivent être calibrées pour chaque client

### Améliorations Possibles

1. **Machine Learning**: Classifier d'actions basé sur des images
2. **Tracking Temporel**: Utiliser les frames précédentes pour confirmer les actions
3. **Templates de Bouton**: Template matching pour le bouton dealer
4. **Calibration Auto**: Détection automatique des régions

## Exemples de Profils

### PokerStars 6-max

```json
{
  "window_title": "Hold'em",
  "owner_name": "PokerStars",
  "player_regions": [
    {
      "position": 0,
      "name_region": {"x": 456, "y": 162, "width": 100, "height": 20},
      "stack_region": {"x": 456, "y": 192, "width": 100, "height": 20},
      "bet_region": {"x": 456, "y": 215, "width": 100, "height": 20},
      "action_region": {"x": 456, "y": 140, "width": 100, "height": 18},
      "card_region": {"x": 466, "y": 235, "width": 80, "height": 60}
    }
    // ... autres joueurs
  ],
  "dealer_button_regions": [
    {"x": 520, "y": 150, "width": 25, "height": 25},
    {"x": 420, "y": 270, "width": 25, "height": 25},
    {"x": 210, "y": 270, "width": 25, "height": 25},
    {"x": 110, "y": 150, "width": 25, "height": 25},
    {"x": 210, "y": 35, "width": 25, "height": 25},
    {"x": 420, "y": 35, "width": 25, "height": 25}
  ]
}
```

## Support

Pour toute question ou problème:
1. Vérifiez ce guide
2. Exécutez les tests: `python tests/test_action_detection.py`
3. Testez avec le script de démo: `python demo_action_detection.py`
4. Consultez les logs pour plus de détails
