# 🚀 TELEGRAMTRADER — Guide de démarrage client

## ⚡ Démarrage en 3 clics

| Action | Fichier à double-cliquer |
|--------|--------------------------|
| 🟢 **Démarrer** l'application | `DEMARRER.bat` |
| 🔴 **Arrêter** l'application | `ARRETER.bat` |
| 🔄 **Mettre à jour** l'application | `METTRE_A_JOUR.bat` |

> Ces 3 fichiers `.bat` sont à la **racine du projet**. Double-cliquez dessus, c'est tout.

---

## 📋 Prérequis (à installer une seule fois)

### 1. Docker Desktop
L'application tourne dans Docker — c'est le seul logiciel à installer.

👉 **Télécharger :** https://www.docker.com/products/docker-desktop/

- Installez Docker Desktop
- Lancez-le (icône baleine dans la barre des tâches)
- C'est tout — `DEMARRER.bat` s'occupe du reste

### 2. Git (pour les mises à jour)
Nécessaire uniquement pour `METTRE_A_JOUR.bat`.

👉 **Télécharger :** https://git-scm.com/download/win

---

## 🔑 Configuration (première fois uniquement)

Au **premier lancement**, `DEMARRER.bat` ouvrira automatiquement le fichier
`backend/.env` pour que vous renseigniez vos clés Telegram :

```env
TELEGRAM_API_ID=votre_api_id        ← depuis https://my.telegram.org
TELEGRAM_API_HASH=votre_api_hash    ← depuis https://my.telegram.org
SECRET_KEY=une-cle-aleatoire-longue ← n'importe quelle chaîne aléatoire
```

> 💡 **Obtenir vos clés Telegram :**
> 1. Allez sur https://my.telegram.org
> 2. Connectez-vous avec votre numéro de téléphone
> 3. Cliquez sur "API development tools"
> 4. Copiez `api_id` et `api_hash`

---

## 📱 Accès à l'application

Une fois démarré (le navigateur s'ouvre automatiquement) :

| Service | URL |
|---------|-----|
| **Interface web** | http://localhost:3000 |
| **API Backend** | http://localhost:8000 |
| **Documentation API** | http://localhost:8000/api/docs |

---

## 🖥️ Agent NinjaTrader 8

L'agent Windows fait le pont entre TelegramTrader et NinjaTrader 8.

### Installation (une seule fois)
1. Ouvrez l'interface web → **Paramètres** → **Agent NinjaTrader**
2. Cliquez **"Générer un code d'appairage"**
3. Cliquez **"Télécharger TelegramTraderAgent.exe"**
4. Double-cliquez sur `TelegramTraderAgent.exe`
5. Saisissez le code d'appairage affiché sur le site
6. L'agent démarre et s'installe dans la barre des tâches (🟢)

### Add-On NinjaTrader 8 (une seule fois)
1. Dans l'interface web → **Paramètres** → **Télécharger l'Add-On NT8**
2. Copiez `TelegramTraderAddOn.cs` dans :
   `Documents\NinjaTrader 8\bin\Custom\AddOns\`
3. Dans NinjaTrader 8 : **Tools → Edit NinjaScript → F5** (compiler)
4. **Fermez et rouvrez NinjaTrader 8** (l'Add-On démarre automatiquement)

---

## 🔧 Commandes avancées (PowerShell)

```powershell
# Démarrage rapide (sans rebuild)
.\scripts\start-auto.ps1 -SkipBuild

# Démarrage sans ouvrir le navigateur
.\scripts\start-auto.ps1 -NoBrowser

# Voir les logs en temps réel
docker-compose logs -f

# Voir les logs du backend uniquement
docker-compose logs -f backend

# Statut des conteneurs
docker-compose ps

# Redémarrer le backend uniquement
docker-compose restart backend

# Arrêter complètement
docker-compose down
```

---

## 🆘 Dépannage

### ❌ "Docker n'est pas démarré"
→ Ouvrez Docker Desktop (icône baleine dans la barre des tâches)
→ Attendez que l'icône soit verte, puis relancez `DEMARRER.bat`

### ❌ "Les clés Telegram ne sont pas configurées"
→ Ouvrez `backend/.env` avec Notepad
→ Renseignez `TELEGRAM_API_ID` et `TELEGRAM_API_HASH`
→ Sauvegardez et relancez `DEMARRER.bat`

### ❌ "NinjaTrader non détecté" (❌ dans l'interface)
→ Vérifiez que NinjaTrader 8 est **ouvert**
→ Vérifiez que l'Add-On est **compilé** (Tools → Edit NinjaScript → F5)
→ **Fermez et rouvrez NinjaTrader 8** (l'Add-On ne démarre qu'au lancement)
→ Attendez ~10 secondes que l'agent envoie un heartbeat

### ❌ "Aucun agent NT8 lié"
→ Vérifiez que `TelegramTraderAgent.exe` tourne (icône 🟢 dans la barre des tâches)
→ Si l'agent tourne mais n'est pas lié : cliquez **"Récupérer mon agent"** (bouton orange dans Paramètres)

### ❌ Port déjà utilisé (3000 ou 8000)
```powershell
# Trouver quel processus utilise le port
netstat -ano | findstr :3000
netstat -ano | findstr :8000
# Tuer le processus (remplacez XXXX par le PID)
taskkill /PID XXXX /F
```

---

## 📞 Support

En cas de problème non résolu :
- Consultez les logs : `docker-compose logs --tail=100`
- Vérifiez le statut : `docker-compose ps`
