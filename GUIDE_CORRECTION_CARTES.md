# Guide de Correction - Reconnaissance des Cartes

## Problème Identifié

Le problème de reconnaissance des cartes a été identifié : les cartes du héros (vos cartes) et les cartes du board (cartes communes) ont des caractéristiques visuelles différentes dans le client poker, ce qui causait des problèmes de reconnaissance.

## Solution Implémentée

Une base de templates séparée a été créée pour les cartes du héros et les cartes du board :

### 1. Deux Ensembles de Templates

- **`assets/templates/`** - Templates pour les cartes du board (cartes communes)
- **`assets/hero_templates/`** - Templates pour les cartes du héros (vos cartes)

### 2. Pourquoi Deux Ensembles ?

Les cartes du héros et du board ont souvent des différences visuelles :
- **Taille** : Les cartes peuvent être affichées à des tailles différentes
- **Éclairage** : Différentes zones de la table ont un éclairage différent
- **Style** : Certains clients rendent les cartes différemment selon leur position
- **Angle de vue** : Les cartes du héros peuvent avoir une perspective légèrement différente

## Comment Utiliser

### Étape 1 : Créer les Templates du Board

1. Démarrez une partie de poker
2. Attendez que les 5 cartes du board soient visibles
3. Prenez une capture d'écran
4. Découpez chaque carte individuellement
5. Sauvegardez dans `assets/templates/` avec le nom `{rang}{couleur}.png`
   - Exemple : `Ah.png` pour As de cœur
   - Rangs : 2, 3, 4, 5, 6, 7, 8, 9, T, J, Q, K, A
   - Couleurs : h (hearts/cœur), d (diamonds/carreau), c (clubs/trèfle), s (spades/pique)

### Étape 2 : Créer les Templates du Héros

1. Démarrez une partie de poker
2. Attendez de recevoir vos cartes (hole cards)
3. Prenez une capture d'écran
4. Découpez chaque carte de VOTRE position
5. Sauvegardez dans `assets/hero_templates/` avec la même convention de nommage
6. Répétez pour obtenir les 52 cartes

### Étape 3 : Configurer le Profil de Table

Dans votre profil de table (fichier JSON dans `assets/table_profiles/`), ajoutez :

```json
{
  "window_title": "Votre Client Poker",
  "hero_position": 0,
  "hero_templates_dir": "assets/hero_templates",
  "card_regions": [...],
  "player_regions": [...],
  ...
}
```

- `hero_position` : L'index de votre position dans `player_regions` (commence à 0)
- `hero_templates_dir` : Le chemin vers vos templates de cartes héros

### Étape 4 : Tester

Exécutez le script d'exemple :

```bash
python example_hero_templates.py
```

Cela va :
- Créer des templates de test (à remplacer par de vrais templates)
- Montrer comment configurer le système
- Expliquer comment utiliser les deux ensembles de templates

## Changements Techniques

### CardRecognizer

```python
# Avant
recognizer = CardRecognizer(templates_dir)

# Maintenant
recognizer = CardRecognizer(
    templates_dir=board_templates_dir,
    hero_templates_dir=hero_templates_dir
)

# Utilisation
board_card = recognizer.recognize_card(img, use_hero_templates=False)
hero_card = recognizer.recognize_card(img, use_hero_templates=True)
```

### StateParser

Le `StateParser` utilise maintenant automatiquement les bons templates :
- Cartes du board → templates du board
- Cartes du héros → templates du héros (si disponibles, sinon templates du board)

## Avantages

1. **Meilleure Précision** : Chaque ensemble de templates est optimisé pour son type de carte
2. **Détection Preflop** : Amélioration de la détection des cartes au preflop
3. **Flexible** : Fonctionne avec ou sans templates héros (fallback automatique)
4. **Rétrocompatible** : Code existant continue de fonctionner

## Prochaines Étapes

1. Créez vos propres templates à partir de captures d'écran réelles
2. Configurez votre profil de table avec `hero_position` et `hero_templates_dir`
3. Testez la reconnaissance des cartes
4. Ajustez les templates si nécessaire

## Fichiers Modifiés

- `src/holdem/vision/cards.py` - Support des templates héros
- `src/holdem/vision/parse_state.py` - Utilisation des templates héros
- `src/holdem/vision/calibrate.py` - Configuration du profil
- `tests/test_hero_card_detection.py` - Tests complets
- `assets/hero_templates/` - Nouveau répertoire
- `example_hero_templates.py` - Script d'exemple

## Support

Pour plus d'informations :
- Voir `assets/templates/README.md`
- Voir `assets/hero_templates/README.md`
- Exécuter `python example_hero_templates.py`
