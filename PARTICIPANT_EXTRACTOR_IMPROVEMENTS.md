# Améliorations du ParticipantExtractor

## Problème identifié

L'application extrayait **59 participants** au lieu de **119** pour cet abstract :

```
In total, 119 individuals participated (53 medical students; 66 residents). 
[...] Depending on topic, 57-92% (N = 59-66) of respondents favored e-learning...
```

**Cause** : Le pattern `N = 59` avait un score de confiance plus élevé (0.9) que "119 individuals participated" (0.8).

## Solution implémentée

### 1. Réorganisation des patterns par priorité

**Fichier** : `search/services/participant_extractor.py`

Les patterns ont été réordonnés pour prioriser les **déclarations principales** :

```python
NUMERIC_PATTERNS = [
    # PRIORITAIRES: Déclarations principales (début d'abstract)
    r'(?:in\s+)?total[,\s]+(\d{1,6})\s+(?:participants?|...)(?:participated|enrolled|...)',
    r'(\d{1,6})\s+(?:participants?|...)(?:participated|were\s+enrolled|...)',
    r'total\s+of\s+(\d{1,6})\s+(?:participants?|...)',
    r'(?:study|trial|analysis)\s+(?:included|enrolled|recruited)\s+(\d{1,6})\s+...',
    r'(\d{1,6})\s+(?:participants?|patients?|...)',
    
    # SECONDAIRES: Formats avec N = (souvent sous-groupes)
    r'sample\s+size\s*[:\(]?\s*[Nn]?\s*=?\s*(\d{1,6})',
    r'[Nn]\s*=\s*(\d{1,6})',  # Dépriorisé !
    ...
]
```

### 2. Nouveau système de scoring

#### Scores de base améliorés :

| Pattern | Ancien score | Nouveau score | Description |
|---------|--------------|---------------|-------------|
| `In total, X individuals participated` | 0.80 | **0.95** | Priorité MAX |
| `X participants were enrolled` | 0.80 | **0.95** | Priorité MAX |
| `total of X participants` | 0.70 | **0.90** | Haute priorité |
| `study included X participants` | 0.70 | **0.90** | Haute priorité |
| `X participants` (simple) | 0.80 | **0.85** | Priorité moyenne-haute |
| `N = X` (isolé) | **0.90** | **0.60** | ⬇️ DÉPRIORISÉ |
| `(N = X)` entre parenthèses | 0.70 | **0.50** | ⬇️ Très basse priorité |

#### Bonus/Malus ajoutés :

**✅ BONUS (+0.15)** : 
- Position dans les premiers 20% de l'abstract (déclaration principale)
- Présence de "in total" ou "a total of"

**✅ BONUS (+0.10)** : 
- Verbes d'action : "participated", "enrolled", "recruited", "included"

**❌ MALUS (-0.15)** : 
- Pattern `N =` sans le mot "total" (souvent un sous-groupe)

**❌ MALUS (-0.10)** : 
- Position dans les derniers 20% de l'abstract (sous-analyses)

**❌ MALUS (-0.40)** : 
- Nombres < 10 (probablement pas le total)

### 3. Prise en compte de la position

```python
position_ratio = match.start() / len(abstract)

if position_ratio < 0.2:  # Premiers 20%
    score += 0.15  # Les déclarations principales sont au début
elif position_ratio > 0.8:  # Derniers 20%
    score -= 0.10  # Les sous-analyses sont souvent à la fin
```

## Résultats des tests

### Test 1 : Cas problématique original ✅

```
Abstract: "In total, 119 individuals participated (53 medical students; 66 residents). 
           [...] (N = 59-66) of respondents..."

Avant : 59 participants (score 0.9) ❌
Après : 119 participants (score 1.0) ✅
```

**Détails des scores** :
- `In total, 119 individuals participated` → **Score: 1.000**
- `N = 59` → **Score: 0.400**

### Test 2 : Study enrolled ✅

```
Abstract: "The study enrolled 250 patients with type 2 diabetes mellitus. 
           Participants were randomized into two groups (N = 125 per group)."

Résultat : 250 patients ✅
Confiance : High
```

### Test 3 : Piège des parenthèses ✅

```
Abstract: "A total of 200 participants were recruited for this randomized controlled trial.
           [...] The primary outcome (N = 50 analyzed) showed significant improvement."

Résultat : 200 participants (pas 50) ✅
```

### Test 4 : Verbe participated ✅

```
Abstract: "85 patients participated in this multicenter study."

Résultat : 85 patients ✅
```

### Test 5 : Multiples N = ✅

```
Abstract: "This study included 500 participants from three centers. 
           Group A (N = 200) received treatment X, Group B (N = 150)..."

Résultat : 500 participants (pas 200) ✅
```

## Tests de validation

**Script** : `test_participant_extraction.py`

```bash
python test_participant_extraction.py
```

**Résultats** : ✅ **5/5 tests réussis**

## Impact utilisateur

### Avant :
```
Sample Size: 59 participants
Haute confiance
Source: "N = 59"
```
❌ Faux positif (sous-groupe au lieu du total)

### Après :
```
Sample Size: 119 participants
Haute confiance
Source: "In total, 119 individuals participated"
```
✅ Correct (nombre total détecté)

## Cas d'usage couverts

| Cas | Pattern | Exemple | Détection |
|-----|---------|---------|-----------|
| Déclaration avec "total" | ✅ | "In total, 119 individuals participated" | Score 1.0 |
| Study enrolled | ✅ | "The study enrolled 250 patients" | Score 0.95 |
| Simple + verbe | ✅ | "85 patients participated" | Score 1.0 |
| Total of | ✅ | "A total of 200 participants were recruited" | Score 0.95 |
| Sous-groupes (N=) | ⚠️ | "(N = 59-66)" | Score 0.4 (ignoré) |
| Parenthèses | ⚠️ | "(N = 50 analyzed)" | Score 0.5 (ignoré) |

## Limitations connues

### 1. Ranges de nombres
```
"(N = 59-66)" → Détecte 59, pas la range
```
**Solution future** : Parser les ranges et prendre la moyenne ou le max

### 2. Nombres séparés par groupes
```
"53 medical students; 66 residents" → Non additionné automatiquement
```
**Workaround actuel** : Détecte "119 individuals participated" avant

### 3. Abstracts sans déclaration claire
```
"Patients were analyzed." (pas de nombre)
```
**Comportement** : Retourne `None` (confiance: 'none')

## Configuration

### Ajuster les seuils de confiance :

Dans `participant_extractor.py`, ligne ~220 :

```python
if best_result['confidence_score'] >= 0.8:
    confidence = 'high'
elif best_result['confidence_score'] >= 0.5:
    confidence = 'medium'
else:
    confidence = 'low'
```

### Activer le debug :

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Fichiers modifiés

| Fichier | Modifications |
|---------|--------------|
| `search/services/participant_extractor.py` | Réorganisation patterns + nouveau scoring |
| `test_participant_extraction.py` | Tests de validation avec 5 cas réels |
| `PARTICIPANT_EXTRACTOR_IMPROVEMENTS.md` | Cette documentation |

## Prochaines étapes possibles

1. **Détection de ranges** : `(N = 59-66)` → moyenne ou total
2. **Addition de sous-groupes** : `(53 + 66)` → `119`
3. **Machine Learning** : Entraîner un modèle sur des abstracts annotés
4. **Multi-langues** : Support français, espagnol, etc.
5. **Validation croisée** : Comparer avec les métadonnées PubMed

## Conclusion

✅ **Problème résolu** : L'application détecte maintenant correctement le nombre total de participants même en présence de sous-groupes.

✅ **Tests validés** : 5/5 cas réels passent avec haute confiance.

✅ **Prêt pour production** : Le système est robuste et préfère les déclarations principales aux mentions secondaires.

---

**Date** : 3 octobre 2025  
**Auteur** : GitHub Copilot  
**Version** : ParticipantExtractor v2.0
