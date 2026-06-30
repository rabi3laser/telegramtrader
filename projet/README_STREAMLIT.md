# 🚀 INTERFACE WEB STREAMLIT - GUIDE COMPLET

## 📋 Vue d'ensemble

Interface web optimisée pour la recherche et calibration de canaux Telegram de trading.

### ✨ Fonctionnalités principales

1. **🔍 Recherche intelligente**
   - Recherche par marché prédéfini (Gold, Nasdaq, Crude Oil, S&P 500)
   - Recherche personnalisée avec vos propres mots-clés
   - Mots-clés enrichis multi-langues (20+ par marché)
   - Recherche RÉELLE via Telegram API (pas de données de démo)

2. **✅ Sélection manuelle**
   - Choisissez uniquement les canaux qui vous intéressent
   - Évitez le gaspillage de ressources OCR

3. **⚙️ Calibration optimisée**
   - OCR uniquement sur les canaux sélectionnés
   - Analyse de performance (winrate, nombre de signaux)
   - Classification automatique (Activé/Test/Rejeté)

4. **🔧 Mode Pro**
   - Paramètres avancés de recherche
   - Contrôle fin de la calibration
   - Pour utilisateurs expérimentés

---

## 🛠️ Installation

### 1. Installer les dépendances

```bash
cd C:\Users\Admin\Desktop\projet
pip install -r requirements.txt
```

### 2. Générer votre StringSession Telegram

**IMPORTANT:** Vous devez faire ceci UNE SEULE FOIS localement.

```bash
python generate_session.py
```

Suivez les instructions :
1. Entrez votre numéro de téléphone : `+212648955924`
2. Ouvrez l'app Telegram pour voir le code (PAS par SMS !)
3. Entrez le code dans le terminal
4. **COPIEZ** la StringSession affichée

### 3. Configuration locale (pour tester)

Créez le fichier `.streamlit/secrets.toml` :

```toml
TELEGRAM_API_ID = "29149167"
TELEGRAM_API_HASH = "d1942abd0a5a7c764d96a8a4b640893e"
TELEGRAM_STRING_SESSION = "VOTRE_STRING_SESSION_ICI"
```

### 4. Lancer l'application

```bash
streamlit run pipeline_ui_optimized.py
```

L'interface s'ouvrira automatiquement dans votre navigateur : `http://localhost:8501`

---

## ☁️ Déploiement sur Streamlit Cloud

### Étape 1: Préparer GitHub

```bash
# Ajouter les nouveaux fichiers
git add pipeline_ui_optimized.py telegram_search.py requirements.txt
git add .streamlit/secrets.toml.example GUIDE_TELEGRAM_SETUP.md
git commit -m "Interface Streamlit avec recherche Telegram réelle"
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

Dans Streamlit Cloud :
1. Allez dans **Settings** → **Secrets**
2. Collez :

```toml
TELEGRAM_API_ID = "29149167"
TELEGRAM_API_HASH = "d1942abd0a5a7c764d96a8a4b640893e"
TELEGRAM_STRING_SESSION = "VOTRE_STRING_SESSION_GENEREE"
```

3. Cliquez sur **Save**
4. L'application redémarrera automatiquement

---

## 🎯 Utilisation

### Workflow en 4 étapes

#### 1️⃣ Recherche de canaux

**Mode Marchés Prédéfinis:**
- Sélectionnez un marché (Gold, Nasdaq, Crude Oil, S&P 500)
- Cliquez sur "LANCER LA RECHERCHE"
- Les résultats utilisent des mots-clés enrichis :
  - **Gold:** gold, XAUUSD, XAU, or, lingot, gold signals, etc.
  - **Nasdaq:** nasdaq, NQ, MNQ, nasdaq 100, QQQ, tech futures, etc.
  - **Crude Oil:** crude oil, CL, MCL, WTI, oil signals, pétrole, etc.
  - **S&P 500:** S&P 500, ES, MES, SPX, SPY, indices, etc.

**Mode Recherche Personnalisée:**
- Entrez vos propres mots-clés (un par ligne)
- Exemple pour Bitcoin :
  ```
  bitcoin
  BTC
  crypto signals
  bitcoin trading
  ```
- Recherchez N'IMPORTE QUEL marché !

#### 2️⃣ Sélection manuelle

- Cochez les canaux qui vous intéressent
- Visualisez : membres, activité, description
- Badge ✅ pour les canaux vérifiés

#### 3️⃣ Calibration

- OCR uniquement sur les canaux sélectionnés
- Analyse de performance
- Classification automatique

#### 4️⃣ Résultats

- Canaux activés (prêts pour trading)
- Canaux en test court
- Canaux rejetés
- Téléchargement du rapport CSV

---

## 🔧 Mode Pro

Activez le Mode Pro dans la sidebar pour :

**Recherche avancée:**
- Filtres de membres (min/max)
- Mots-clés personnalisés supplémentaires

**Calibration avancée:**
- Nombre de messages à analyser
- Critères de winrate minimum
- Paramètres OCR (batch size, timeout)

---

## 📊 Exemples de recherche

### Recherche Gold (mots-clés enrichis)

```
Anglais: gold, gold signals, XAUUSD, XAU, xau/usd, MGC, GC futures, 
         gold trading, gold forex, gold analysis

Français: or, or signals, lingot, analyse or, signaux or, trading or
```

### Recherche Nasdaq (mots-clés enrichis)

```
Anglais: nasdaq, NQ, MNQ, nasdaq 100, QQQ, tech futures, 
         nasdaq signals, tech index

Français: nasdaq signaux, indices tech
```

### Recherche personnalisée Bitcoin

```
bitcoin
BTC
crypto signals
bitcoin trading
cryptocurrency
BTC/USD
bitcoin analysis
```

---

## 🚨 Dépannage

### "Erreur lors de la recherche"

➡️ **Vérifiez votre StringSession**
- Dans Streamlit Cloud : Settings → Secrets
- Localement : `.streamlit/secrets.toml`
- La StringSession doit être valide et complète

### "Aucun canal trouvé"

➡️ **Essayez d'autres mots-clés**
- Utilisez le mode "Recherche personnalisée"
- Ajoutez des variantes (anglais + français)
- Élargissez les critères

### "L'application ne démarre pas"

➡️ **Vérifiez les dépendances**
```bash
pip install -r requirements.txt
```

---

## 📁 Structure des fichiers

```
projet/
├── pipeline_ui_optimized.py      # Interface Streamlit principale
├── telegram_search.py            # Module de recherche Telegram
├── generate_session.py           # Générateur de StringSession
├── requirements.txt              # Dépendances Python
├── .streamlit/
│   └── secrets.toml.example      # Exemple de configuration
├── GUIDE_TELEGRAM_SETUP.md       # Guide configuration Telegram
├── INSTRUCTIONS_SESSION.md       # Instructions StringSession
└── README_STREAMLIT.md           # Ce fichier
```

---

## 🔐 Sécurité

**IMPORTANT:**
- ❌ Ne commitez JAMAIS votre StringSession sur GitHub
- ❌ Ne partagez JAMAIS votre StringSession publiquement
- ✅ Utilisez les Secrets Streamlit Cloud
- ✅ Ajoutez `.streamlit/secrets.toml` au `.gitignore`

---

## 🎉 Avantages de cette solution

### ✅ Recherche réelle
- Pas de données de démo
- Résultats en temps réel depuis Telegram
- Mots-clés enrichis multi-langues

### ✅ Flexibilité totale
- 4 marchés prédéfinis
- Recherche personnalisée pour N'IMPORTE QUEL marché
- Mode Pro pour utilisateurs avancés

### ✅ Optimisation des ressources
- OCR uniquement sur canaux sélectionnés
- Pas de gaspillage de temps/ressources
- Workflow en 4 étapes claires

### ✅ Déploiement facile
- Streamlit Cloud gratuit
- Configuration simple via Secrets
- Accessible depuis n'importe où

---

## 📞 Support

Pour toute question :
1. Consultez `GUIDE_TELEGRAM_SETUP.md`
2. Consultez `INSTRUCTIONS_SESSION.md`
3. Vérifiez les logs Streamlit Cloud

---

**Version:** 2.0 - Optimisée avec recherche Telegram réelle  
**Date:** 28/06/2026  
**Auteur:** Pipeline Trading Team
