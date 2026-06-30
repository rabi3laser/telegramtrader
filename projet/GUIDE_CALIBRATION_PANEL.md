# 📊 GUIDE - CALIBRATION PANEL (Indicateur NinjaTrader 8)

## 🎯 Objectif

L'indicateur **CalibrationPanel** affiche un panneau d'information complet sur votre chart NinjaTrader 8. Ce panneau est conçu pour être **capturé en screenshot** et uploadé dans Streamlit pour :
- Fournir les prix exacts de votre broker (OHLC)
- Calculer le **vrai winrate** des signaux Telegram
- Comparer les signaux (Entry/TP/SL) avec les prix réels

---

## 📋 Ce que le panneau affiche

```
┌─ CALIBRATION PANEL ──────────────────────────────────┐
│                                                       │
│  INSTRUMENT: Gold (MGC) Dec 26                        │
│  TIMEFRAME : 15 Min                                   │
│  ─────────────────────────────────────────────────    │
│  DATE      : 30/06/2026                               │
│  BAR TIME  : 14:30:00                                 │
│  ─────────────────────────────────────────────────    │
│  OPEN      : 2340.10                                  │
│  HIGH      : 2350.50   ← en vert                      │
│  LOW       : 2338.20   ← en rouge                     │
│  LAST      : 2345.60  (+5.50 / +0.23%)  ← vert/rouge │
│  ─────────────────────────────────────────────────    │
│  ATR(14)   : 15.20                                    │
│  VOLUME    : 12,345                                   │
│  TICK SIZE : 0.10                                     │
│  ─────────────────────────────────────────────────    │
│  SERVER: 14:30:25.123                                 │
└───────────────────────────────────────────────────────┘
```

---

## 🛠️ INSTALLATION

### Étape 1 : Copier le fichier

Copiez `CalibrationPanel.cs` dans le dossier des indicateurs NT8 :

```
C:\Users\[Votre Nom]\Documents\NinjaTrader 8\bin\Custom\Indicators\
```

> 💡 Remplacez `[Votre Nom]` par votre nom d'utilisateur Windows

### Étape 2 : Compiler dans NinjaTrader

1. Ouvrez **NinjaTrader 8**
2. Menu : **Tools** → **Edit NinjaScript** → **Indicator...**
3. Dans l'éditeur, cliquez sur **Compile** (bouton en haut ou `F5`)
4. Vérifiez qu'il n'y a pas d'erreurs dans la fenêtre de compilation
5. Fermez l'éditeur

### Étape 3 : Ajouter sur un chart

1. Ouvrez un chart du marché à calibrer (ex: Gold MGC 15min)
2. Clic droit sur le chart → **Indicators...**
3. Dans la liste, trouvez **CalibrationPanel**
4. Double-cliquez pour l'ajouter
5. Configurez les paramètres si nécessaire (voir ci-dessous)
6. Cliquez **OK**

---

## ⚙️ PARAMÈTRES CONFIGURABLES

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| **Position X** | 10 | Distance depuis le bord gauche (pixels) |
| **Position Y** | 10 | Distance depuis le bord haut (pixels) |
| **Taille de police** | 14 | Taille du texte (8-24) |
| **Opacité fond** | 200 | Transparence du fond (0=transparent, 255=opaque) |
| **Afficher ATR** | Oui | Affiche l'ATR(14) |
| **Période ATR** | 14 | Nombre de barres pour le calcul ATR |
| **Afficher Volume** | Oui | Affiche le volume de la barre |
| **Afficher Tick Size** | Oui | Affiche la taille du tick |

> 💡 **Conseil** : Augmentez la taille de police à **16-18** pour une meilleure lisibilité sur les captures

---

## 📸 COMMENT FAIRE UNE BONNE CAPTURE

### Méthode recommandée : Win + Shift + S

1. Assurez-vous que le panneau est **visible et non coupé**
2. Appuyez sur **Win + Shift + S**
3. Sélectionnez la zone incluant le panneau CalibrationPanel
4. La capture est copiée dans le presse-papiers
5. Collez dans Paint ou sauvegardez directement

### Méthode alternative : PrintScreen

1. Appuyez sur **PrintScreen** (capture tout l'écran)
2. Ouvrez Paint → Coller → Recadrer si nécessaire
3. Sauvegardez en PNG

### ✅ Bonnes pratiques pour l'OCR

- **Format PNG** de préférence (meilleure qualité)
- **Résolution minimale** : 1280x720
- **Panneau non coupé** : tout le texte doit être visible
- **Contraste élevé** : fond sombre + texte clair (par défaut)
- **Pas de zoom** : taille normale du chart

---

## 🔄 WORKFLOW COMPLET

### 1. Préparer NT8

```
NT8 → Ouvrir chart Gold MGC 15min
    → Ajouter CalibrationPanel
    → Attendre la barre qui correspond à un signal Telegram
```

### 2. Capturer au bon moment

```
Signal Telegram reçu à 14:25 : "BUY Gold @ 2340 TP 2355 SL 2330"
    → Attendre la barre de 14:30 (fermeture de la barre 15min)
    → Faire la capture quand la barre est fermée
    → Le panneau affiche : OPEN 2340.10 HIGH 2350.50 LOW 2338.20 LAST 2345.60
```

### 3. Uploader dans Streamlit

```
Streamlit → Accueil → "Repères de Prix NinjaTrader"
    → Sélectionner le marché : Gold (MGC)
    → Sélectionner le timeframe : 15
    → Uploader la capture PNG
    → OCR automatique (si Ollama disponible) OU saisie manuelle
    → Vérifier les valeurs extraites
    → Cliquer "SAUVEGARDER CETTE RÉFÉRENCE"
```

### 4. Calcul du Winrate

```
Streamlit → Accueil → "Repères de Prix NinjaTrader"
    → Section "Winrate Réel calculé depuis vos références NT8"
    → Affiche : "🟢 GOLD Snipers : Winrate réel = 65% (13/20 trades)"
```

---

## 📊 COMMENT LE WINRATE EST CALCULÉ

### Logique de comparaison

Pour chaque signal Telegram détecté :

**Signal BUY** (ex: BUY Gold @ 2340, TP 2355, SL 2330) :
- ✅ **Gagné** si `HIGH de la barre ≥ TP (2355)`
- ❌ **Perdu** si `LOW de la barre ≤ SL (2330)`
- ❓ **Indéterminé** si ni TP ni SL atteint

**Signal SELL** (ex: SELL Gold @ 2345, TP 2330, SL 2360) :
- ✅ **Gagné** si `LOW de la barre ≤ TP (2330)`
- ❌ **Perdu** si `HIGH de la barre ≥ SL (2360)`
- ❓ **Indéterminé** si ni TP ni SL atteint

### Formule

```
Winrate = (Trades Gagnés / (Trades Gagnés + Trades Perdus)) × 100%
```

### Exemple

```
Canal "GOLD Snipers" - 20 signaux analysés :
  - 13 signaux : TP atteint ✅
  - 5 signaux  : SL atteint ❌
  - 2 signaux  : Indéterminé ❓

Winrate = 13 / (13 + 5) = 72.2% 🟢
```

---

## 🎯 STRATÉGIE DE CAPTURE OPTIMALE

### Pour une calibration précise

**Capturez plusieurs barres** pour chaque signal :

| Capture | Moment | Utilité |
|---------|--------|---------|
| **Capture 1** | Barre du signal | Prix d'entrée exact |
| **Capture 2** | 1h après le signal | Voir si TP/SL atteint |
| **Capture 3** | 4h après le signal | Confirmation finale |

### Marchés et timeframes recommandés

| Marché | Timeframe | Raison |
|--------|-----------|--------|
| Gold MGC | 15min | Signaux fréquents |
| Nasdaq MNQ | 15min | Volatilité élevée |
| Crude Oil MCL | 15min | Mouvements rapides |
| S&P 500 MES | 15min | Tendances claires |

---

## 🚨 DÉPANNAGE

### "CalibrationPanel n'apparaît pas dans la liste"
→ Vérifiez que le fichier est dans le bon dossier  
→ Recompilez : Tools → Edit NinjaScript → Compile  
→ Redémarrez NinjaTrader si nécessaire

### "Erreur de compilation"
→ Vérifiez que vous utilisez NinjaTrader 8 (pas NT7)  
→ Vérifiez que le fichier n'est pas corrompu  
→ Essayez de recopier le fichier depuis GitHub

### "Le panneau est invisible"
→ Augmentez l'opacité du fond (paramètre BackgroundOpacity → 220)  
→ Vérifiez que Position X et Y sont dans la zone visible du chart  
→ Essayez Position X=10, Position Y=10

### "L'OCR ne lit pas bien les valeurs"
→ Augmentez la taille de police (FontSize → 16 ou 18)  
→ Assurez-vous que la capture est en PNG (pas JPEG compressé)  
→ Utilisez la saisie manuelle comme fallback

---

## 📁 Fichiers associés

| Fichier | Description |
|---------|-------------|
| `CalibrationPanel.cs` | Code source de l'indicateur NT8 |
| `price_reference.py` | Module Python d'extraction et calcul |
| `price_references.json` | Base de données des références de prix |
| `pipeline_ui_optimized.py` | Interface Streamlit (section NT8) |

---

**Version :** 1.0  
**Compatible :** NinjaTrader 8.x  
**Date :** 30/06/2026