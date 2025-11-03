# Calibration Guide / Guide de Calibration

[English](#english) | [Français](#français)

---

## English

# Complete Table Calibration Guide

This guide explains how to calibrate your poker table for optimal detection and automation.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Understanding Calibration](#understanding-calibration)
3. [Step-by-Step Calibration Process](#step-by-step-calibration-process)
4. [Platform-Specific Instructions](#platform-specific-instructions)
5. [PokerStars Specific Configuration](#pokerstars-specific-configuration)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)

## Prerequisites

Before starting calibration, ensure you have:

1. **Installed Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Set Up Assets**
   ```bash
   python setup_assets.py
   ```

3. **Poker Client Running**
   - Open your poker client (e.g., PokerStars)
   - Join or open a table
   - Make sure the table is visible on screen

## Understanding Calibration

Calibration is the process of teaching the system to recognize and interact with your poker table. It involves:

- **Window Detection**: Finding the poker table window on your screen
- **Table Layout**: Identifying regions for cards, chips, buttons, etc.
- **Feature Extraction**: Creating reference points for table recognition
- **Region Mapping**: Defining where to look for game information

## Step-by-Step Calibration Process

### Step 1: Prepare Your Table

1. Open your poker client
2. Join a table with the game type you want to play (e.g., Hold'em No Limit 9-player)
3. Make sure the table is fully visible and not overlapped by other windows
4. Note the exact window title (shown in the title bar)

**Example Window Titles:**
- PokerStars: `"No Limit Hold'em $0.01/$0.02 - Table 'Alpha' - Seat 5"`
- 888poker: `"NL Hold'em - $1/$2 - Table #123456"`
- GGPoker: `"NLHE 9-max - $0.25/$0.50"`

### Step 2: Run the Profile Wizard

#### Method 1: Using Window Title (Recommended)

```bash
python -m holdem.cli.profile_wizard \
  --window-title "No Limit Hold'em" \
  --seats 9 \
  --out assets/table_profiles/pokerstars_nlhe_9max.json
```

**Tips:**
- Use `--seats 9` for 9-max tables (default) or `--seats 6` for 6-max tables
- Use a partial window title that will match your tables
- The system performs case-insensitive matching
- Shorter partial titles work better (e.g., "Hold'em" instead of full title)

#### Method 2: Using Screen Region (Fallback)

If window detection fails, you can specify the exact screen coordinates:

```bash
python -m holdem.cli.profile_wizard \
  --region 100 100 1200 800 \
  --seats 9 \
  --out assets/table_profiles/my_table.json
```

Where the numbers are: `X Y Width Height`

**How to find coordinates:**
- On macOS: Use Screenshot.app (Cmd+Shift+4) - shows coordinates
- On Windows: Use Snipping Tool or built-in tools
- On Linux: Use GNOME Screenshot or similar tools

**Helper Script for macOS:**
Use the included helper script to list all available windows:
```bash
# List all windows
python list_windows.py

# Filter by poker-related windows only
python list_windows.py --filter "poker"
python list_windows.py --filter "stars"
```
This will show you exact window titles and owner names to use with the profile wizard.

### Step 3: Verify Profile Creation

After running the wizard, you should see:

```
✓ Screenshot captured: (height, width, channels)
✓ Running calibration...
✓ Calibration complete (automated regions)
✓ Profile saved to: assets/table_profiles/pokerstars_nlhe_9max.json
```

The wizard creates several files:
- `pokerstars_nlhe_9max.json` - Main profile configuration
- `pokerstars_nlhe_9max_reference.npy` - Reference image for table detection
- `pokerstars_nlhe_9max_descriptors.npy` - Feature descriptors for matching

### Step 4: Test Your Profile

Test the profile in dry-run mode to ensure it works:

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars_nlhe_9max.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 --min-iters 100
```

**Note:** You need to train a blueprint policy first. See the main README for training instructions.

## Platform-Specific Instructions

### macOS

#### Required Permissions

macOS requires special permissions for screen capture and window control:

1. **Screen Recording Permission**
   - Open System Preferences → Security & Privacy → Privacy
   - Select "Screen Recording" from the left sidebar
   - Add your Terminal.app or IDE to the list
   - Restart Terminal/IDE after granting permission

2. **Accessibility Permission** (for auto-play)
   - Open System Preferences → Security & Privacy → Privacy
   - Select "Accessibility" from the left sidebar
   - Add your Terminal.app or IDE to the list
   - Restart Terminal/IDE after granting permission

#### Window Detection on macOS

The system uses two methods to find windows on macOS:

1. **Quartz (Primary)** - Native macOS window management
   - More reliable
   - Better performance
   - Automatically installed with `pyobjc-framework-Quartz`

2. **pygetwindow (Fallback)** - Cross-platform library
   - Used if Quartz is not available
   - May be less reliable on macOS

#### Common macOS Issues

**Problem:** "Window not found" error
- **Solution 1:** Grant Screen Recording permissions (see above)
- **Solution 2:** Use the exact window title from the title bar
- **Solution 3:** Use `--region` with exact coordinates instead

**Problem:** "AppleScript error -10003"
- **Cause:** Missing Accessibility permissions
- **Solution:** Add Terminal/IDE to Accessibility in System Preferences

### Windows

Windows uses `pywinauto` for native window management. No special permissions required.

```bash
python -m holdem.cli.profile_wizard \
  --window-title "PokerStars" \
  --out assets/table_profiles/pokerstars_windows.json
```

### Linux

Linux uses `pygetwindow` with X11. Make sure your display server is properly configured.

```bash
python -m holdem.cli.profile_wizard \
  --window-title "PokerStars" \
  --out assets/table_profiles/pokerstars_linux.json
```

## PokerStars Specific Configuration

### For PokerStars on macOS (9-Player No Limit Hold'em)

PokerStars tables often have complex window titles that change with each table. Here's the recommended approach:

#### Option 1: Use Application Owner Name (Recommended)

Edit your profile JSON file and add the `owner_name` field:

```json
{
  "window_title": "Hold'em",
  "owner_name": "PokerStars",
  "screen_region": null,
  ...
}
```

This tells the system to find windows owned by the PokerStars application, even if the exact title doesn't match.

#### Option 2: Use a Pre-Configured Profile Template

We provide a template for PokerStars 9-player tables:

```bash
# Copy the template
cp assets/table_profiles/pokerstars_nlhe_9max_template.json \
   assets/table_profiles/my_pokerstars.json

# Edit the screen_region if needed
nano assets/table_profiles/my_pokerstars.json
```

Then capture a reference screenshot:

```bash
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --seats 9 \
  --out assets/table_profiles/my_pokerstars.json
```

#### Option 3: Manual Region Configuration

If window detection fails, manually specify the region:

1. Open PokerStars and position the table window
2. Take a screenshot and note the coordinates
3. Create profile with exact coordinates:

```bash
python -m holdem.cli.profile_wizard \
  --region X Y WIDTH HEIGHT \
  --seats 9 \
  --out assets/table_profiles/pokerstars_manual.json
```

Replace X, Y, WIDTH, HEIGHT with your actual coordinates.

### PokerStars Table Layout (9-Player)

For 9-player tables, the typical layout is:
- **Player positions**: 0-8 in clockwise order
- **Button position**: Rotates around the table
- **Community cards**: Center top area
- **Pot display**: Center of table
- **Action buttons**: Bottom center

The calibration wizard automatically creates regions for these areas based on standard 9-player layouts.

## Troubleshooting

### Profile Creation Issues

**Problem:** "Failed to capture screenshot"
- Verify the window title is correct
- Check that the poker client is running and visible
- Grant necessary permissions (especially on macOS)
- Try using `--region` instead of `--window-title`

**Problem:** "Window not found in window list"
- The window title might contain special characters
- Try a shorter, partial title match
- Use the `owner_name` approach for PokerStars
- As a fallback, use manual region specification

### Table Detection Issues

**Problem:** Table not detected during play
- The reference image might not match current table appearance
- Re-run calibration with the current table theme/layout
- Ensure table is not resized or moved after calibration
- Check that table features (cards, buttons) are visible

**Problem:** "Not enough features detected"
- Table appearance has changed (different theme, lighting)
- Re-calibrate with current table appearance
- Ensure table window is not partially obscured
- Try using a different feature detection method (ORB vs AKAZE)

### Permission Issues (macOS)

**Problem:** Screen recording permission denied
1. Go to System Preferences → Security & Privacy → Privacy
2. Select "Screen Recording"
3. Add your Terminal or Python IDE
4. Restart the terminal/IDE
5. Run calibration again

## Advanced Configuration

### Manual Profile Editing

You can manually edit the JSON profile file to fine-tune regions:

```json
{
  "window_title": "Hold'em",
  "owner_name": "PokerStars",
  "screen_region": [100, 100, 1200, 800],
  "hero_position": 0,
  "card_regions": [
    {
      "x": 400,
      "y": 300,
      "width": 400,
      "height": 100
    }
  ],
  "player_regions": [
    {
      "position": 0,
      "name_region": {"x": 500, "y": 200, "width": 120, "height": 25},
      "stack_region": {"x": 500, "y": 225, "width": 120, "height": 25},
      "card_region": {"x": 480, "y": 250, "width": 100, "height": 80}
    }
  ],
  "pot_region": {
    "x": 450,
    "y": 250,
    "width": 200,
    "height": 100
  },
  "button_regions": {
    "fold": {"x": 300, "y": 700, "width": 120, "height": 50},
    "call": {"x": 450, "y": 700, "width": 120, "height": 50},
    "raise": {"x": 600, "y": 700, "width": 120, "height": 50}
  }
}
```

#### Setting Hero Position

The `hero_position` field tells the system which player is you (the "hero"). This is essential for the bot to detect your hole cards during PREFLOP play.

**Important:** Set `hero_position` to the index of your seat in the `player_regions` array.

For example:
- If you're sitting in position 0 (usually bottom-left in 9-max layouts): `"hero_position": 0`
- If you're in position 4 (usually top-center): `"hero_position": 4`
- Position numbering typically goes clockwise from bottom-left (0, 1, 2, ..., 8 for 9-max)

**Why is this needed?**
- The system needs to see your hole cards to make decisions during PREFLOP
- Only the hero's cards are visible on screen; opponent cards are face-down
- Without setting `hero_position`, the bot won't detect your cards and will remain stuck at PREFLOP

**Example for 9-max PokerStars:**
```json
{
  "hero_position": 0,
  "player_regions": [
    {
      "position": 0,
      "name": "Seat 1 (Bottom Left - Your Seat)",
      "card_region": {"x": 130, "y": 700, "width": 100, "height": 80}
    },
    ...
  ]
}
```

### Using Different Feature Detectors

The system supports two feature detection methods:

- **ORB** (default): Faster, works well for most tables
- **AKAZE**: More accurate, slower, better for complex layouts

Specify in your code when creating TableDetector:

```python
from holdem.vision.detect_table import TableDetector
from holdem.vision.calibrate import TableProfile

profile = TableProfile.load("assets/table_profiles/my_table.json")
detector = TableDetector(profile, method="akaze")  # or "orb"
```

### Creating Multiple Profiles

You can create different profiles for different table types or poker rooms:

```bash
# PokerStars cash game
python -m holdem.cli.profile_wizard \
  --window-title "Cash Game" \
  --out assets/table_profiles/ps_cash.json

# PokerStars tournament
python -m holdem.cli.profile_wizard \
  --window-title "Tournament" \
  --out assets/table_profiles/ps_tournament.json

# Different poker room
python -m holdem.cli.profile_wizard \
  --window-title "888poker" \
  --out assets/table_profiles/888poker.json
```

Then select the appropriate profile when running the bot.

## Next Steps

After successful calibration:

1. **Build Abstraction Buckets**
   ```bash
   python -m holdem.cli.build_buckets \
     --hands 500000 \
     --out assets/abstraction/precomputed_buckets.pkl
   ```

2. **Train Blueprint Strategy**
   ```bash
   python -m holdem.cli.train_blueprint \
     --iters 2500000 \
     --buckets assets/abstraction/precomputed_buckets.pkl \
     --logdir runs/blueprint
   ```

3. **Test in Dry-Run Mode**
   ```bash
   python -m holdem.cli.run_dry_run \
     --profile assets/table_profiles/pokerstars_nlhe_9max.json \
     --policy runs/blueprint/avg_policy.json
   ```

---

## Français

# Guide Complet de Calibration de Table

Ce guide explique comment calibrer votre table de poker pour une détection et une automatisation optimales.

## Table des Matières
1. [Prérequis](#prérequis)
2. [Comprendre la Calibration](#comprendre-la-calibration)
3. [Processus de Calibration Étape par Étape](#processus-de-calibration-étape-par-étape)
4. [Instructions Spécifiques par Plateforme](#instructions-spécifiques-par-plateforme)
5. [Configuration Spécifique PokerStars](#configuration-spécifique-pokerstars)
6. [Dépannage](#dépannage)
7. [Configuration Avancée](#configuration-avancée)

## Prérequis

Avant de commencer la calibration, assurez-vous d'avoir :

1. **Installé les Dépendances**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Configuré les Assets**
   ```bash
   python setup_assets.py
   ```

3. **Client Poker Lancé**
   - Ouvrez votre client poker (ex: PokerStars)
   - Rejoignez ou ouvrez une table
   - Assurez-vous que la table est visible à l'écran

## Comprendre la Calibration

La calibration est le processus d'apprentissage du système pour reconnaître et interagir avec votre table de poker. Elle implique :

- **Détection de Fenêtre** : Trouver la fenêtre de la table de poker sur votre écran
- **Disposition de Table** : Identifier les régions pour les cartes, jetons, boutons, etc.
- **Extraction de Caractéristiques** : Créer des points de référence pour la reconnaissance de table
- **Mappage de Régions** : Définir où chercher les informations du jeu

## Processus de Calibration Étape par Étape

### Étape 1 : Préparer Votre Table

1. Ouvrez votre client poker
2. Rejoignez une table avec le type de jeu que vous voulez jouer (ex: Hold'em No Limit 9 joueurs)
3. Assurez-vous que la table est entièrement visible et non recouverte par d'autres fenêtres
4. Notez le titre exact de la fenêtre (affiché dans la barre de titre)

**Exemples de Titres de Fenêtre :**
- PokerStars : `"No Limit Hold'em $0.01/$0.02 - Table 'Alpha' - Seat 5"`
- 888poker : `"NL Hold'em - $1/$2 - Table #123456"`
- GGPoker : `"NLHE 9-max - $0.25/$0.50"`

### Étape 2 : Exécuter l'Assistant de Profil

#### Méthode 1 : Utilisation du Titre de Fenêtre (Recommandé)

```bash
python -m holdem.cli.profile_wizard \
  --window-title "No Limit Hold'em" \
  --seats 9 \
  --out assets/table_profiles/pokerstars_nlhe_9max.json
```

**Conseils :**
- Utilisez `--seats 9` pour les tables 9-max (par défaut) ou `--seats 6` pour les tables 6-max
- Utilisez un titre de fenêtre partiel qui correspondra à vos tables
- Le système effectue une correspondance insensible à la casse
- Les titres partiels plus courts fonctionnent mieux (ex: "Hold'em" au lieu du titre complet)

#### Méthode 2 : Utilisation de la Région d'Écran (Secours)

Si la détection de fenêtre échoue, vous pouvez spécifier les coordonnées exactes de l'écran :

```bash
python -m holdem.cli.profile_wizard \
  --region 100 100 1200 800 \
  --seats 9 \
  --out assets/table_profiles/ma_table.json
```

Où les nombres sont : `X Y Largeur Hauteur`

**Comment trouver les coordonnées :**
- Sur macOS : Utilisez Screenshot.app (Cmd+Shift+4) - affiche les coordonnées
- Sur Windows : Utilisez l'Outil Capture d'écran ou outils intégrés
- Sur Linux : Utilisez Capture d'écran GNOME ou outils similaires

**Script d'Aide pour macOS :**
Utilisez le script d'aide inclus pour lister toutes les fenêtres disponibles :
```bash
# Lister toutes les fenêtres
python list_windows.py

# Filtrer par fenêtres liées au poker seulement
python list_windows.py --filter "poker"
python list_windows.py --filter "stars"
```
Cela vous montrera les titres exacts des fenêtres et les noms des propriétaires à utiliser avec l'assistant de profil.

### Étape 3 : Vérifier la Création du Profil

Après avoir exécuté l'assistant, vous devriez voir :

```
✓ Screenshot captured: (hauteur, largeur, canaux)
✓ Running calibration...
✓ Calibration complete (automated regions)
✓ Profile saved to: assets/table_profiles/pokerstars_nlhe_9max.json
```

L'assistant crée plusieurs fichiers :
- `pokerstars_nlhe_9max.json` - Configuration du profil principal
- `pokerstars_nlhe_9max_reference.npy` - Image de référence pour la détection de table
- `pokerstars_nlhe_9max_descriptors.npy` - Descripteurs de caractéristiques pour la correspondance

### Étape 4 : Tester Votre Profil

Testez le profil en mode dry-run pour vous assurer qu'il fonctionne :

```bash
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars_nlhe_9max.json \
  --policy runs/blueprint/avg_policy.json \
  --time-budget-ms 80 --min-iters 100
```

**Note :** Vous devez d'abord entraîner une stratégie blueprint. Voir le README principal pour les instructions d'entraînement.

## Instructions Spécifiques par Plateforme

### macOS

#### Permissions Requises

macOS nécessite des permissions spéciales pour la capture d'écran et le contrôle des fenêtres :

1. **Permission d'Enregistrement d'Écran**
   - Ouvrez Préférences Système → Sécurité et Confidentialité → Confidentialité
   - Sélectionnez "Enregistrement d'écran" dans la barre latérale gauche
   - Ajoutez votre Terminal.app ou IDE à la liste
   - Redémarrez Terminal/IDE après avoir accordé la permission

2. **Permission d'Accessibilité** (pour l'auto-play)
   - Ouvrez Préférences Système → Sécurité et Confidentialité → Confidentialité
   - Sélectionnez "Accessibilité" dans la barre latérale gauche
   - Ajoutez votre Terminal.app ou IDE à la liste
   - Redémarrez Terminal/IDE après avoir accordé la permission

#### Détection de Fenêtre sur macOS

Le système utilise deux méthodes pour trouver les fenêtres sur macOS :

1. **Quartz (Principal)** - Gestion native des fenêtres macOS
   - Plus fiable
   - Meilleures performances
   - Automatiquement installé avec `pyobjc-framework-Quartz`

2. **pygetwindow (Secours)** - Bibliothèque multiplateforme
   - Utilisé si Quartz n'est pas disponible
   - Peut être moins fiable sur macOS

#### Problèmes Courants sur macOS

**Problème :** Erreur "Window not found"
- **Solution 1 :** Accordez les permissions d'Enregistrement d'écran (voir ci-dessus)
- **Solution 2 :** Utilisez le titre exact de la fenêtre de la barre de titre
- **Solution 3 :** Utilisez `--region` avec des coordonnées exactes à la place

**Problème :** "AppleScript error -10003"
- **Cause :** Permissions d'Accessibilité manquantes
- **Solution :** Ajoutez Terminal/IDE à Accessibilité dans Préférences Système

## Configuration Spécifique PokerStars

### Pour PokerStars sur macOS (No Limit Hold'em 9 Joueurs)

Les tables PokerStars ont souvent des titres de fenêtre complexes qui changent avec chaque table. Voici l'approche recommandée :

#### Option 1 : Utiliser le Nom du Propriétaire d'Application (Recommandé)

Modifiez votre fichier JSON de profil et ajoutez le champ `owner_name` :

```json
{
  "window_title": "Hold'em",
  "owner_name": "PokerStars",
  "screen_region": null,
  ...
}
```

Cela indique au système de trouver les fenêtres appartenant à l'application PokerStars, même si le titre exact ne correspond pas.

#### Option 2 : Utiliser un Modèle de Profil Pré-Configuré

Nous fournissons un modèle pour les tables PokerStars à 9 joueurs :

```bash
# Copiez le modèle
cp assets/table_profiles/pokerstars_nlhe_9max_template.json \
   assets/table_profiles/mon_pokerstars.json

# Modifiez screen_region si nécessaire
nano assets/table_profiles/mon_pokerstars.json
```

Ensuite, capturez une capture d'écran de référence :

```bash
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --seats 9 \
  --out assets/table_profiles/mon_pokerstars.json
```

#### Option 3 : Configuration Manuelle de la Région

Si la détection de fenêtre échoue, spécifiez manuellement la région :

1. Ouvrez PokerStars et positionnez la fenêtre de la table
2. Prenez une capture d'écran et notez les coordonnées
3. Créez un profil avec les coordonnées exactes :

```bash
python -m holdem.cli.profile_wizard \
  --region X Y LARGEUR HAUTEUR \
  --seats 9 \
  --out assets/table_profiles/pokerstars_manuel.json
```

Remplacez X, Y, LARGEUR, HAUTEUR par vos coordonnées réelles.

### Disposition de Table PokerStars (9 Joueurs)

Pour les tables à 9 joueurs, la disposition typique est :
- **Positions des joueurs** : 0-8 dans le sens horaire
- **Position du bouton** : Tourne autour de la table
- **Cartes communes** : Zone supérieure centrale
- **Affichage du pot** : Centre de la table
- **Boutons d'action** : Centre inférieur

L'assistant de calibration crée automatiquement des régions pour ces zones basées sur les dispositions standard à 9 joueurs.

## Dépannage

### Problèmes de Création de Profil

**Problème :** "Failed to capture screenshot"
- Vérifiez que le titre de la fenêtre est correct
- Vérifiez que le client poker est en cours d'exécution et visible
- Accordez les permissions nécessaires (surtout sur macOS)
- Essayez d'utiliser `--region` au lieu de `--window-title`

**Problème :** "Window not found in window list"
- Le titre de la fenêtre peut contenir des caractères spéciaux
- Essayez un titre partiel plus court
- Utilisez l'approche `owner_name` pour PokerStars
- En dernier recours, utilisez la spécification manuelle de région

### Problèmes de Détection de Table

**Problème :** Table non détectée pendant le jeu
- L'image de référence peut ne pas correspondre à l'apparence actuelle de la table
- Relancez la calibration avec le thème/disposition actuel de la table
- Assurez-vous que la table n'est pas redimensionnée ou déplacée après calibration
- Vérifiez que les caractéristiques de la table (cartes, boutons) sont visibles

**Problème :** "Not enough features detected"
- L'apparence de la table a changé (thème différent, éclairage)
- Recalibrez avec l'apparence actuelle de la table
- Assurez-vous que la fenêtre de la table n'est pas partiellement masquée
- Essayez d'utiliser une méthode de détection de caractéristiques différente (ORB vs AKAZE)

### Problèmes de Permissions (macOS)

**Problème :** Permission d'enregistrement d'écran refusée
1. Allez dans Préférences Système → Sécurité et Confidentialité → Confidentialité
2. Sélectionnez "Enregistrement d'écran"
3. Ajoutez votre Terminal ou IDE Python
4. Redémarrez le terminal/IDE
5. Relancez la calibration

## Configuration Avancée

### Édition Manuelle du Profil

Vous pouvez modifier manuellement le fichier JSON du profil pour affiner les régions :

```json
{
  "window_title": "Hold'em",
  "owner_name": "PokerStars",
  "screen_region": [100, 100, 1200, 800],
  "card_regions": [
    {
      "x": 400,
      "y": 300,
      "width": 400,
      "height": 100
    }
  ],
  "player_regions": [
    {
      "position": 0,
      "name_region": {"x": 500, "y": 200, "width": 120, "height": 25},
      "stack_region": {"x": 500, "y": 225, "width": 120, "height": 25},
      "card_region": {"x": 480, "y": 250, "width": 100, "height": 80}
    }
  ],
  "pot_region": {
    "x": 450,
    "y": 250,
    "width": 200,
    "height": 100
  },
  "button_regions": {
    "fold": {"x": 300, "y": 700, "width": 120, "height": 50},
    "call": {"x": 450, "y": 700, "width": 120, "height": 50},
    "raise": {"x": 600, "y": 700, "width": 120, "height": 50}
  }
}
```

## Prochaines Étapes

Après une calibration réussie :

1. **Construire les Buckets d'Abstraction**
   ```bash
   python -m holdem.cli.build_buckets \
     --hands 500000 \
     --out assets/abstraction/precomputed_buckets.pkl
   ```

2. **Entraîner la Stratégie Blueprint**
   ```bash
   python -m holdem.cli.train_blueprint \
     --iters 2500000 \
     --buckets assets/abstraction/precomputed_buckets.pkl \
     --logdir runs/blueprint
   ```

3. **Tester en Mode Dry-Run**
   ```bash
   python -m holdem.cli.run_dry_run \
     --profile assets/table_profiles/pokerstars_nlhe_9max.json \
     --policy runs/blueprint/avg_policy.json
   ```
