# 🔐 GUIDE DE CONFIGURATION TELEGRAM POUR STREAMLIT

Ce guide explique comment configurer la recherche Telegram réelle dans l'interface Streamlit.

## 📋 Vue d'ensemble

L'interface utilise maintenant **Telethon** pour faire de vraies recherches Telegram avec des mots-clés spécifiques à chaque marché :

- **Gold (MGC)** : `XAUUSD`, `gold signals`, `MGC`, `gold trading`...
- **Nasdaq (MNQ)** : `nasdaq signals`, `NQ`, `MNQ`, `nasdaq futures`...
- **Crude Oil (MCL)** : `crude oil signals`, `MCL`, `WTI`, `oil trading`...
- **S&P 500 (MES)** : `sp500 signals`, `MES`, `ES futures`, `s&p 500`...

## 🚀 Étape 1 : Générer votre StringSession (LOCAL - UNE SEULE FOIS)

### 1.1 Prérequis

Assurez-vous d'avoir vos identifiants Telegram API :
- **API ID** : Obtenu sur https://my.telegram.org
- **API Hash** : Obtenu sur https://my.telegram.org
- **Numéro de téléphone** : Votre numéro Telegram

### 1.2 Créer le fichier .env (si pas déjà fait)

Créez un fichier `.env` dans le dossier `projet/` :

```env
TELEGRAM_API_ID=votre_api_id
TELEGRAM_API_HASH=votre_api_hash
TELEGRAM_PHONE=+33612345678
```

### 1.3 Exécuter le générateur de session

```bash
cd projet
python generate_session.py
```

**Ce qui va se passer :**
1. Le script vous demandera votre numéro de téléphone
2. Vous recevrez un code SMS sur Telegram
3. Entrez le code
4. Le script affichera votre **StringSession** (une longue chaîne de caractères)

**Exemple de sortie :**
```
======================================================================
  GÉNÉRATEUR DE STRING SESSION TELEGRAM
======================================================================

Votre StringSession (à copier dans Streamlit Secrets):
----------------------------------------------------------------------
1BVtsOKIBu5pn3qF8xYzMjY4NDgyNjQ6QUFGdGRhMDM4ZThjMmJlMmVlMTUzMGJiZDc1ZmVhNjc5ZmY2...
----------------------------------------------------------------------
```

**⚠️ IMPORTANT :** 
- Copiez cette StringSession dans un endroit sûr
- Ne la partagez JAMAIS publiquement
- Vous n'aurez à faire cette étape qu'UNE SEULE FOIS

## 🌐 Étape 2 : Configurer Streamlit Cloud Secrets

### 2.1 Accéder aux Secrets

1. Allez sur https://share.streamlit.io
2. Cliquez sur votre app `telegramtrader`
3. Cliquez sur **⚙️ Settings** (en haut à droite)
4. Cliquez sur **Secrets** dans le menu de gauche

### 2.2 Ajouter les Secrets

Copiez-collez ce contenu dans l'éditeur de Secrets :

```toml
[telegram]
api_id = "26848264"
api_hash = "da038e8c2be2ee1530bbd75fea679ff6"
session_string = "COLLEZ_ICI_VOTRE_STRING_SESSION_GENEREE"
```

**Remplacez :**
- `api_id` : Votre API ID (si différent)
- `api_hash` : Votre API Hash (si différent)
- `session_string` : La StringSession générée à l'étape 1.3

### 2.3 Sauvegarder

Cliquez sur **Save** en bas de la page.

## ✅ Étape 3 : Vérifier que ça fonctionne

### 3.1 Redémarrer l'app

Streamlit Cloud va automatiquement redémarrer l'app après avoir sauvegardé les Secrets.

### 3.2 Tester la recherche

1. Allez sur votre app Streamlit
2. Sélectionnez un marché (ex: **Nasdaq (MNQ)**)
3. Cliquez sur **🔍 LANCER LA RECHERCHE**
4. Vous devriez maintenant voir de **vrais canaux Nasdaq** au lieu des canaux Gold de démo !

**Résultat attendu :**
```
📊 Résultats de la Recherche
5 canaux trouvés - Cochez ceux que vous voulez calibrer:

✅ Nasdaq Futures Signals
@nasdaqfutures
Membres: 12,450
🟢 Très actif
Professional NQ trading signals...

✅ MNQ Trading Pro
@mnqtradingpro
Membres: 8,920
🟡 Actif
Micro Nasdaq futures analysis...
```

## 🔧 Dépannage

### Problème : "Erreur d'authentification"

**Solution :** Votre StringSession est peut-être expirée ou invalide.
1. Régénérez une nouvelle StringSession avec `generate_session.py`
2. Mettez à jour les Secrets Streamlit
3. Redémarrez l'app

### Problème : "Aucun canal trouvé"

**Causes possibles :**
1. Les critères de filtrage sont trop stricts (MIN_MEMBERS=1000, MAX_MEMBERS=50000)
2. Les mots-clés ne correspondent à aucun canal actif
3. Rate limiting Telegram (attendez quelques minutes)

**Solution :** Ajustez les paramètres dans le Mode Pro de l'interface.

### Problème : "Module 'telethon' not found"

**Solution :** Le fichier `requirements.txt` doit contenir :
```
streamlit>=1.28.0
pandas>=2.0.0
plotly>=5.17.0
telethon>=1.34.0
python-dotenv>=1.0.0
```

Streamlit Cloud installera automatiquement ces dépendances.

## 📊 Mots-clés par Marché

Les mots-clés sont définis dans `telegram_search.py` :

### Gold (MGC)
```python
"gold signals", "XAUUSD", "MGC", "gold trade", "gold forex",
"gold trading", "xauusd signals", "gold pips", "forex gold",
"gold futures", "gold analysis"
```

### Nasdaq (MNQ)
```python
"nasdaq signals", "NQ", "MNQ", "nasdaq futures", "nasdaq 100",
"nasdaq trading", "NQ signals", "tech futures", "nasdaq analysis",
"nasdaq forex", "nasdaq pips"
```

### Crude Oil (MCL)
```python
"crude oil signals", "MCL", "WTI", "oil trading", "crude futures",
"oil signals", "CL futures", "crude oil forex", "oil analysis",
"petroleum signals", "energy trading"
```

### S&P 500 (MES)
```python
"sp500 signals", "MES", "ES futures", "s&p 500", "spx signals",
"sp500 trading", "ES signals", "index futures", "sp500 analysis",
"s&p forex", "spy signals"
```

## 🔒 Sécurité

### ✅ Bonnes pratiques

- ✅ StringSession stockée dans Streamlit Secrets (chiffrés)
- ✅ Pas de credentials dans le code source
- ✅ `.env` dans `.gitignore`
- ✅ Session réutilisable (pas besoin de code SMS à chaque fois)

### ❌ À NE JAMAIS FAIRE

- ❌ Commiter la StringSession dans Git
- ❌ Partager votre StringSession publiquement
- ❌ Mettre les credentials en dur dans le code
- ❌ Publier votre `.env` sur GitHub

## 📝 Notes Techniques

### Pourquoi StringSession ?

- **Pas de fichier session** : Streamlit Cloud est éphémère, les fichiers sont perdus au redémarrage
- **Pas de code SMS** : La StringSession permet de se reconnecter sans re-authentification
- **Portable** : Une simple chaîne de texte facile à stocker dans les Secrets

### Limites de l'API Telegram

- **Rate limiting** : Maximum ~20 recherches par minute
- **Flood wait** : Si trop de requêtes, Telegram peut vous bloquer temporairement
- **Délais** : Le code ajoute des `sleep(1)` entre les recherches pour éviter le rate limiting

## 🎯 Prochaines Étapes

Une fois la configuration terminée :

1. ✅ Testez la recherche pour chaque marché
2. ✅ Sélectionnez les canaux pertinents
3. ✅ Lancez la calibration (OCR uniquement sur canaux sélectionnés)
4. ✅ Exportez les résultats
5. ✅ Utilisez les canaux activés pour le trading

## 📞 Support

Si vous rencontrez des problèmes :

1. Vérifiez que tous les Secrets sont correctement configurés
2. Consultez les logs Streamlit Cloud (Settings → Logs)
3. Testez localement avec `python telegram_search.py`
4. Régénérez une nouvelle StringSession si nécessaire

---

**Version :** 2.0  
**Dernière mise à jour :** 28/06/2026  
**Auteur :** Pipeline Trading Team
