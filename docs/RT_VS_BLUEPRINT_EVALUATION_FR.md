# Évaluation RT Search vs Blueprint avec IC95 Bootstrap

## Vue d'ensemble

Ce système évalue la différence de valeur attendue (EVΔ) entre la recherche en temps réel (RT search) et la stratégie blueprint, avec :

1. **Intervalles de confiance bootstrap à 95%** pour la rigueur statistique
2. **Public card sampling (16-64 échantillons)** pour réduire la variance
3. **Mesures de latence** pour évaluer le coût computationnel

## Exigences

### 1. Mesurer EVΔ du RT search vs blueprint avec bootstrap CI95 (doit être > 0)

✅ **Implémenté** : `tools/eval_rt_vs_blueprint.py`

- Compare la performance de la recherche RT vs stratégie blueprint pure
- Calcule EVΔ (RT - blueprint) en bb/100 mains
- Utilise la méthode bootstrap pour les intervalles de confiance à 95%
- Valide que EVΔ > 0 avec significativité statistique (p < 0.05)

### 2. Activer public-card sampling (16–64 samples) + mesurer variance/latence

✅ **Implémenté** : Configuration via `SearchConfig.samples_per_solve`

- Teste avec 16, 32, et 64 échantillons
- Mesure la réduction de variance
- Mesure l'impact sur la latence

## Utilisation

### Évaluation de base (sans sampling)

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 1000 \
    --samples-per-solve 1 \
    --output results/baseline.json
```

### Avec 16 échantillons

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 1000 \
    --samples-per-solve 16 \
    --output results/16samples.json
```

### Avec 32 échantillons

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 1000 \
    --samples-per-solve 32 \
    --output results/32samples.json
```

### Avec 64 échantillons

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 1000 \
    --samples-per-solve 64 \
    --output results/64samples.json
```

### Tester plusieurs configurations

```bash
python tools/eval_rt_vs_blueprint.py \
    --policy runs/blueprint/avg_policy.json \
    --hands 500 \
    --test-sample-counts 1,16,32,64 \
    --output results/comparison.json
```

## Format de sortie

### Console

```
======================================================================
RÉSULTATS D'ÉVALUATION RT SEARCH vs BLUEPRINT
======================================================================

Configuration:
  Mains totales:     2000
  Échantillons:      16

Différence de valeur attendue (RT - Blueprint):
  EVΔ:              +3.25 bb/100
  IC 95%:           [+1.12, +5.38]
  Marge:            ±2.13 bb/100
  p-value:          0.0023

  ✅ SIGNIFICATIF: RT search est statistiquement meilleur que blueprint (p < 0.05)

Statistiques de latence:
  Moyenne:          85.32 ms
  Médiane (p50):    78.15 ms
  p95:              145.78 ms
  p99:              210.43 ms

======================================================================
```

### JSON

```json
{
  "configuration": {
    "policy": "runs/blueprint/avg_policy.json",
    "hands": 1000,
    "samples_per_solve": 16,
    "time_budget_ms": 80,
    "seed": 42
  },
  "result": {
    "total_hands": 2000,
    "samples_per_solve": 16,
    "ev_delta_bb100": 3.25,
    "ci_lower": 1.12,
    "ci_upper": 5.38,
    "ci_margin": 2.13,
    "is_significant": true,
    "p_value": 0.0023,
    "mean_rt_latency_ms": 85.32,
    "p50_latency_ms": 78.15,
    "p95_latency_ms": 145.78,
    "p99_latency_ms": 210.43
  }
}
```

## Interprétation des résultats

### EVΔ (Différence de valeur attendue)

| EVΔ (bb/100) | Interprétation |
|--------------|----------------|
| > +5.0 | Excellent amélioration |
| +2.0 à +5.0 | Bonne amélioration |
| +0.5 à +2.0 | Amélioration modérée |
| -0.5 à +0.5 | Pas de différence significative |
| < -0.5 | Régression (RT pire que blueprint) |

### Significativité statistique

**Exemple 1: Positif significatif** ✅
```
EVΔ: +3.25 bb/100
IC 95%: [+1.12, +5.38]
p-value: 0.0023
Résultat: RT search est significativement meilleur
```

**Exemple 2: Non significatif** ⚠️
```
EVΔ: +1.50 bb/100
IC 95%: [-0.23, +3.23]
p-value: 0.088
Résultat: Impossible de conclure (IC contient 0)
```

**Exemple 3: Négatif significatif** ❌
```
EVΔ: -2.10 bb/100
IC 95%: [-3.85, -0.35]
p-value: 0.019
Résultat: RT search est significativement pire (régression!)
```

## Configuration du sampling

### Paramètres recommandés

| Cas d'usage | Échantillons | Budget temps | Latence attendue |
|-------------|--------------|--------------|------------------|
| Jeu rapide en ligne | 1 | 80ms | ~80ms |
| Équilibré | 16 | 800ms | ~800ms |
| Haute qualité | 32 | 1600ms | ~1.6s |
| Analyse | 64 | 3200ms | ~3.2s |

### Code de configuration

```python
from holdem.types import SearchConfig

# Sans sampling (baseline)
config = SearchConfig(
    time_budget_ms=80,
    samples_per_solve=1
)

# 16 échantillons
config = SearchConfig(
    time_budget_ms=800,
    samples_per_solve=16
)

# 32 échantillons
config = SearchConfig(
    time_budget_ms=1600,
    samples_per_solve=32
)

# 64 échantillons
config = SearchConfig(
    time_budget_ms=3200,
    samples_per_solve=64
)
```

## Métriques mesurées

### Métriques EVΔ

- **ev_delta_bb100**: Différence EV en grosses blindes par 100 mains
- **ci_lower**: Borne inférieure de l'IC à 95%
- **ci_upper**: Borne supérieure de l'IC à 95%
- **ci_margin**: Marge d'erreur (±)
- **is_significant**: Vrai si significatif à p < 0.05
- **p_value**: p-value bilatérale

### Métriques de latence

- **mean_rt_latency_ms**: Temps de décision moyen
- **p50_latency_ms**: Médiane (50e percentile)
- **p95_latency_ms**: 95e percentile (valeurs aberrantes)
- **p99_latency_ms**: 99e percentile (pire cas)

### Métriques de variance (optionnel)

- **strategy_variance**: Distance L2 entre stratégies
- **variance_reduction_pct**: Réduction de variance en % vs baseline

## Tests

### Exécuter les tests

```bash
# Installer les dépendances (si nécessaire)
pip install -r requirements.txt

# Tests RT vs blueprint
pytest tests/test_eval_rt_vs_blueprint.py -v

# Tests de sampling étendus (avec sortie détaillée)
pytest tests/test_public_card_sampling_extended.py -v -s
```

### Suites de tests

1. **test_eval_rt_vs_blueprint.py**
   - Tests du simulateur de poker
   - Tests des structures de résultats
   - Tests de l'évaluation principale
   - Tests de comparaison de sampling
   - Tests des IC bootstrap

2. **test_public_card_sampling_extended.py**
   - Tests avec 16, 32, 64 échantillons
   - Validation du scaling de latence
   - Mesure de réduction de variance
   - Métriques de performance complètes

## Résultats attendus

### EVΔ attendu

- **RT search devrait être meilleur que blueprint** (EVΔ > 0)
- RT s'adapte aux tendances de l'adversaire
- Blueprint est statique, exploitable
- **EVΔ attendu: +2 à +10 bb/100**

### Sampling attendu

**Réduction de variance:**
- Plus d'échantillons → variance plus faible
- Réduction attendue: 20-50% avec 16-64 échantillons
- Dépend de la qualité de l'implémentation CFR

**Scaling de latence:**
- Devrait évoluer approximativement linéairement
- Overhead par échantillon: < 2x baseline
- 16 échantillons: ~800ms (pas 16 * 80ms = 1280ms)
- Meilleur que linéaire grâce au caching

## Résumé de l'implémentation

✅ **Exigence 1: Mesurer EVΔ avec IC95 bootstrap (doit être > 0)**
- Implémenté dans `tools/eval_rt_vs_blueprint.py`
- Calcule EVΔ (RT - blueprint) en bb/100
- Utilise bootstrap pour IC à 95%
- Teste la significativité statistique

✅ **Exigence 2: Public-card sampling (16-64) + variance/latence**
- Configuration via `SearchConfig.samples_per_solve`
- Tests avec 16, 32, 64 échantillons
- Mesure variance et latence
- Tests complets dans `test_public_card_sampling_extended.py`

## Références

1. **EVAL_PROTOCOL.md** - Protocole d'évaluation interne
2. **PUBLIC_CARD_SAMPLING_GUIDE.md** - Guide d'implémentation du sampling
3. **docs/RT_VS_BLUEPRINT_EVALUATION.md** - Documentation complète (anglais)
