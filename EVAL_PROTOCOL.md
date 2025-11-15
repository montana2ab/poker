# EVAL_PROTOCOL.md

Protocole d'évaluation : métriques, AIVAT/variance reduction, batteries de tests, adversaires, seeds, bornes statistiques, seuils de régression

---

## TABLE DES MATIÈRES

1. [Vue d'ensemble](#1-vue-densemble)
2. [Protocole standard type Pluribus](#2-protocole-standard-type-pluribus)
3. [Métriques d'évaluation](#3-métriques-dévaluation)
4. [AIVAT et réduction de variance](#4-aivat-et-réduction-de-variance)
5. [Adversaires de référence](#5-adversaires-de-référence)
6. [Configuration seeds et reproductibilité](#6-configuration-seeds-et-reproductibilité)
7. [Intervalles de confiance et significativité](#7-intervalles-de-confiance-et-significativité)
8. [Batteries de tests](#8-batteries-de-tests)
9. [Seuils de régression](#9-seuils-de-régression)
10. [Protocole d'exécution](#10-protocole-dexécution)
11. [Rapports et documentation](#11-rapports-et-documentation)

---

## 1. VUE D'ENSEMBLE

### 1.1 Objectifs

L'évaluation du poker AI vise à :

1. **Mesurer la force absolue** : Performance vs adversaires connus
2. **Détecter les régressions** : Comparaison vs versions précédentes
3. **Quantifier l'incertitude** : Intervalles de confiance statistiques
4. **Valider les changements** : Tests non-régression avant merge

### 1.2 Principes

- **Reproductibilité** : Seeds contrôlés, environnement déterministe
- **Significativité** : Échantillons suffisamment larges (CI 95%)
- **Faible variance** : AIVAT pour efficacité d'échantillonnage
- **Automatisation** : Scripts standardisés, CI/CD intégré

---

## 2. PROTOCOLE STANDARD TYPE PLURIBUS

### 2.1 Vue d'ensemble du protocole

Ce protocole définit une méthode d'évaluation standardisée, reproductible et statistiquement rigoureuse pour évaluer les agents poker, inspirée des méthodes utilisées dans Pluribus et d'autres systèmes de pointe.

### 2.2 Format de jeu

**Configuration standard:**
- **Variante:** Texas Hold'em No-Limit
- **Table:** 6-max (6 joueurs maximum)
- **Blinds:** SB = 1, BB = 2 (ou configuration équivalente)
- **Stack initial:** 200 BB (par défaut)
- **Avant:** Aucun (No Ante)

**Rationale:**
- 6-max est le format standard pour l'évaluation multiplayer
- Permet une évaluation équilibrée entre complexité et vitesse
- Compatible avec les benchmarks académiques et industriels

### 2.3 Nombre de mains recommandé

**Objectifs par type d'évaluation:**

| Type d'évaluation | Mains minimales | Mains recommandées | Durée estimée | Objectif |
|-------------------|-----------------|---------------------|---------------|----------|
| Quick test (sanity check) | 500 | 1,000 | 5-10 min | Vérifier pas de crash |
| Développement (itératif) | 5,000 | 10,000 | 30-60 min | Tests rapides pendant dev |
| Évaluation standard | 50,000 | 100,000 | 2-4 heures | CI ±1-2 bb/100 |
| Évaluation rigoureuse | 100,000 | 200,000 | 4-8 heures | CI ±0.5-1 bb/100 |
| Publication scientifique | 200,000 | 500,000+ | 8-20+ heures | Haute précision statistique |

**Notes:**
- Avec AIVAT (78% réduction variance), diviser par ~4-5x pour même précision
- Plus de mains = intervalles de confiance plus serrés
- Ajuster selon la variance de l'agent (agents serrés = moins de variance)

### 2.4 Types de matchs

#### 2.4.1 Blueprint vs Baselines

**Objectif:** Mesurer la force absolue de l'agent blueprint contre des adversaires connus

**Configuration:**
- 1 agent blueprint (héros) vs 5 baseline agents
- Baselines: Mix de RandomAgent, TightAgent, LooseAggressiveAgent, CallingStation
- Position héros: Rotation équitable (chaque position 1/6 du temps)
- Seeds: Fixe pour reproductibilité

**Commande exemple:**
```bash
bin/run_eval_blueprint_vs_baselines.py \
  --policy runs/blueprint/avg_policy.json \
  --num-hands 50000 \
  --seed 42 \
  --out eval_runs/blueprint_vs_baselines.json
```

**Métriques attendues:**
- vs RandomAgent: +40 à +60 bb/100
- vs TightAgent: +15 à +25 bb/100
- vs LooseAggressiveAgent: +5 à +15 bb/100
- vs CallingStation: +10 à +20 bb/100

#### 2.4.2 Blueprint + Re-solve vs Baselines

**Objectif:** Mesurer l'amélioration apportée par le re-solving en temps réel

**Configuration:**
- 1 agent (blueprint + real-time search) vs 5 baseline agents
- Baselines identiques au test précédent
- Budget temps RT: 80ms par décision (configurable)
- Public card sampling: 1-64 samples (typiquement 16)

**Commande exemple:**
```bash
bin/run_eval_resolve_vs_blueprint.py \
  --policy runs/blueprint/avg_policy.json \
  --num-hands 50000 \
  --time-budget 80 \
  --samples-per-solve 16 \
  --seed 42 \
  --out eval_runs/resolve_vs_baselines.json
```

**Amélioration attendue:**
- EVΔ (resolve - blueprint): +2 à +8 bb/100 selon la qualité du blueprint
- Latence p95 < 150ms, p99 < 200ms

#### 2.4.3 Agent Re-solve vs Agent Blueprint

**Objectif:** Évaluation directe de l'amélioration du re-solving

**Configuration:**
- Heads-up: Agent avec RT search vs Agent blueprint seul
- Duplicate deals avec swap de position
- Permet isolation exacte de l'effet du re-solving

**Commande exemple:**
```bash
tools/eval_rt_vs_blueprint.py \
  --policy runs/blueprint/avg_policy.json \
  --hands 10000 \
  --samples-per-solve 16 \
  --output eval_runs/rt_vs_blueprint.json
```

**Interprétation:**
- EVΔ > 0: Re-solving améliore la stratégie
- EVΔ ≈ 0: Blueprint déjà near-optimal
- EVΔ < 0: Re-solving dégrade (sur-fitting, bruit)

### 2.5 Métriques à reporter

**Pour chaque évaluation, documenter:**

1. **Performance:**
   - bb/100 par joueur/agent
   - Intervalle de confiance 95% (CI 95%)
   - Nombre de mains (N)
   - p-value pour significativité statistique

2. **Configuration:**
   - Policy utilisée (path + commit hash)
   - Buckets configuration (si applicable)
   - Seed(s) utilisé(s)
   - Format de jeu (6-max, HU, etc.)
   - Baselines (agents adverses)

3. **Performance système (si RT search):**
   - Latence moyenne, p50, p95, p99
   - Nombre de samples per solve
   - Budget temps par décision
   - Taux de fallback au blueprint

4. **Variance (si AIVAT activé):**
   - Variance vanilla
   - Variance AIVAT
   - % réduction de variance
   - Efficiency gain (ratio)

### 2.6 Interprétation des résultats

**Comment déterminer qu'un agent est "meilleur":**

#### Critère 1: Significativité statistique

L'agent A est statistiquement meilleur que B si:
- L'intervalle de confiance 95% de (A - B) ne contient pas 0
- p-value < 0.05 (test bilatéral)

**Exemple:**
```
Agent A: +10.5 ± 1.2 bb/100 (CI: [9.3, 11.7])
Agent B: +8.2 ± 1.3 bb/100 (CI: [6.9, 9.5])
Différence: +2.3 bb/100
CI de la différence: [0.5, 4.1]  ✅ Ne contient pas 0 → SIGNIFICATIF
```

#### Critère 2: Taille de l'effet (Effect Size)

Utiliser Cohen's d pour quantifier l'ampleur de la différence:
- d < 0.2: Effet négligeable
- 0.2 ≤ d < 0.5: Petit effet
- 0.5 ≤ d < 0.8: Effet moyen
- d ≥ 0.8: Grand effet

#### Critère 3: Pertinence pratique

Au-delà de la significativité statistique, considérer:
- **bb/100 > 2:** Amélioration pratiquement pertinente
- **bb/100 < 1:** Amélioration marginale (peut ne pas valoir le coût en latence/complexité)
- **Trade-offs:** Latence vs performance, mémoire vs précision

**Règle de décision:**
1. Si statistiquement significatif ET effect size > 0.2 ET bb/100 > 1: **ADOPTION**
2. Si statistiquement significatif mais effet petit: **À CONSIDÉRER** (dépend du contexte)
3. Si non significatif: **PAS D'ADOPTION** (besoin de plus de données)

### 2.7 Scripts d'évaluation

**Scripts disponibles:**

1. **bin/run_eval_blueprint_vs_baselines.py**
   - Évaluation blueprint contre baselines
   - Support mode quick-test (--quick-test)
   - Sortie JSON + résumé console

2. **bin/run_eval_resolve_vs_blueprint.py**
   - Évaluation agent avec RT search
   - Comparaison avec baseline blueprint
   - Métriques de latence incluses

3. **tools/eval_rt_vs_blueprint.py**
   - Évaluation heads-up directe RT vs blueprint
   - Duplicate deals + position swap
   - EVΔ avec bootstrap CI

**Voir les sections suivantes pour plus de détails sur les métriques et l'utilisation.**

---

## 3. MÉTRIQUES D'ÉVALUATION

### 2.1 Métriques principales

#### 2.1.1 Winrate (bb/100 hands)

**Définition:**  
Big blinds gagnées par 100 mains jouées

**Formule:**
```
winrate (bb/100) = (total_chips_won / num_hands) * (100 / big_blind)
```

**Interprétation:**
- `+10 bb/100` : Très fort (niveau pro)
- `+5 bb/100` : Fort (gagnant régulier)
- `+2 bb/100` : Gagnant marginal
- `0 bb/100` : Break-even
- `-X bb/100` : Perdant

**Code:**
```python
def compute_winrate(chip_results: List[float], big_blind: float) -> float:
    """Compute winrate in bb/100 hands."""
    total_profit = sum(chip_results)
    num_hands = len(chip_results)
    bb_per_hand = total_profit / big_blind
    return (bb_per_hand / num_hands) * 100
```

#### 2.1.2 Variance (σ²)

**Définition:**  
Dispersion des résultats autour de la moyenne

**Formule:**
```
variance = E[(X - μ)²]
```

**Usage:**
- Évaluer la consistance du bot
- Calculer intervalles de confiance
- Estimer taille échantillon requise

#### 2.1.3 Standard Error (SE)

**Définition:**  
Erreur standard de la moyenne

**Formule:**
```
SE = σ / sqrt(n)
```

où σ est l'écart-type et n la taille d'échantillon

#### 2.1.4 Exploitability (mbb/hand)

**Définition:**  
Profit maximal d'un adversaire optimal contre notre stratégie

**Mesure:**
- Calculable exactement en heads-up simplifié
- Approximation via best-response en multiplayer
- Métrique théorique de qualité stratégie

**Cible:**
- < 10 mbb/hand : Très fort
- < 50 mbb/hand : Compétitif
- < 100 mbb/hand : Acceptable

### 2.2 Métriques secondaires

- **VPIP** (Voluntarily Put In Pot) : % mains jouées
- **PFR** (Pre-Flop Raise) : % raises préflop
- **3-bet %** : % 3-bets préflop
- **Aggression Factor** : (Bets + Raises) / Calls
- **Showdown Win %** : % victoires à l'abattage
- **Non-showdown Win %** : % pots gagnés sans abattage

---

## 3. AIVAT ET RÉDUCTION DE VARIANCE

### 3.1 Principe AIVAT

**AIVAT** (Actor-Independent Variance-reduced Advantage Technique) réduit la variance d'évaluation en retirant une baseline indépendante des actions du joueur.

**Formule:**
```
Advantage_i = Payoff_i - V_i(s, a_{-i})
```

où:
- `Payoff_i` : gain réel du joueur i
- `V_i(s, a_{-i})` : valeur baseline conditionnelle aux actions adversaires
- `s` : état du jeu
- `a_{-i}` : actions des adversaires

### 3.2 Implémentation

**STATUS : ✅ IMPLÉMENTÉ**

L'implémentation AIVAT est maintenant disponible dans `src/holdem/rl_eval/aivat.py`.

**Étapes:**

1. **Collecte de samples** : Jouer N mains, enregistrer (state, actions, payoff)
2. **Training value functions** : Apprendre V_i(s, a_{-i}) par régression
3. **Compute advantages** : Payoff - baseline pour chaque sample
4. **Estimation** : Moyenne des advantages (variance réduite)

**Code basique:**
```python
from holdem.rl_eval.aivat import AIVATEvaluator

# Initialize
aivat = AIVATEvaluator(num_players=9, min_samples=1000)

# Collect training samples (warm-up)
for _ in range(1000):
    result = play_hand(policy, opponents)
    aivat.add_sample(
        player_id=0,
        state_key=result['state'],
        actions_taken=result['actions'],
        payoff=result['payoff']
    )

# Train value functions
aivat.train_value_functions(min_samples=1000)

# Evaluate with variance reduction
for _ in range(10000):
    result = play_hand(policy, opponents)
    advantage = aivat.compute_advantage(
        player_id=0,
        state_key=result['state'],
        actual_payoff=result['payoff']
    )
    # Use advantage for estimation
```

**Intégration avec l'évaluateur:**
```python
from holdem.rl_eval.eval_loop import Evaluator
from holdem.mccfr.policy_store import PolicyStore

# Create evaluator with AIVAT enabled
policy = PolicyStore()
evaluator = Evaluator(policy, use_aivat=True, num_players=9)

# Run evaluation with warmup phase for baseline training
results = evaluator.evaluate(
    num_episodes=10000,
    warmup_episodes=1000
)

# Results include variance metrics
for baseline_name, metrics in results.items():
    if 'aivat' in metrics:
        print(f"{baseline_name}:")
        print(f"  Vanilla variance: {metrics['aivat']['vanilla_variance']:.2f}")
        print(f"  AIVAT variance: {metrics['aivat']['aivat_variance']:.2f}")
        print(f"  Reduction: {metrics['aivat']['variance_reduction_pct']:.1f}%")
```

**Fonctionnalités clés:**

- `AIVATEvaluator`: Classe principale pour la réduction de variance
- `add_sample()`: Collecte des échantillons pour entraînement
- `train_value_functions()`: Entraîne les fonctions de valeur baseline
- `compute_advantage()`: Calcule l'avantage variance-réduit
- `compute_variance_reduction()`: Statistiques de réduction
- `get_statistics()`: État actuel de l'évaluateur

**Tests disponibles:**

- `tests/test_aivat.py`: Tests unitaires complets
  - Test d'initialisation et configuration
  - Test de collecte d'échantillons
  - Test d'entraînement des value functions
  - Test de calcul d'avantages
  - Test de réduction de variance (>30% requis)
  - Test de biais (vérification estimation non biaisée)
  - Test avec données synthétiques multi-états

- `tests/test_aivat_integration.py`: Tests d'intégration
  - Test evaluateur sans AIVAT (mode vanilla)
  - Test evaluateur avec AIVAT activé
  - Test de réduction de variance dans l'évaluateur
  - Test de l'interface _play_episode_with_state

**Résultats des tests:**

Sur données synthétiques avec multiples états et variance connue:
- Réduction variance simple état: **94.5%** (σ²: 652 → 36)
- Réduction variance multi-états: **78.8%** (σ²: 1028 → 218)
- Estimation non biaisée: moyenne AIVAT ≈ 0.0 (vérifiée)
- ✅ Dépasse largement l'objectif de 30% de réduction

### 3.3 Gains attendus

**RÉSULTATS OBTENUS : ✅ VALIDÉ**

**Réduction de variance mesurée:**
- Tests sur données synthétiques: **78.8% - 94.5%** de réduction
- Largement supérieur à l'objectif de 30%
- Permet échantillon 2-5x plus petit pour même précision
- Critique en multiplayer (variance naturellement élevée)

**Exemples de performance:**

1. **Cas simple (état unique):**
   - Vanilla: σ² = 652.05
   - AIVAT: σ² = 36.16
   - **Réduction: 94.5%** ✅

2. **Cas réaliste (10 états différents):**
   - Vanilla: σ² = 1028.36
   - AIVAT: σ² = 217.55
   - **Réduction: 78.8%** ✅

**Impact pratique:**
- Sans AIVAT : σ² = 100 → n = 10,000 mains pour CI±2bb/100
- Avec AIVAT (78% reduction) : σ² = 22 → n = 2,200 mains pour même précision
- **Économie: ~78% de temps d'évaluation**

**Propriétés validées:**
- ✅ Estimation non biaisée (AIVAT mean ≈ vanilla mean)
- ✅ Variance significativement réduite (>30% requis)
- ✅ Robustesse sur différents patterns de données
- ✅ Scalabilité multi-joueurs (testé jusqu'à 9 joueurs)

---

## 4. ADVERSAIRES DE RÉFÉRENCE

### 4.1 Baselines intégrés

#### 4.1.1 RandomAgent

**Comportement:**
- Actions uniformément aléatoires parmi actions légales
- Fold/call/raise avec proba égale (après légalité)

**Usage:**
- Sanity check : bot doit dominer largement
- Baseline minimum : winrate > +50 bb/100 attendu

#### 4.1.2 TightAgent

**Comportement:**
- Joue seulement top 10-15% mains préflop
- Fold à toute aggression sans main forte
- Stratégie passive : call > raise

**Usage:**
- Adversaire facile exploitable
- Winrate cible : +20 bb/100

#### 4.1.3 LooseAggressiveAgent

**Comportement:**
- Joue 40-50% mains préflop (loose)
- Bet/raise fréquent (aggressive)
- Surestime force mains marginales

**Usage:**
- Adversaire difficile à court terme (variance)
- Winrate cible : +10 bb/100 (plus difficile)

#### 4.1.4 CallingStation

**Comportement:**
- Call excessif, fold rarement
- Passive (rarement raise)
- Exploitable par value betting

**Usage:**
- Tester exploitation calling stations
- Winrate cible : +15 bb/100

### 4.2 Adversaires externes

#### 4.2.1 Slumbot (si disponible)

**Source:** http://www.slumbot.com/  
**Niveau:** Professionnel heads-up  
**Usage:** Benchmark compétitif

#### 4.2.2 Stratégies GTO approximatives

**Source:** Solver outputs (PioSolver, etc.)  
**Niveau:** Near-optimal  
**Usage:** Mesure exploitability

### 4.3 Configuration multi-adversaires

**Setup recommandé pour tests:**

```python
opponents = [
    TightAgent(),
    TightAgent(),
    LooseAggressiveAgent(),
    LooseAggressiveAgent(),
    CallingStation(),
    CallingStation(),
    RandomAgent(),  # Sanity check
    RandomAgent()
]
```

**Diversité:** Mix de styles force le bot à adapter

---

## 5. CONFIGURATION SEEDS ET REPRODUCTIBILITÉ

### 5.1 Seeds standards

**Seeds de test dédiés:**

```python
# Seeds pour évaluation reproductible
EVAL_SEEDS = {
    'baseline': 42,        # Seed principal
    'variant_1': 1337,     # Seed alternatif 1
    'variant_2': 2048,     # Seed alternatif 2
    'regression': 9999     # Seed tests non-régression
}
```

### 5.2 Protocole seeding

**Avant chaque évaluation:**

```python
import numpy as np
import random
from holdem.utils.rng import set_global_seed

# Set all seeds
seed = EVAL_SEEDS['baseline']
set_global_seed(seed)
np.random.seed(seed)
random.seed(seed)

# Log seed used
logger.info(f"Evaluation seed: {seed}")
```

### 5.3 Vérification reproductibilité

**Test:**

```bash
# Run 1
python -m holdem.cli.eval_blueprint \
  --policy policy.json \
  --seed 42 \
  --episodes 1000 \
  --out results_run1.json

# Run 2
python -m holdem.cli.eval_blueprint \
  --policy policy.json \
  --seed 42 \
  --episodes 1000 \
  --out results_run2.json

# Compare
diff results_run1.json results_run2.json
# Doit être identique
```

---

## 7. INTERVALLES DE CONFIANCE ET SIGNIFICATIVITÉ

### 7.1 Calcul intervalles de confiance 95%

**STATUS : ✅ IMPLÉMENTÉ**

L'implémentation des intervalles de confiance est maintenant disponible dans `src/holdem/rl_eval/statistics.py`.

**Méthode 1 : Bootstrap (distribution-free, recommandée)**

Le bootstrap est la méthode recommandée car elle ne nécessite aucune hypothèse sur la distribution des données (non-paramétrique).

```python
from holdem.rl_eval.statistics import compute_confidence_interval

# Compute 95% CI using bootstrap
results = [5.2, 3.1, 6.8, 4.5, 5.9, ...]  # Evaluation results
ci_info = compute_confidence_interval(
    results,
    confidence=0.95,
    method="bootstrap",
    n_bootstrap=10000
)

print(f"Mean: {ci_info['mean']:.2f}")
print(f"95% CI: [{ci_info['ci_lower']:.2f}, {ci_info['ci_upper']:.2f}]")
print(f"Margin: ±{ci_info['margin']:.2f}")
```

**Méthode 2 : Analytique (si distribution normale)**

Pour les cas où l'on peut supposer la normalité (grands échantillons), une méthode analytique plus rapide est disponible.

```python
# Compute 95% CI using analytical method (t-distribution)
ci_info = compute_confidence_interval(
    results,
    confidence=0.95,
    method="analytical"
)
```

**Fonctionnalités incluses :**

- Calcul automatique de la marge d'erreur
- Support de différents niveaux de confiance (90%, 95%, 99%, etc.)
- Fallback gracieux si scipy n'est pas disponible
- Calcul de l'erreur standard (stderr)
- Logging détaillé pour debugging

### 7.2 Taille d'échantillon requise

**STATUS : ✅ IMPLÉMENTÉ**

La fonction `required_sample_size()` calcule le nombre d'échantillons nécessaires pour atteindre une marge d'erreur cible.

**Formule:**

```
n = (Z * σ / E)²
```

où:
- Z : score critique (1.96 pour 95% CI)
- σ : écart-type estimé
- E : marge d'erreur désirée

**Utilisation:**

```python
from holdem.rl_eval.statistics import required_sample_size

# Exemple: Vouloir ±1 bb/100 avec σ²=100
n = required_sample_size(
    target_margin=1.0,
    estimated_variance=100.0,
    confidence=0.95
)
print(f"Required sample size: {n} hands")
# Output: ~385 hands
```

**Exemples de calculs:**

| Variance (σ²) | Target Margin | Confidence | Sample Size |
|---------------|---------------|------------|-------------|
| 100 (σ=10)    | ±1 bb/100     | 95%        | ~385        |
| 100 (σ=10)    | ±2 bb/100     | 95%        | ~97         |
| 25 (σ=5)      | ±1 bb/100     | 95%        | ~97         |
| 400 (σ=20)    | ±1 bb/100     | 95%        | ~1537       |

**Avec AIVAT (78% réduction de variance):**

```python
# Sans AIVAT: σ²=100 → n=385 pour ±1 bb/100
# Avec AIVAT: σ²=22 → n=85 pour ±1 bb/100
# Économie: 78% d'échantillons en moins!

from holdem.rl_eval.statistics import estimate_variance_reduction

reduction = estimate_variance_reduction(
    vanilla_variance=100.0,
    aivat_variance=22.0
)
print(f"Variance reduction: {reduction['reduction_pct']:.1f}%")
print(f"Efficiency gain: {reduction['efficiency_gain']:.1f}x")
```

### 7.3 Vérification d'adéquation de la marge

**STATUS : ✅ IMPLÉMENTÉ**

La fonction `check_margin_adequacy()` vérifie si la marge actuelle est suffisante et recommande des échantillons supplémentaires si nécessaire.

```python
from holdem.rl_eval.statistics import check_margin_adequacy

adequacy = check_margin_adequacy(
    current_margin=1.5,
    target_margin=1.0,
    current_n=1000,
    estimated_variance=100.0,
    confidence=0.95
)

if not adequacy['is_adequate']:
    print(adequacy['recommendation'])
    # Output: "Current margin (1.50) exceeds target (1.00). 
    #          Recommend 485 additional samples (total: 1485)"
```

### 7.4 Intégration avec l'évaluateur

**STATUS : ✅ IMPLÉMENTÉ**

Les statistiques CI sont maintenant automatiquement calculées lors de l'évaluation.

```python
from holdem.rl_eval.eval_loop import Evaluator
from holdem.mccfr.policy_store import PolicyStore

# Create evaluator with CI calculation
policy = PolicyStore()
evaluator = Evaluator(
    policy,
    use_aivat=True,
    confidence_level=0.95,
    target_margin=1.0  # Target ±1 bb/100
)

# Run evaluation
results = evaluator.evaluate(num_episodes=10000, warmup_episodes=1000)

# Results now include CI information
for baseline_name, metrics in results.items():
    if baseline_name == 'aivat_stats':
        continue
    
    ci = metrics['confidence_interval']
    print(f"{baseline_name}:")
    print(f"  Winrate: {ci['mean']:.2f} ± {ci['margin']:.2f} bb/100")
    print(f"  95% CI: [{ci['ci_lower']:.2f}, {ci['ci_upper']:.2f}]")
    
    # Check margin adequacy
    if 'margin_adequacy' in metrics:
        adequacy = metrics['margin_adequacy']
        if not adequacy['is_adequate']:
            print(f"  ⚠️ {adequacy['recommendation']}")
```

**Résultats enrichis:**

Chaque baseline result contient maintenant:
- `confidence_interval`: Dict avec mean, ci_lower, ci_upper, margin, std, stderr
- `margin_adequacy`: Dict avec is_adequate et recommendation (si target_margin spécifié)
- `aivat_confidence_interval`: CI pour les avantages AIVAT (si AIVAT activé)

### 7.5 Formatage des résultats

**STATUS : ✅ IMPLÉMENTÉ**

```python
from holdem.rl_eval.statistics import format_ci_result

# Format CI result for display
formatted = format_ci_result(
    value=5.23,
    ci_info=ci,
    decimals=2,
    unit="bb/100"
)
print(formatted)
# Output: "5.23 ± 0.45 bb/100 (95% CI: [4.78, 5.68])"
```

### 7.6 Tests de significativité

**Test t de Student (comparaison 2 policies):**

```python
from scipy import stats

def compare_policies(results_a: List[float], results_b: List[float], alpha=0.05):
    """Test if policy A significantly better than B."""
    
    # Two-sample t-test
    t_statistic, p_value = stats.ttest_ind(results_a, results_b)
    
    # Effect size (Cohen's d)
    mean_diff = np.mean(results_a) - np.mean(results_b)
    pooled_std = np.sqrt((np.var(results_a) + np.var(results_b)) / 2)
    cohens_d = mean_diff / pooled_std
    
    is_significant = p_value < alpha
    
    return {
        't_statistic': t_statistic,
        'p_value': p_value,
        'is_significant': is_significant,
        'mean_difference': mean_diff,
        'cohens_d': cohens_d,
        'effect_size_interpretation': interpret_cohens_d(cohens_d)
    }

def interpret_cohens_d(d: float) -> str:
    """Interpret Cohen's d effect size."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"
```

---

## 7. BATTERIES DE TESTS

### 7.1 Test Suite Standard

#### 7.1.1 Smoke Test (rapide)

**Durée:** 1 minute  
**Objectif:** Vérifier pas de crash évident

```bash
pytest tests/test_eval_smoke.py -v
# - 100 mains vs RandomAgent
# - Vérifier winrate > 0
# - Pas de crash
```

#### 7.1.2 Regression Test

**Durée:** 10 minutes  
**Objectif:** Détecter régressions vs version précédente

```bash
pytest tests/test_eval_regression.py -v
# - 5,000 mains vs baselines
# - Seed fixe (EVAL_SEEDS['regression'])
# - Comparer winrate ± 5%
```

#### 7.1.3 Full Evaluation

**Durée:** 1-4 heures  
**Objectif:** Évaluation complète avec CI

```bash
python -m holdem.cli.eval_blueprint \
  --policy runs/blueprint/avg_policy.json \
  --episodes 50000 \
  --use-aivat \
  --confidence 0.95 \
  --out eval_report.json
```

### 7.2 Tests spécifiques

#### 7.2.1 Vision Accuracy Test

**Objectif:** Valider précision OCR/vision

```bash
pytest tests/test_vision_accuracy.py -v
# - Dataset annoté (500 samples)
# - Card recognition > 97%
# - OCR accuracy > 97%
```

#### 7.2.2 Bucketing Stability Test

**Objectif:** Vérifier bucketing déterministe

```bash
pytest tests/test_bucketing.py -v
# - Seed fixe
# - Assigner buckets 1000 mains
# - Vérifier assignments identiques
```

#### 7.2.3 Realtime Budget Test

**Objectif:** Valider respect time budget

```bash
pytest tests/test_realtime_budget.py -v
# - 1000 décisions avec budget 80ms
# - p95 latence < 150ms
# - p99 latence < 200ms
```

#### 7.2.4 MCCFR Convergence Test

**Objectif:** Vérifier convergence MCCFR

```bash
pytest tests/test_mccfr_sanity.py -v
# - Training 10k iters simplified game
# - Stratégie finale non-uniforme
# - Exploitability décroît
```

### 7.3 CI/CD Integration

**GitHub Actions workflow:**

```yaml
name: Evaluation Tests

on: [push, pull_request]

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run smoke tests
        run: pytest tests/test_eval_smoke.py -v
        
  regression-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run regression tests
        run: pytest tests/test_eval_regression.py -v
```

---

## 8. SEUILS DE RÉGRESSION

### 8.1 Seuils d'acceptation

| Métrique | Changement acceptable | Seuil alerte | Seuil blocage |
|----------|---------------------|--------------|---------------|
| Winrate vs Random | ±5% | -10% | -20% |
| Winrate vs Tight | ±10% | -15% | -30% |
| Winrate vs LAG | ±15% | -20% | -40% |
| Vision accuracy | ±1% | -2% | -5% |
| Latency p95 | ±10% | +20% | +50% |
| Memory usage | ±15% | +30% | +50% |

### 8.2 Décisions merge

**Règles:**

1. **GREEN (merge OK)** : Toutes métriques dans acceptable
2. **YELLOW (review required)** : 1+ métriques en alerte
3. **RED (block merge)** : 1+ métriques en blocage

**Exemple:**

```python
def evaluate_merge_readiness(current_metrics, baseline_metrics):
    """Determine if changes are ready to merge."""
    
    decisions = {}
    
    for metric_name, current_value in current_metrics.items():
        baseline_value = baseline_metrics[metric_name]
        
        # Calculate % change
        pct_change = (current_value - baseline_value) / baseline_value
        
        # Apply thresholds (example for winrate)
        if abs(pct_change) < 0.05:
            decisions[metric_name] = 'GREEN'
        elif abs(pct_change) < 0.10:
            decisions[metric_name] = 'YELLOW'
        else:
            decisions[metric_name] = 'RED'
    
    # Overall decision
    if all(d == 'GREEN' for d in decisions.values()):
        return 'MERGE_OK', decisions
    elif any(d == 'RED' for d in decisions.values()):
        return 'BLOCK_MERGE', decisions
    else:
        return 'REVIEW_REQUIRED', decisions
```

---

## 9. PROTOCOLE D'EXÉCUTION

### 9.1 Procédure standard

**Étape 1: Préparer environnement**

```bash
# Nettoyer environnement
make clean

# Installer dépendances
pip install -r requirements.txt

# Vérifier installation
pytest tests/test_structure.py -v
```

**Étape 2: Baseline evaluation**

```bash
# Évaluer version baseline (main)
git checkout main
python -m holdem.cli.eval_blueprint \
  --policy runs/baseline/avg_policy.json \
  --episodes 10000 \
  --seed 42 \
  --use-aivat \
  --out eval_baseline.json
```

**Étape 3: Feature branch evaluation**

```bash
# Évaluer feature branch
git checkout feature/my-improvement
python -m holdem.cli.eval_blueprint \
  --policy runs/feature/avg_policy.json \
  --episodes 10000 \
  --seed 42 \
  --use-aivat \
  --out eval_feature.json
```

**Étape 4: Compare results**

```bash
python scripts/compare_evaluations.py \
  --baseline eval_baseline.json \
  --feature eval_feature.json \
  --out comparison_report.md
```

**Étape 5: Decision**

- Lire comparison_report.md
- Vérifier seuils de régression
- Décider: MERGE / REVIEW / BLOCK

### 9.2 Automation script

**Script:** `scripts/run_full_evaluation.sh`

```bash
#!/bin/bash
# Full evaluation protocol

set -e

echo "Starting full evaluation protocol..."

# Configuration
POLICY_PATH="runs/blueprint/avg_policy.json"
NUM_EPISODES=50000
SEED=42

# Step 1: Smoke test
echo "Step 1: Smoke test..."
pytest tests/test_eval_smoke.py -v

# Step 2: Regression test
echo "Step 2: Regression test..."
pytest tests/test_eval_regression.py -v

# Step 3: Full evaluation
echo "Step 3: Full evaluation (this may take 1-2 hours)..."
python -m holdem.cli.eval_blueprint \
  --policy "$POLICY_PATH" \
  --episodes "$NUM_EPISODES" \
  --seed "$SEED" \
  --use-aivat \
  --confidence 0.95 \
  --out eval_results.json

# Step 4: Generate report
echo "Step 4: Generating report..."
python scripts/generate_eval_report.py \
  --results eval_results.json \
  --out EVAL_REPORT.md

echo "Evaluation complete. See EVAL_REPORT.md for results."
```

---

## 11. RAPPORTS ET DOCUMENTATION

### 11.1 Format rapport standard

**Template:** `EVAL_REPORT_TEMPLATE.md`

```markdown
# Evaluation Report

**Date:** YYYY-MM-DD  
**Policy:** path/to/policy.json  
**Git commit:** abc1234  
**Seed:** 42  
**Episodes:** 50,000  

## Summary

- **Winrate vs Random:** +52.3 ± 2.1 bb/100 (CI 95%)
- **Winrate vs Tight:** +18.7 ± 3.5 bb/100
- **Winrate vs LAG:** +8.2 ± 4.2 bb/100

## Detailed Results

### Against RandomAgent

| Metric | Value | CI 95% |
|--------|-------|--------|
| Winrate (bb/100) | +52.3 | [50.2, 54.4] |
| Variance | 89.2 | - |
| AIVAT Variance | 42.1 | - |
| Variance Reduction | 52.8% | - |

### Against TightAgent

...

## Regression Analysis

| Metric | Baseline | Current | Change | Status |
|--------|----------|---------|--------|--------|
| Winrate Random | +50.1 | +52.3 | +2.2 (+4.4%) | ✅ GREEN |
| Winrate Tight | +20.3 | +18.7 | -1.6 (-7.9%) | ⚠️ YELLOW |
| Winrate LAG | +9.1 | +8.2 | -0.9 (-9.9%) | ⚠️ YELLOW |

## Conclusion

**Overall Status:** ⚠️ REVIEW REQUIRED

Slight regression against Tight and LAG agents. Investigate...
```

### 11.2 Artifacts à conserver

**Pour chaque évaluation, sauvegarder:**

1. `eval_results.json` - Résultats bruts
2. `EVAL_REPORT.md` - Rapport formatté
3. `eval_config.yaml` - Configuration utilisée
4. `policy_metadata.json` - Metadata policy (commit, config, etc.)
5. `comparison_vs_baseline.png` - Graphique comparaison

**Storage:**

```
evals/
  2025-11-08_baseline/
    eval_results.json
    EVAL_REPORT.md
    eval_config.yaml
    policy_metadata.json
  2025-11-09_feature_x/
    ...
```

---

## ANNEXE A: SCRIPTS UTILITAIRES

### A.1 Generate Evaluation Report

**Script:** `scripts/generate_eval_report.py`

```python
#!/usr/bin/env python3
"""Generate formatted evaluation report from results JSON."""

import json
import argparse
from pathlib import Path
from datetime import datetime

def generate_report(results_path: Path, output_path: Path):
    """Generate markdown report from eval results."""
    
    with open(results_path) as f:
        results = json.load(f)
    
    report = f"""# Evaluation Report

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Policy:** {results['policy_path']}
**Episodes:** {results['num_episodes']:,}
**Seed:** {results['seed']}

## Summary

"""
    
    for opponent, metrics in results['opponents'].items():
        winrate = metrics['winrate']
        ci_lower = metrics['ci_lower']
        ci_upper = metrics['ci_upper']
        
        report += f"- **Winrate vs {opponent}:** {winrate:+.1f} ± {(ci_upper - ci_lower)/2:.1f} bb/100\n"
    
    report += "\n## Detailed Results\n\n"
    
    # Add detailed sections...
    
    output_path.write_text(report)
    print(f"Report generated: {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('EVAL_REPORT.md'))
    args = parser.parse_args()
    
    generate_report(args.results, args.out)
```

### A.2 Compare Evaluations

**Script:** `scripts/compare_evaluations.py`

```python
#!/usr/bin/env python3
"""Compare two evaluation results."""

import json
import argparse
from pathlib import Path

def compare_evaluations(baseline_path: Path, feature_path: Path, output_path: Path):
    """Compare two evaluations and generate report."""
    
    with open(baseline_path) as f:
        baseline = json.load(f)
    
    with open(feature_path) as f:
        feature = json.load(f)
    
    report = "# Evaluation Comparison\n\n"
    report += f"**Baseline:** {baseline['policy_path']}\n"
    report += f"**Feature:** {feature['policy_path']}\n\n"
    report += "| Opponent | Baseline (bb/100) | Feature (bb/100) | Change | Status |\n"
    report += "|----------|-------------------|------------------|--------|--------|\n"
    
    for opponent in baseline['opponents'].keys():
        baseline_wr = baseline['opponents'][opponent]['winrate']
        feature_wr = feature['opponents'][opponent]['winrate']
        change = feature_wr - baseline_wr
        pct_change = (change / abs(baseline_wr)) * 100 if baseline_wr != 0 else 0
        
        # Determine status
        if abs(pct_change) < 5:
            status = "✅ GREEN"
        elif abs(pct_change) < 10:
            status = "⚠️ YELLOW"
        else:
            status = "❌ RED"
        
        report += f"| {opponent} | {baseline_wr:+.1f} | {feature_wr:+.1f} | {change:+.1f} ({pct_change:+.1f}%) | {status} |\n"
    
    output_path.write_text(report)
    print(f"Comparison report generated: {output_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--feature', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('comparison_report.md'))
    args = parser.parse_args()
    
    compare_evaluations(args.baseline, args.feature, args.out)
```

---

## ANNEXE B: RÉFÉRENCES

1. **Brown & Sandholm (2019).** "Superhuman AI for multiplayer poker" - Science 365(6456):885-890
   - Section "Evaluation" dans supplementary materials
   - AIVAT description et validation

2. **Johanson et al. (2011).** "Evaluating State-Space Abstractions in Extensive-Form Games"
   - Métriques d'évaluation poker AI
   - Exploitability mesure

3. **Efron & Tibshirani (1994).** "An Introduction to the Bootstrap"
   - Bootstrap confidence intervals
   - Non-parametric statistics

4. **Cohen (1988).** "Statistical Power Analysis for the Behavioral Sciences"
   - Effect sizes (Cohen's d)
   - Sample size calculations

---

**Version:** 1.0  
**Dernière mise à jour:** 2025-11-08  
**Maintenu par:** montana2ab
