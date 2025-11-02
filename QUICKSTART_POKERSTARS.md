# Quick Start: PokerStars sur macOS / PokerStars on macOS

## 🇫🇷 Français

### Configuration Rapide (5 minutes)

1. **Accorder les Permissions macOS**
   - Ouvrir: Préférences Système → Sécurité et Confidentialité → Confidentialité
   - Sélectionner "Enregistrement d'écran"
   - Ajouter Terminal.app à la liste
   - Redémarrer Terminal

2. **Ouvrir PokerStars**
   - Lancer PokerStars
   - Rejoindre une table Hold'em No Limit 9 joueurs
   - Laisser la fenêtre visible

3. **Exécuter la Calibration**
   ```bash
   python -m holdem.cli.profile_wizard \
     --window-title "Hold'em" \
     --owner-name "PokerStars" \
     --out assets/table_profiles/pokerstars.json
   ```

4. **Vérifier**
   - Vérifier que le profil a été créé: `ls assets/table_profiles/pokerstars*`
   - Vous devriez voir 3 fichiers: `.json`, `_reference.npy`, `_descriptors.npy`

### Problème?

- **Fenêtre non trouvée?** → Vérifier les permissions ci-dessus
- **Besoin d'aide?** → Lire [POKERSTARS_SETUP.md](POKERSTARS_SETUP.md)
- **Documentation complète** → Lire [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md)

### Prochaines Étapes

Voir [README.md](README.md) pour:
1. Construire les buckets d'abstraction
2. Entraîner la stratégie blueprint
3. Tester en mode dry-run

---

## 🇬🇧 English

### Quick Setup (5 minutes)

1. **Grant macOS Permissions**
   - Open: System Preferences → Security & Privacy → Privacy
   - Select "Screen Recording"
   - Add Terminal.app to the list
   - Restart Terminal

2. **Open PokerStars**
   - Launch PokerStars
   - Join a Hold'em No Limit 9-player table
   - Keep the window visible

3. **Run Calibration**
   ```bash
   python -m holdem.cli.profile_wizard \
     --window-title "Hold'em" \
     --owner-name "PokerStars" \
     --out assets/table_profiles/pokerstars.json
   ```

4. **Verify**
   - Check that the profile was created: `ls assets/table_profiles/pokerstars*`
   - You should see 3 files: `.json`, `_reference.npy`, `_descriptors.npy`

### Issues?

- **Window not found?** → Check permissions above
- **Need help?** → Read [POKERSTARS_SETUP.md](POKERSTARS_SETUP.md)
- **Full documentation** → Read [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md)

### Next Steps

See [README.md](README.md) for:
1. Building abstraction buckets
2. Training blueprint strategy
3. Testing in dry-run mode

---

## 📋 Commandes Utiles / Useful Commands

```bash
# Lister les fenêtres disponibles / List available windows
python list_windows.py --filter "stars"

# Utiliser le modèle pré-configuré / Use pre-configured template
cp assets/table_profiles/pokerstars_nlhe_9max_template.json \
   assets/table_profiles/pokerstars.json

# Vérifier le profil / Check profile
cat assets/table_profiles/pokerstars.json | head -20
```

## 📚 Documentation

- 🚀 **Démarrage Rapide / Quick Start**: Ce fichier / This file
- 🎯 **PokerStars Spécifique / PokerStars Specific**: [POKERSTARS_SETUP.md](POKERSTARS_SETUP.md)
- 📖 **Guide Complet / Complete Guide**: [CALIBRATION_GUIDE.md](CALIBRATION_GUIDE.md)
- 💻 **Documentation Générale / General Docs**: [README.md](README.md)
