# 🚀 DÉMARRAGE RAPIDE - 3 Étapes Simples

## Le Problème Est Résolu ! ✅

Vos cartes hero et les cartes du board seront maintenant reconnues correctement.

## Comment Utiliser - 3 Commandes

### 1️⃣ Capturer les Cartes (pendant que vous jouez)

```bash
python capture_templates.py --profile assets/table_profiles/pokerstars.json
```

**→ Jouez au poker normalement. Appuyez sur Ctrl+C pour arrêter.**

### 2️⃣ Identifier les Cartes

```bash
# Cartes du board
python organize_captured_templates.py \
    --input assets/templates_captured/board \
    --output assets/templates

# Vos cartes
python organize_captured_templates.py \
    --input assets/templates_captured/hero \
    --output assets/hero_templates
```

**→ Tapez l'identité de chaque carte (ex: Ah, Ks, 7d)**

### 3️⃣ C'est Prêt !

```bash
python -m holdem.cli.run_dry_run \
    --profile assets/table_profiles/pokerstars.json \
    --policy votre_policy.pkl
```

**→ La reconnaissance des cartes fonctionne maintenant ! 🎉**

## 📖 Plus d'Infos

- **Démarrage rapide:** `README_AUTO_CAPTURE.md`
- **Guide complet:** `GUIDE_AUTO_CAPTURE.md`
- **Configuration:** `GUIDE_CORRECTION_CARTES.md`
- **Création de buckets:** `GUIDE_CREATION_BUCKETS.md` - Guide détaillé pour créer buckets.pkl

## ❓ Besoin d'Aide ?

Tous les guides sont en français dans ce dossier !

---

**C'est tout ! Trois commandes et c'est résolu.** 🎴
