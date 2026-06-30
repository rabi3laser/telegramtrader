# 🚀 INTERFACE WEB STREAMLIT - GUIDE COMPLET v3.0

## 📋 Vue d'ensemble

Interface web optimisée pour la recherche, calibration et gestion de canaux Telegram de trading.

### ✨ Fonctionnalités principales

1. **🔑 Connexion Telegram sécurisée**
   - Authentification par numéro de téléphone + code SMS
   - Session persistante via StringSession

2. **📚 Mes Canaux**
   - Affichage de tous vos canaux déjà calibrés
   - Winrates et scores visibles immédiatement
   - Recalibration possible à tout moment
   - Export/Import JSON pour sauvegarder entre sessions

3. **🔍 Recherche de Nouveaux Canaux**
   - Recherche par marché prédéfini (Gold, Nasdaq, Crude Oil, S&P 500)
   - Recherche personnalisée avec vos propres mots-clés
   - Indication des canaux déjà calibrés dans les résultats

4. **⚙️ Calibration**
   - Analyse des messages Telegram via votre session personnelle
   - Calcul du score (0-100) et du winrate
   - Sauvegarde automatique dans `calibration_history.json`

5. **🔧 Mode Pro**
   - Paramètres avancés de recherche et calibration

---

## 🏗️ Architecture

```
projet/
├── pipeline_ui_optimized.py      # Interface Streamlit principale (v3.0)
├── telegram_authenticator.py     # Authentification Telegram (SMS)
├── telegram_search.py            # Module de recherche Telegram
├── telegram_calibrator.py        # Module de calibration
├── signal_detector.py            # Détection de signaux trading
├── calibration_history.json      # Base de données locale des canaux calibrés
├── requirements.txt              # Dépendances Python
├── .streamlit/
│   ├── secrets.toml              # Secrets (NE PAS COMMITER)
│   └── secrets.toml.example      # Exemple de configuration
└── README_STREAMLIT.md           # Ce fichier
```

---

## 🛠️ Installation

### 1. Installer les dépendances

```bash
cd C:\Users\Admin\Desktop\projet
pip install -r requirements.txt
```

### 2. Configuration des Secrets

Créez le fichier `.streamlit/secrets.toml` :

```toml
[telegram]
api_id = "26848264"
api_hash = "da038e8c2be2ee1530bbd75fea679ff6"
```

### 3. Lancer l'application

```bash
streamlit run pipeline_ui_optimized.py
```

L'interface s'ouvrira automatiquement : `http://localhost:8501`

---

## ☁️ Déploiement sur Streamlit Cloud

### Étape 1: Pousser sur GitHub

```bash
git add .
git commit -m "Mise à jour interface"
git push origin main
```

### Étape 2: Déployer sur Streamlit Cloud

1. Allez sur : https://share.streamlit.io/
2. Connectez-vous avec GitHub
3. Cliquez sur **"New app"**
4. Sélectionnez :
   - Repository: `rabi3laser/telegramtrader`
   - Branch: `main`
   - Main file: `projet/pipeline_ui_optimized.py`

### Étape 3: Configurer les Secrets

Dans Streamlit Cloud → Settings → Secrets :

```toml
[telegram]
api_id = "26848264"
api_hash = "da038e8c2be2ee1530bbd75fea679ff6"
```

---

## 🎯 Workflow Complet

### Étape 0 : Connexion Telegram
- Entrez votre numéro de téléphone (format international : +33...)
- Recevez le code par SMS
- Entrez le code → Connexion établie

### Étape 1 : Accueil - Mes Canaux
- Visualisez tous vos canaux déjà calibrés avec leurs **winrates**
- Couleurs : 🟢 ≥70% | 🟡 50-70% | 🔴 <50%
- Bouton **🔄 Recalibrer** pour mettre à jour un canal
- Bouton **🗑️** pour supprimer un canal de la liste
- **Export JSON** pour sauvegarder vos données
- **Import JSON** pour restaurer vos données

### Étape 2 : Recherche de Nouveaux Canaux
- Sélectionnez un marché ou entrez des mots-clés personnalisés
- Les canaux déjà calibrés sont marqués 📌 et non sélectionnables
- Cochez les canaux qui vous intéressent

### Étape 3 : Sélection
- Validez votre sélection
- Supprimez les canaux indésirables
- Estimation du temps de calibration

### Étape 4 : Calibration
- **Déclenché manuellement** par l'utilisateur
- Utilise votre session Telegram personnelle
- Analyse les messages et calcule le score/winrate
- **Sauvegarde automatique** dans `calibration_history.json`

### Étape 5 : Résultats
- Canaux activés (score ≥ 70)
- Canaux en test court (score 50-70)
- Canaux rejetés avec raison détaillée
- Export CSV du rapport complet

---

## 💾 Persistance des Données

### Fichier `calibration_history.json`

Ce fichier stocke tous vos canaux calibrés :

```json
{
  "channels": {
    "gold_signals_pro": {
      "username": "gold_signals_pro",
      "title": "Gold Signals Pro",
      "market": "gold_mgc",
      "status": "activated",
      "score": 82,
      "winrate": 82,
      "signals_count": 25,
      "metrics": {
        "total_messages": 200,
        "total_signals": 25,
        "signals_per_day": 2.5,
        "avg_quality": 7.2,
        "hours_since_last_signal": 3.5
      },
      "date_calibration": "2026-06-30T02:50:00"
    }
  },
  "last_updated": "2026-06-30T02:50:00"
}
```

### ⚠️ Important pour Streamlit Cloud

Sur Streamlit Cloud, le système de fichiers est **éphémère** :
- Le fichier `calibration_history.json` est réinitialisé à chaque redéploiement
- **Solution** : Utilisez le bouton **📥 Exporter mes canaux (JSON)** pour sauvegarder
- Puis **📤 Importer canaux (JSON)** pour restaurer après redéploiement

### Pour la Production

Pour une persistance permanente, envisagez :
- **Option A** : Streamlit Community Cloud + fichier JSON exporté/importé manuellement
- **Option B** : Base de données externe (Supabase, Firebase, etc.)
- **Option C** : Déploiement local sur votre machine (persistance native)

---

## 🔧 Mode Pro

Activez le Mode Pro dans la sidebar pour :

**Recherche avancée :**
- Filtres de membres (min/max)

**Calibration avancée :**
- Nombre de messages à analyser (min/cible)
- Seuil de signaux minimum
- Winrate minimum requis

---

## 📊 Interprétation des Scores

| Score | Statut | Signification |
|-------|--------|---------------|
| ≥ 70 | ✅ Activé | Canal de qualité, prêt pour le trading |
| 50-69 | ⏳ Test Court | Canal prometteur, à surveiller |
| < 50 | ❌ Rejeté | Canal insuffisant |

### Critères de scoring (0-100 points)

| Critère | Poids | Description |
|---------|-------|-------------|
| Nombre de signaux | 30% | ≥30 signaux = 30 pts |
| Fréquence | 25% | ≥3 signaux/jour = 25 pts |
| Qualité moyenne | 20% | Note /10 des signaux |
| Récence | 15% | Dernier signal < 6h = 15 pts |
| Diversité marchés | 5% | Nombre de marchés couverts |
| Membres | 5% | ≥5000 membres = 5 pts |

---

## 🚨 Dépannage

### "Veuillez d'abord vous connecter à Telegram"
➡️ Retournez à l'étape 0 et reconnectez-vous

### "Erreur lors de la recherche"
➡️ Vérifiez votre connexion Telegram (étape 0)

### "Aucun canal trouvé"
➡️ Essayez d'autres mots-clés ou le mode "Recherche personnalisée"

### "Calibration échoue"
➡️ Vérifiez que vous êtes membre du canal à calibrer

### "Mes canaux ont disparu après redéploiement"
➡️ Exportez vos canaux en JSON avant chaque redéploiement et réimportez-les

---

## 🔐 Sécurité

- ❌ Ne commitez JAMAIS votre `secrets.toml` sur GitHub
- ❌ Ne partagez JAMAIS votre session Telegram
- ✅ Utilisez les Secrets Streamlit Cloud
- ✅ Le fichier `.streamlit/secrets.toml` est dans `.gitignore`
- ✅ `calibration_history.json` ne contient pas de données sensibles

---

**Version :** 3.0 - Mes Canaux + Persistance + Navigation complète
**Date :** 30/06/2026