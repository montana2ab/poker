# Guide - Capture Automatique des Templates de Cartes

## Vue d'ensemble

Ce module permet de capturer automatiquement les templates de cartes pendant que vous jouez au poker. Le système :

1. **Surveille** la table pendant que vous jouez
2. **Détecte** automatiquement quand de nouvelles cartes apparaissent
3. **Capture** les images des cartes (board et hero)
4. **Sauvegarde** les templates pour utilisation ultérieure

## Avantages

✅ **Pas besoin de captures manuelles** - Le système fait tout automatiquement  
✅ **Qualité optimale** - Les templates sont capturés dans les conditions réelles de jeu  
✅ **Complet** - Capture les cartes hero ET board séparément  
✅ **Simple** - Jouez normalement, le système s'occupe du reste  

## Installation

Les modules sont déjà installés. Vous avez besoin de :
- Un profil de table configuré (`TableProfile`)
- Python avec les dépendances du projet

## Utilisation - 3 Étapes

### Étape 1 : Capturer les Templates

Lancez le module de capture automatique pendant que vous jouez :

```bash
# Lancer la capture (s'arrête avec Ctrl+C)
python -m holdem.cli.capture_templates --profile assets/table_profiles/pokerstars.json

# Ou avec durée limitée (30 minutes = 1800 secondes)
python -m holdem.cli.capture_templates \
    --profile assets/table_profiles/pokerstars.json \
    --duration 1800

# Capture toutes les 2 secondes (plus lent mais moins de doublons)
python -m holdem.cli.capture_templates \
    --profile assets/table_profiles/pokerstars.json \
    --interval 2.0
```

**Pendant la capture :**
- Jouez au poker normalement
- Le système capture automatiquement :
  - Vos cartes (hole cards) quand elles sont distribuées
  - Les cartes du board au flop, turn, river
- Jouez plusieurs mains pour capturer différentes cartes
- Appuyez sur Ctrl+C pour arrêter

**Fichiers sauvegardés :**
- Board : `assets/templates_captured/board/`
- Hero : `assets/templates_captured/hero/`

### Étape 2 : Organiser et Identifier les Templates

Après la capture, identifiez chaque carte :

```bash
# Organiser les cartes du board
python organize_captured_templates.py \
    --input assets/templates_captured/board \
    --output assets/templates

# Organiser les cartes hero
python organize_captured_templates.py \
    --input assets/templates_captured/hero \
    --output assets/hero_templates
```

**Le script va :**
1. Afficher chaque carte capturée
2. Vous demander d'identifier la carte (ex: "Ah", "Ks", "7d")
3. Renommer et sauvegarder avec le bon nom
4. Éviter les doublons

**Format d'identification :**
- Rang : `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `T`, `J`, `Q`, `K`, `A`
- Couleur : `h` (cœur), `d` (carreau), `c` (trèfle), `s` (pique)
- Exemples : `Ah` (As de cœur), `Ks` (Roi de pique), `7d` (7 de carreau)

### Étape 3 : Utiliser les Templates

Les templates sont maintenant prêts à être utilisés ! Ils sont dans :
- `assets/templates/` - Cartes du board
- `assets/hero_templates/` - Cartes hero

Configurez votre profil de table :

```json
{
  "hero_position": 0,
  "hero_templates_dir": "assets/hero_templates",
  ...
}
```

## Options Avancées

### Personnaliser les Répertoires de Sortie

```bash
python -m holdem.cli.capture_templates \
    --profile mon_profil.json \
    --board-output mes_templates/board \
    --hero-output mes_templates/hero
```

### Mode Non-Interactif

Pour organiser sans intervention (garde les noms de fichiers) :

```bash
python organize_captured_templates.py \
    --input templates_captured/board \
    --output templates \
    --no-interactive
```

### Écraser les Templates Existants

```bash
python organize_captured_templates.py \
    --input templates_captured/board \
    --output templates \
    --overwrite
```

## Conseils pour une Capture Optimale

### Avant de Commencer

1. **Configurez votre profil de table** avec les bonnes régions
2. **Testez** que les régions de cartes sont correctes
3. **Vérifiez** que `hero_position` est correctement défini

### Pendant la Capture

1. **Jouez plusieurs mains** pour voir différentes cartes
2. **Variez les situations** (preflop, flop, turn, river)
3. **Évitez les animations** - attendez que les cartes soient stables
4. **Bon éclairage** - assurez-vous que les cartes sont bien visibles
5. **Pas de superposition** - pas de fenêtres par-dessus le client poker

### Après la Capture

1. **Vérifiez la qualité** des images capturées
2. **Supprimez les doublons** ou images floues
3. **Gardez les meilleures** images pour chaque carte
4. **Testez** la reconnaissance avec vos nouveaux templates

## Dépannage

### "Table not detected"

➡️ Vérifiez que :
- Le client poker est visible à l'écran
- Le profil de table est correct
- La fenêtre n'est pas minimisée

### "No cards captured"

➡️ Vérifiez que :
- Les régions de cartes (`card_regions`) sont correctes
- Les cartes sont visibles (pas d'animation)
- L'intervalle n'est pas trop rapide

### Images floues ou de mauvaise qualité

➡️ Solutions :
- Augmentez l'intervalle (`--interval 2.0`)
- Attendez que les animations soient terminées
- Vérifiez la résolution de votre écran
- Ajustez les régions dans le profil

### Pas assez de cartes capturées

➡️ Solutions :
- Jouez plus de mains
- Laissez tourner plus longtemps
- Vérifiez les logs pour voir ce qui est détecté

## Exemple Complet - Session de Capture

```bash
# 1. Lancer la capture pour 1 heure
python -m holdem.cli.capture_templates \
    --profile assets/table_profiles/pokerstars.json \
    --duration 3600 \
    --interval 1.5

# Pendant ce temps : jouez au poker normalement
# Appuyez sur Ctrl+C si vous voulez arrêter avant

# 2. Organiser les cartes du board
python organize_captured_templates.py \
    --input assets/templates_captured/board \
    --output assets/templates

# Identifiez chaque carte affichée (Ah, Ks, etc.)

# 3. Organiser les cartes hero
python organize_captured_templates.py \
    --input assets/templates_captured/hero \
    --output assets/hero_templates

# Identifiez chaque carte affichée

# 4. Vérifier les résultats
ls -l assets/templates/
ls -l assets/hero_templates/

# 5. Tester la reconnaissance
python example_hero_templates.py
```

## Architecture Technique

### Modules Créés

1. **`src/holdem/vision/auto_capture.py`**
   - Classe `CardTemplateCapture` - Gère la capture automatique
   - Détection de nouvelles cartes
   - Validation de qualité d'image
   - Sauvegarde organisée

2. **`src/holdem/cli/capture_templates.py`**
   - Interface CLI pour lancer la capture
   - Configuration via arguments
   - Monitoring et statistiques

3. **`organize_captured_templates.py`**
   - Outil d'organisation et labeling
   - Interface interactive
   - Gestion des doublons

### Fonctionnement Interne

```
┌─────────────────────┐
│  Capture d'écran    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Détection de table │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Extraction régions │
│  - Board cards      │
│  - Hero cards       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Détection changem. │
│  (carte différente?)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Validation qualité │
│  - Taille OK?       │
│  - Contraste OK?    │
│  - Variance OK?     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Sauvegarde image   │
│  avec timestamp     │
└─────────────────────┘
```

## Progression

Le système affiche la progression en temps réel :

```
Capture #5: Board +2 (total: 12), Hero +1 (total: 8)
Overall progress: 19.2%
```

- **Board** : Cartes du board capturées
- **Hero** : Cartes hero capturées
- **Overall** : Progression totale (sur 104 cartes = 52 board + 52 hero)

## Prochaines Étapes

Après avoir capturé et organisé vos templates :

1. ✅ Configurez votre profil avec `hero_templates_dir`
2. ✅ Testez la reconnaissance avec les nouveaux templates
3. ✅ Ajustez si nécessaire (recapturez certaines cartes)
4. ✅ Utilisez le système normalement avec meilleure précision !

## Support

- Voir `CARD_RECOGNITION_FIX_SUMMARY.md` pour vue d'ensemble
- Voir `GUIDE_CORRECTION_CARTES.md` pour configuration générale
- Voir `example_hero_templates.py` pour exemples de code
