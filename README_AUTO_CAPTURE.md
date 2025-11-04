# 🎯 Capture Automatique de Templates - Démarrage Rapide

## 📋 En Bref

Ce système capture automatiquement les images des cartes pendant que vous jouez au poker, puis vous aide à les organiser en templates réutilisables.

## 🚀 Utilisation Rapide

### 1️⃣ Capturer les Cartes (pendant que vous jouez)

```bash
python capture_templates.py --profile assets/table_profiles/pokerstars.json
```

**Jouez normalement au poker. Le système capture automatiquement les cartes !**

Appuyez sur `Ctrl+C` pour arrêter.

### 2️⃣ Identifier les Cartes Capturées

```bash
# Pour les cartes du board
python organize_captured_templates.py \
    --input assets/templates_captured/board \
    --output assets/templates

# Pour vos cartes (hero)
python organize_captured_templates.py \
    --input assets/templates_captured/hero \
    --output assets/hero_templates
```

Le script affiche chaque carte et vous demande de l'identifier (ex: `Ah`, `Ks`, `7d`).

### 3️⃣ Utiliser les Templates

Les templates sont maintenant dans :
- `assets/templates/` - Cartes du board
- `assets/hero_templates/` - Vos cartes

Configurez votre profil :

```json
{
  "hero_position": 0,
  "hero_templates_dir": "assets/hero_templates"
}
```

C'est tout ! 🎉

## 📖 Documentation Complète

- **[GUIDE_AUTO_CAPTURE.md](GUIDE_AUTO_CAPTURE.md)** - Guide complet en français
- **[GUIDE_CORRECTION_CARTES.md](GUIDE_CORRECTION_CARTES.md)** - Configuration générale
- **[CARD_RECOGNITION_FIX_SUMMARY.md](CARD_RECOGNITION_FIX_SUMMARY.md)** - Vue d'ensemble technique

## 💡 Conseils

- **Jouez plusieurs mains** pour capturer différentes cartes
- **Attendez que les cartes soient stables** (pas d'animation)
- **Bon éclairage** - fenêtre poker bien visible
- **Supprimez les doublons** après organisation

## 🔧 Options Avancées

```bash
# Capturer pendant 30 minutes
python capture_templates.py --profile pokerstars.json --duration 1800

# Capturer toutes les 2 secondes
python capture_templates.py --profile pokerstars.json --interval 2.0

# Sortie personnalisée
python capture_templates.py \
    --profile pokerstars.json \
    --board-output mes_templates/board \
    --hero-output mes_templates/hero
```

## ❓ Problèmes ?

### "Table not detected"
➡️ Vérifiez que le profil de table est correct et que le poker est visible

### "No cards captured"  
➡️ Vérifiez que les régions dans le profil sont correctes

### Images floues
➡️ Augmentez l'intervalle ou attendez la fin des animations

## 📊 Exemple de Session

```bash
# Jour 1 : Capturer pendant 1h
python capture_templates.py --profile pokerstars.json --duration 3600

# Jour 1 : Organiser les captures
python organize_captured_templates.py \
    --input assets/templates_captured/board \
    --output assets/templates
    
python organize_captured_templates.py \
    --input assets/templates_captured/hero \
    --output assets/hero_templates

# Jour 2 : Utiliser pour jouer avec meilleure reconnaissance !
python -m holdem.cli.run_dry_run --profile pokerstars.json --policy my_policy.pkl
```

## 🎯 Objectif

Obtenir les 52 cartes × 2 sets = **104 templates** pour une reconnaissance optimale !

Le système affiche la progression en temps réel.

---

**Note:** Les cartes hero et board ont souvent un rendu différent dans les clients poker, d'où l'importance de templates séparés ! 🃏
