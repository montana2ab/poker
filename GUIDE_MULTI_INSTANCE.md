# Guide d'utilisation : Entraînement Multi-Instance

Ce guide explique comment utiliser la nouvelle option d'entraînement multi-instance qui permet de lancer plusieurs solveurs indépendants en parallèle.

## Vue d'ensemble

L'option multi-instance permet de lancer **plusieurs instances indépendantes du solver** en parallèle, chacune avec un seul worker. C'est différent du mode parallèle existant qui utilise plusieurs workers au sein d'une seule instance.

### Différence entre les modes

| Mode | Description | Quand l'utiliser |
|------|-------------|------------------|
| **Standard** | 1 instance, 1 worker | Machine simple, petit entraînement |
| **Parallèle** | 1 instance, N workers | Machine multi-cœur, entraînement moyen |
| **Multi-instance** | N instances, 1 worker chacune | Machines multiples ou très gros entraînement |

### Avantages du mode multi-instance

- ✅ **Isolation complète** : Chaque instance fonctionne de manière indépendante
- ✅ **Répartition automatique** : Les itérations sont automatiquement distribuées entre instances
- ✅ **Suivi de progression** : Monitoring en temps réel de chaque instance
- ✅ **Résultats séparés** : Chaque instance garde ses propres checkpoints et logs
- ✅ **Tolérance aux pannes** : Une instance peut échouer sans affecter les autres

## Installation

Aucune installation supplémentaire n'est nécessaire. La fonctionnalité est intégrée dans le CLI existant.

## Utilisation de base

### Commande simple

```bash
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/multi_instance \
  --iters 1000000 \
  --num-instances 4
```

Cette commande va :
1. Lancer 4 instances indépendantes du solver
2. Distribuer les 1,000,000 d'itérations entre elles (250,000 par instance)
3. Chaque instance utilise 1 seul worker
4. Sauvegarder les résultats dans `runs/multi_instance/instance_0/`, `instance_1/`, etc.

### Paramètres

#### Paramètre obligatoire

- `--num-instances N` : Nombre d'instances à lancer (N ≥ 1)

#### Paramètres requis

- `--buckets` : Chemin vers le fichier de buckets
- `--logdir` : Répertoire pour les logs et checkpoints
- `--iters` : Nombre total d'itérations (obligatoire en mode multi-instance)

#### Paramètres compatibles

- `--checkpoint-interval` : Intervalle de sauvegarde des checkpoints
- `--discount-interval` : Intervalle de discount
- `--epsilon` : Epsilon d'exploration
- `--tensorboard` / `--no-tensorboard` : Activer/désactiver TensorBoard
- `--config` : Fichier de configuration YAML
- Tous les autres paramètres MCCFR standards

#### Paramètres incompatibles

❌ `--time-budget` : Non supporté en mode multi-instance (utilisez `--iters`)
❌ `--num-workers` : Chaque instance utilise automatiquement 1 worker
❌ `--resume-from` : Le reprise de checkpoint n'est pas supportée en mode multi-instance

## Exemples d'utilisation

### Exemple 1 : Entraînement rapide avec 4 instances

```bash
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/quick_4_instances \
  --iters 500000 \
  --num-instances 4 \
  --checkpoint-interval 10000
```

**Résultat** :
- Instance 0 : itérations 0 - 124,999
- Instance 1 : itérations 125,000 - 249,999
- Instance 2 : itérations 250,000 - 374,999
- Instance 3 : itérations 375,000 - 499,999

### Exemple 2 : Gros entraînement avec 8 instances

```bash
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/large_8_instances \
  --iters 10000000 \
  --num-instances 8 \
  --checkpoint-interval 50000 \
  --epsilon 0.6
```

**Résultat** : Chaque instance traite 1,250,000 itérations

### Exemple 3 : Utilisation avec fichier de configuration

Créez `configs/multi_instance.yaml` :

```yaml
# Configuration MCCFR
num_iterations: 2000000
checkpoint_interval: 20000
discount_interval: 5000
exploration_epsilon: 0.6
enable_pruning: true
pruning_threshold: -300000000.0
pruning_probability: 0.95
```

Puis lancez :

```bash
python -m holdem.cli.train_blueprint \
  --config configs/multi_instance.yaml \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/config_multi \
  --num-instances 6
```

### Exemple 4 : Nombre impair d'instances

```bash
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/uneven \
  --iters 1000000 \
  --num-instances 3
```

**Distribution des itérations** :
- Instance 0 : 333,334 itérations (0 - 333,333)
- Instance 1 : 333,333 itérations (333,334 - 666,666)
- Instance 2 : 333,333 itérations (666,667 - 999,999)

Le reste est automatiquement distribué aux premières instances.

## Structure des fichiers de sortie

```
runs/multi_instance/
├── progress/
│   ├── instance_0_progress.json    # État de progression instance 0
│   ├── instance_1_progress.json    # État de progression instance 1
│   └── ...
├── instance_0/
│   ├── instance_0.log              # Logs de l'instance 0
│   ├── checkpoint_10000.pkl        # Checkpoints
│   ├── checkpoint_20000.pkl
│   └── tensorboard/                # Logs TensorBoard
│       └── events.out.tfevents...
├── instance_1/
│   └── ...
└── ...
```

## Suivi de la progression

### Monitoring en temps réel

Pendant l'exécution, le système affiche automatiquement la progression toutes les 30 secondes :

```
============================================================
Overall Progress: 45.3%
------------------------------------------------------------
Instance 0: ▶️ 47.2% (iter 118000/250000)
Instance 1: ▶️ 45.8% (iter 114500/250000)
Instance 2: ▶️ 43.9% (iter 109750/250000)
Instance 3: ▶️ 44.5% (iter 111250/250000)
============================================================
```

**Symboles de statut** :
- ⏳ `starting` : Instance en démarrage
- ▶️ `running` : Instance en cours d'exécution
- ✅ `completed` : Instance terminée avec succès
- ❌ `failed` : Instance échouée
- ⏸️ `interrupted` : Instance interrompue par l'utilisateur

### Fichiers de progression

Chaque instance écrit son état dans `progress/instance_N_progress.json` :

```json
{
  "instance_id": 0,
  "start_iter": 0,
  "end_iter": 250000,
  "current_iter": 118000,
  "status": "running",
  "error_msg": null,
  "progress_pct": 47.2,
  "last_update": 1699564823.45
}
```

Vous pouvez lire ces fichiers pour monitorer la progression depuis un script externe.

## Visualisation avec TensorBoard

Chaque instance a ses propres logs TensorBoard. Pour visualiser :

### Instance individuelle

```bash
tensorboard --logdir runs/multi_instance/instance_0/tensorboard
```

### Toutes les instances ensemble

```bash
tensorboard --logdir runs/multi_instance/
```

TensorBoard affichera automatiquement toutes les instances dans des graphiques séparés.

## Utilisation des résultats

### Choisir quelle instance utiliser

Chaque instance a son propre checkpoint final. Pour évaluer :

```bash
# Évaluer l'instance 0
python -m holdem.cli.eval_blueprint \
  --checkpoint runs/multi_instance/instance_0/checkpoint_final.pkl \
  --buckets assets/abstraction/precomputed_buckets.pkl

# Évaluer l'instance 2
python -m holdem.cli.eval_blueprint \
  --checkpoint runs/multi_instance/instance_2/checkpoint_final.pkl \
  --buckets assets/abstraction/precomputed_buckets.pkl
```

### Fusionner les résultats (avancé)

Si vous voulez combiner les stratégies de plusieurs instances, vous devrez :
1. Charger les checkpoints de chaque instance
2. Moyenner les regrets cumulatifs
3. Recalculer la stratégie moyenne

Ceci n'est généralement pas nécessaire car chaque instance produit une stratégie valide indépendamment.

## Gestion des erreurs

### Si une instance échoue

Le système continue à exécuter les autres instances même si l'une échoue. Consultez le log de l'instance échouée :

```bash
cat runs/multi_instance/instance_2/instance_2.log
```

### Interruption gracieuse

Appuyez sur Ctrl+C pour arrêter toutes les instances proprement :

```
Received interrupt signal, shutting down instances...
Terminating instance 0 (PID: 12345)
Terminating instance 1 (PID: 12346)
...
```

Les checkpoints déjà sauvegardés restent valides.

## Conseils de performance

### Choisir le nombre d'instances

| Scénario | Recommandation |
|----------|----------------|
| Machine locale (8 cœurs) | 4-8 instances |
| Serveur (32 cœurs) | 16-32 instances |
| Cluster / Grid | 1 instance par nœud |

### Mémoire

Chaque instance nécessite de la mémoire pour :
- Le bucketing (partagé en lecture seule)
- Les regrets accumulés (~variable selon la taille du jeu)
- Les buffers Python

**Estimation** : ~2-4 GB par instance pour un jeu standard

### Optimisation

1. **Checkpoint interval** : Ajustez `--checkpoint-interval` pour équilibrer :
   - Valeur petite = plus de sauvegardes, moins de perte en cas d'échec
   - Valeur grande = moins d'I/O disque, plus rapide

2. **Nombre d'instances vs itérations** :
   - Trop d'instances avec peu d'itérations = overhead de démarrage
   - Minimum recommandé : 50,000 itérations par instance

3. **Stockage** :
   - Chaque instance crée ses propres checkpoints
   - Prévoir l'espace disque en conséquence

## Comparaison avec le mode parallèle standard

### Mode parallèle standard (`--num-workers`)

```bash
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/parallel \
  --iters 1000000 \
  --num-workers 4 \
  --batch-size 100
```

**Caractéristiques** :
- ✅ 1 seule instance avec 4 workers
- ✅ Synchronisation des workers après chaque batch
- ✅ 1 seul checkpoint final
- ❌ Tous les workers partagent le même processus parent

### Mode multi-instance (`--num-instances`)

```bash
python -m holdem.cli.train_blueprint \
  --buckets assets/abstraction/precomputed_buckets.pkl \
  --logdir runs/multi \
  --iters 1000000 \
  --num-instances 4
```

**Caractéristiques** :
- ✅ 4 instances complètement indépendantes
- ✅ Aucune synchronisation nécessaire
- ✅ 4 checkpoints séparés
- ✅ Isolation complète entre instances

### Quand utiliser chaque mode ?

| Critère | Mode parallèle | Mode multi-instance |
|---------|----------------|---------------------|
| **Machine** | Single | Single ou cluster |
| **Itérations** | < 5M | > 5M |
| **Isolation** | Non nécessaire | Importante |
| **Checkpoints** | 1 seul souhaité | Multiples OK |
| **Flexibilité** | Moins | Plus |

## Dépannage

### Problème : "Multi-instance mode requires --iters"

**Solution** : Le mode multi-instance nécessite `--iters`. N'utilisez pas `--time-budget`.

### Problème : "cannot be used with --num-workers"

**Solution** : Ne spécifiez pas `--num-workers` avec `--num-instances`. Chaque instance utilise automatiquement 1 worker.

### Problème : Instances très lentes

**Vérifications** :
1. Vérifiez l'utilisation CPU : `top` ou `htop`
2. Vérifiez la mémoire disponible : `free -h`
3. Réduisez le nombre d'instances si nécessaire
4. Vérifiez l'I/O disque (checkpoints)

### Problème : Toutes les instances échouent

**Solutions** :
1. Testez d'abord avec 1 instance
2. Vérifiez que le mode standard fonctionne
3. Consultez les logs d'erreur
4. Vérifiez la compatibilité des buckets

## Questions fréquentes

### Q : Puis-je reprendre un entraînement multi-instance ?

**R** : Non, `--resume-from` n'est pas supporté en mode multi-instance. Chaque instance commence à zéro.

### Q : Les instances communiquent-elles entre elles ?

**R** : Non, les instances sont complètement indépendantes. Elles ne partagent que les buckets en lecture seule.

### Q : Puis-je lancer plus d'instances que de cœurs CPU ?

**R** : Oui, mais les performances seront limitées. Recommandation : nombre d'instances ≤ nombre de cœurs.

### Q : Comment combiner les résultats de plusieurs instances ?

**R** : Chaque instance produit une stratégie valide. Choisissez celle avec les meilleures métriques (L2 regret slope, entropy) ou utilisez-en une au hasard.

### Q : Le mode multi-instance est-il plus rapide ?

**R** : Pas nécessairement. Il offre plus d'isolation et de flexibilité, mais pas nécessairement plus de vitesse qu'un mode parallèle bien configuré.

### Q : Puis-je lancer des instances sur des machines différentes ?

**R** : Oui ! Lancez chaque instance avec des ranges d'itérations manuellement spécifiées (fonctionnalité à venir). Pour l'instant, lancez le coordinateur sur une machine qui peut accéder à toutes les autres.

## Exemples avancés

### Script de lancement automatisé

```bash
#!/bin/bash
# launch_multi_instance.sh

BUCKETS="assets/abstraction/precomputed_buckets.pkl"
LOGDIR="runs/auto_multi_$(date +%Y%m%d_%H%M%S)"
ITERS=5000000
INSTANCES=8

echo "Launching $INSTANCES instances for $ITERS iterations"
echo "Logs: $LOGDIR"

python -m holdem.cli.train_blueprint \
  --buckets "$BUCKETS" \
  --logdir "$LOGDIR" \
  --iters $ITERS \
  --num-instances $INSTANCES \
  --checkpoint-interval 25000 \
  --tensorboard

echo "Training complete!"
echo "View results: ls $LOGDIR/"
```

### Monitoring script externe

```python
#!/usr/bin/env python3
# monitor_progress.py

import json
import time
from pathlib import Path

def monitor(progress_dir):
    progress_dir = Path(progress_dir)
    
    while True:
        progress_files = sorted(progress_dir.glob("instance_*_progress.json"))
        
        if not progress_files:
            print("No progress files found")
            time.sleep(5)
            continue
        
        total_progress = 0
        all_completed = True
        
        print("\n" + "=" * 60)
        for pfile in progress_files:
            with open(pfile) as f:
                data = json.load(f)
            
            total_progress += data['progress_pct']
            
            if data['status'] not in ['completed', 'failed']:
                all_completed = False
            
            print(f"Instance {data['instance_id']}: {data['status']} - "
                  f"{data['progress_pct']:.1f}% (iter {data['current_iter']})")
        
        avg_progress = total_progress / len(progress_files)
        print(f"\nOverall: {avg_progress:.1f}%")
        print("=" * 60)
        
        if all_completed:
            print("All instances completed!")
            break
        
        time.sleep(10)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python monitor_progress.py <progress_dir>")
        sys.exit(1)
    
    monitor(sys.argv[1])
```

Utilisation :

```bash
python monitor_progress.py runs/multi_instance/progress/
```

## Conclusion

Le mode multi-instance offre une approche flexible et robuste pour l'entraînement de grande échelle. Utilisez-le quand vous avez besoin de :
- **Isolation** : Instances indépendantes
- **Flexibilité** : Checkpoints séparés
- **Scalabilité** : Distribution sur plusieurs machines (futur)

Pour des entraînements standards sur une seule machine, le mode parallèle (`--num-workers`) reste une excellente option.

## Support

Pour des questions ou des problèmes :
1. Consultez les logs d'instance : `cat runs/logdir/instance_N/instance_N.log`
2. Vérifiez les fichiers de progression JSON
3. Comparez avec les exemples de ce guide
4. Ouvrez une issue sur GitHub avec les logs pertinents
