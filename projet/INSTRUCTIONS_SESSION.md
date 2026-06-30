# 📱 INSTRUCTIONS POUR GÉNÉRER VOTRE STRING SESSION

## ✅ ÉTAPE ACTUELLE
Le script `generate_session.py` est **EN COURS D'EXÉCUTION** et attend votre saisie.

## 🔢 ÉTAPES À SUIVRE MAINTENANT

### 1️⃣ Entrer votre numéro de téléphone
Dans le terminal où le script tourne, vous voyez :
```
Please enter your phone (or bot token):
```

**ACTION REQUISE :**
- Tapez votre numéro de téléphone au format international : `+212648955924`
- Appuyez sur **ENTRÉE**

### 2️⃣ Recevoir le code de vérification
**IMPORTANT :** Le code NE VIENT PAS par SMS !

Le code arrive dans **l'application Telegram** elle-même :
- Ouvrez votre application Telegram (sur téléphone ou ordinateur)
- Cherchez un message de **Telegram** (compte officiel)
- Vous verrez un code à 5 chiffres

### 3️⃣ Entrer le code de vérification
Dans le terminal, le script demandera :
```
Please enter the code you received:
```

**ACTION REQUISE :**
- Tapez le code à 5 chiffres reçu dans Telegram
- Appuyez sur **ENTRÉE**

### 4️⃣ Copier la StringSession
Si tout se passe bien, vous verrez :
```
✅ Connexion établie!

Votre StringSession (à copier dans Streamlit Secrets):
1AgAOMTQ5LjE1NC4xNjcuNTEBu... (longue chaîne de caractères)
```

**ACTION REQUISE :**
- **COPIEZ** toute cette longue chaîne de caractères
- **GARDEZ-LA EN SÉCURITÉ** (c'est comme un mot de passe)

---

## 🚨 PROBLÈMES COURANTS

### "Je ne reçois rien"
➡️ **Le code arrive dans l'app Telegram, PAS par SMS !**
- Ouvrez Telegram sur votre téléphone/ordinateur
- Regardez dans "Telegram" (compte officiel)

### "Invalid phone number"
➡️ Utilisez le format international avec `+`
- Exemple : `+212648955924` (Maroc)
- Exemple : `+33612345678` (France)

### "Phone number banned"
➡️ Votre compte Telegram a des restrictions
- Utilisez un autre compte Telegram
- Contactez le support Telegram

---

## 📋 APRÈS AVOIR LA STRING SESSION

Une fois que vous avez copié la StringSession, vous devrez :

1. **Sur Streamlit Cloud** (quand vous déployez) :
   - Aller dans Settings → Secrets
   - Ajouter :
   ```toml
   TELEGRAM_API_ID = "29149167"
   TELEGRAM_API_HASH = "d1942abd0a5a7c764d96a8a4b640893e"
   TELEGRAM_STRING_SESSION = "votre_longue_string_session_ici"
   ```

2. **Pour tester localement** :
   - Modifier `projet/.env` pour ajouter :
   ```
   TELEGRAM_STRING_SESSION=votre_longue_string_session_ici
   ```

---

## 🎯 RÉSUMÉ RAPIDE

1. ✍️ Tapez `+212648955924` dans le terminal → ENTRÉE
2. 📱 Ouvrez Telegram → Cherchez le code
3. ✍️ Tapez le code dans le terminal → ENTRÉE
4. 📋 Copiez la StringSession affichée
5. ✅ Gardez-la en sécurité pour la configuration Streamlit

---

**IMPORTANT :** Cette StringSession est comme un mot de passe. Ne la partagez jamais publiquement !
