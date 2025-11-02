# PokerStars Quick Setup Guide / Guide Rapide PokerStars

[English](#english) | [Français](#français)

---

## English

# Quick Setup for PokerStars (macOS)

This is a quick reference for setting up table detection with PokerStars on macOS, particularly for No Limit Hold'em 9-player tables.

## Prerequisites

1. **Install the software:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Grant macOS permissions:**
   - Go to System Preferences → Security & Privacy → Privacy
   - Add Terminal.app to "Screen Recording"
   - Restart Terminal

## Quick Calibration (Recommended Method)

### Step 1: Open PokerStars and Join a Table

Open PokerStars and join a No Limit Hold'em 9-max table. Make sure the table is fully visible.

### Step 2: Run Profile Wizard

```bash
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --out assets/table_profiles/pokerstars.json
```

**Why use `--owner-name "PokerStars"`?**
- PokerStars window titles change with each table
- Using the application owner name ensures detection works across all tables
- This is the most reliable method on macOS

### Step 3: Verify

The wizard should output:
```
✓ Found window by owner: 'PokerStars' (title: 'No Limit Hold'em...')
✓ Screenshot captured: (height, width, 3)
✓ Calibration complete
✓ Profile saved to: assets/table_profiles/pokerstars.json
```

## Alternative: Use the Template

If you have trouble with window detection, use our pre-configured template:

```bash
# Copy the template
cp assets/table_profiles/pokerstars_nlhe_9max_template.json \
   assets/table_profiles/pokerstars.json

# Edit to add your screen coordinates (if needed)
# Then capture a reference image
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --out assets/table_profiles/pokerstars.json
```

## Troubleshooting

### Find Available Windows

If you're not sure what window title to use, run the helper script:

```bash
# List all available windows on macOS
python list_windows.py

# Filter to show only PokerStars windows
python list_windows.py --filter "stars"
```

This will show you:
- Exact window titles
- Owner/application names
- Window coordinates and sizes

Use this information with the `--window-title` and `--owner-name` flags.

### "Window not found"

**Solution 1:** Grant Screen Recording permission
1. System Preferences → Security & Privacy → Privacy → Screen Recording
2. Add Terminal.app
3. Restart Terminal

**Solution 2:** Use exact window coordinates
1. Position PokerStars table window
2. Note the position and size
3. Use `--region` instead:
   ```bash
   python -m holdem.cli.profile_wizard \
     --region X Y WIDTH HEIGHT \
     --out assets/table_profiles/pokerstars.json
   ```

### "Not enough features detected"

This usually means the table appearance changed. Re-run calibration with the current table theme.

## Next Steps

After successful calibration, see the main README.md for:
1. Building abstraction buckets
2. Training blueprint strategy
3. Running in dry-run mode

📖 **For complete documentation, see [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md)**

---

## Français

# Configuration Rapide pour PokerStars (macOS)

Ceci est un guide de référence rapide pour configurer la détection de table avec PokerStars sur macOS, particulièrement pour les tables No Limit Hold'em à 9 joueurs.

## Prérequis

1. **Installer le logiciel :**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Accorder les permissions macOS :**
   - Allez dans Préférences Système → Sécurité et Confidentialité → Confidentialité
   - Ajoutez Terminal.app à "Enregistrement d'écran"
   - Redémarrez Terminal

## Calibration Rapide (Méthode Recommandée)

### Étape 1 : Ouvrir PokerStars et Rejoindre une Table

Ouvrez PokerStars et rejoignez une table No Limit Hold'em 9-max. Assurez-vous que la table est entièrement visible.

### Étape 2 : Exécuter l'Assistant de Profil

```bash
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --out assets/table_profiles/pokerstars.json
```

**Pourquoi utiliser `--owner-name "PokerStars"` ?**
- Les titres de fenêtre PokerStars changent avec chaque table
- L'utilisation du nom du propriétaire de l'application garantit que la détection fonctionne sur toutes les tables
- C'est la méthode la plus fiable sur macOS

### Étape 3 : Vérifier

L'assistant devrait afficher :
```
✓ Found window by owner: 'PokerStars' (title: 'No Limit Hold'em...')
✓ Screenshot captured: (hauteur, largeur, 3)
✓ Calibration complete
✓ Profile saved to: assets/table_profiles/pokerstars.json
```

## Alternative : Utiliser le Modèle

Si vous avez des difficultés avec la détection de fenêtre, utilisez notre modèle pré-configuré :

```bash
# Copier le modèle
cp assets/table_profiles/pokerstars_nlhe_9max_template.json \
   assets/table_profiles/pokerstars.json

# Modifier pour ajouter vos coordonnées d'écran (si nécessaire)
# Puis capturer une image de référence
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --out assets/table_profiles/pokerstars.json
```

## Dépannage

### Trouver les Fenêtres Disponibles

Si vous n'êtes pas sûr du titre de fenêtre à utiliser, exécutez le script d'aide :

```bash
# Lister toutes les fenêtres disponibles sur macOS
python list_windows.py

# Filtrer pour afficher uniquement les fenêtres PokerStars
python list_windows.py --filter "stars"
```

Cela vous montrera :
- Titres exacts des fenêtres
- Noms des propriétaires/applications
- Coordonnées et tailles des fenêtres

Utilisez ces informations avec les drapeaux `--window-title` et `--owner-name`.

### "Window not found" (Fenêtre non trouvée)

**Solution 1 :** Accorder la permission d'enregistrement d'écran
1. Préférences Système → Sécurité et Confidentialité → Confidentialité → Enregistrement d'écran
2. Ajouter Terminal.app
3. Redémarrer Terminal

**Solution 2 :** Utiliser les coordonnées exactes de la fenêtre
1. Positionner la fenêtre de table PokerStars
2. Noter la position et la taille
3. Utiliser `--region` à la place :
   ```bash
   python -m holdem.cli.profile_wizard \
     --region X Y LARGEUR HAUTEUR \
     --out assets/table_profiles/pokerstars.json
   ```

### "Not enough features detected" (Pas assez de caractéristiques détectées)

Cela signifie généralement que l'apparence de la table a changé. Relancez la calibration avec le thème actuel de la table.

## Prochaines Étapes

Après une calibration réussie, consultez le README.md principal pour :
1. Construire les buckets d'abstraction
2. Entraîner la stratégie blueprint
3. Exécuter en mode dry-run

📖 **Pour la documentation complète, voir [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md)**

---

## Common Commands / Commandes Courantes

### Full Setup / Configuration Complète

```bash
# 1. Calibrate / Calibrer
python -m holdem.cli.profile_wizard \
  --window-title "Hold'em" \
  --owner-name "PokerStars" \
  --out assets/table_profiles/pokerstars.json

# 2. Build buckets / Construire les buckets
python -m holdem.cli.build_buckets \
  --hands 500000 \
  --out assets/abstraction/precomputed_buckets.pkl

# 3. Train blueprint / Entraîner blueprint
python -m holdem.cli.train_blueprint \
  --iters 2500000 \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/blueprint

# 4. Test in dry-run / Tester en dry-run
python -m holdem.cli.run_dry_run \
  --profile assets/table_profiles/pokerstars.json \
  --policy runs/blueprint/avg_policy.json
```

## Support

For issues or questions / Pour les problèmes ou questions :
- See [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) for detailed troubleshooting
- Consultez [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md) pour le dépannage détaillé
- Check the main [README.md](README.md) for general documentation
- Consultez le [README.md](README.md) principal pour la documentation générale
