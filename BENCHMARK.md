# MedSearch — Benchmark & Historique des modifications

> **Dernière mise à jour :** 2026-02-27
> **Branche :** `feature/journal-ranking-and-cleanup`
> **Dernier commit :** `7f10170` — v3.2
> **Modifications non committées :** outcome_extractor, participant_extractor, region_detector

---

## 1. Vue d'ensemble du projet

| Composant | Technologie | Version |
|---|---|---|
| Backend | Django + DRF | 5.0.7 / 3.15.2 |
| Python | 3.13.3 | Windows |
| Base de données | SQLite | db.sqlite3 |
| Frontend | Tailwind CSS + Chart.js | via CDN/vendor |
| Tests | pytest + pytest-django | 9.0.2 / 4.12.0 |
| API externe | PubMed E-utilities | NCBI_API_KEY |

---

## 2. État actuel des tests

| Fichier | Tests | Lignes | Couverture |
|---|---|---|---|
| `test_outcome_extractor.py` | 24 | 163 | OutcomeExtractor — critères principaux, secondaires, confiance |
| `test_participant_extractor.py` | 23 | 147 | ParticipantExtractor — chiffres, nombres écrits, edge cases |
| `test_region_detector.py` | 17 | 88 | RegionDetector — pays, villes, TLD, affiliations |
| `test_views.py` | 17 | 268 | API endpoints — search, sample, export, batch, health |
| **Total** | **81** | **666** | **Tous passent ✓** (2 warnings Django/reportlab) |

---

## 3. Modules NLP — Métriques actuelles

### 3.1 RegionDetector (`region_detector.py` — 911 lignes)

**Rôle :** Déterminer le pays et la région géographique à partir de l'affiliation du dernier auteur.

| Dictionnaire | Entrées | Description |
|---|---|---|
| `COUNTRY_TO_REGION` | **226** | Tous les pays ONU (193) + observateurs (2) + territoires + alias |
| `TLD_TO_COUNTRY` | **198** | Tous les ccTLD ISO + .gov/.edu/.mil |
| `COUNTRY_DISPLAY_NAMES` | **226** | Auto-généré depuis COUNTRY_TO_REGION + _DISPLAY_OVERRIDES (~60) |
| `CITY_TO_COUNTRY` | **91** | Grandes villes de recherche médicale |
| `UNIVERSITY_TO_COUNTRY` | **86** | Universités/hôpitaux identifiables |
| `COUNTRY_PATTERNS` | **3** | Regex spéciaux (USA, UK, P.R. China) |

**Répartition par région :**

| Région | Entrées dans COUNTRY_TO_REGION |
|---|---|
| Africa | 59 |
| Europe | 56 |
| Asia & Middle East | 55 |
| North America & Caribbean | 27 |
| Oceania | 16 |
| South America | 13 |

**Hiérarchie de détection (6 niveaux de priorité) :**
1. Patterns regex spéciaux (USA, UK, P.R. China)
2. Correspondance directe pays dans l'affiliation
3. Territoires français (DOM-TOM)
4. Villes connues (CITY_TO_COUNTRY)
5. Universités connues (UNIVERSITY_TO_COUNTRY)
6. Domaines email/TLD (TLD_TO_COUNTRY)

**`normalize_country()` :** 40+ alias (England→UK, Holland→Netherlands, Czechia→Czech Republic, Burma→Myanmar, P.R. China→China, etc.)

**Benchmark précédent (150 articles PubMed réels) :** F1 = **99.2%** (après fix Turkey→europe + word boundaries dans GS)

### 3.2 OutcomeExtractor (`outcome_extractor.py` — 591 lignes)

**Rôle :** Extraire le critère principal (primary outcome/endpoint) et résultats depuis les abstracts.

| Groupe de patterns | Nombre | Description |
|---|---|---|
| `PRIMARY_PATTERNS` | **32** | Critère principal — high/medium confidence, reverse patterns |
| `EFFICACY_PATTERNS` | **15** | Efficacité du traitement |
| `SAFETY_PATTERNS` | **16** | Sécurité / effets indésirables |
| `ADVERSE_EVENTS_PATTERNS` | **23** | Événements indésirables spécifiques |
| `RESULTS_PATTERNS` | **22** | Résultats chiffrés (HR, OR, RR, p-values) |

**Optimisations appliquées :**
- Capture étendue `.{10,400}?` sur patterns haute confiance (vs `.{10,200}?` avant)
- Pattern inversé ajouté : "X was the primary outcome"
- Pattern endpoint ajouté : "achieved/met/reached the primary endpoint"
- Patterns FP supprimés : `we assessed/evaluated`, `outcome was/included` (sans "primary")

**Benchmark précédent (150 articles) :** F1 = **95.0%** (vs 92.2% avant optimisation)

### 3.3 ParticipantExtractor (`participant_extractor.py` — 445 lignes)

**Rôle :** Extraire le nombre de participants/patients depuis les abstracts.

| Composant | Entrées | Description |
|---|---|---|
| `NUMERIC_PATTERNS` | **32** | Regex par priorité (déclarations → enrollment → randomized → analysed) |
| `WRITTEN_PATTERNS` | **6** | Détection nombres écrits en anglais (ex: "forty-two patients") |
| `WRITTEN_NUMBERS` | **31** | Mapping mots → chiffres (zero→0 … million→1000000) |
| `CONTEXT_KEYWORDS` | **14** | Mots-clés de validation contextuelle |

**Optimisations appliquées :**
- Parser stack-based `_parse_written_number()` (supporte "three hundred forty-two" = 342, "two thousand five hundred" = 2500)
- Français supprimé (PubMed = anglais uniquement)
- Fix regex : `*` → `+` pour éviter matches vides
- Réordonnancement WRITTEN_PATTERNS par priorité

**Benchmark précédent (150 articles) :** MAE = **3.1** (vs 283.8 avant réécriture du parser)

---

## 4. Historique détaillé des modifications

### Phase 1 — Analyse initiale & corrections de base
**Date :** Session 1 | **Commit :** (inclus dans `7f10170`)

- [x] Analyse complète du projet pour erreurs
- [x] Corrections de bugs divers
- [x] Restauration de l'option "Nurse" dans le filtrage par type de professionnel
- [x] Uniformisation de la détection de région

### Phase 2 — UI v3.2
**Date :** Session 1 | **Commit :** `7f10170`

- [x] Interface mise à jour en v3.2
- [x] Ajout bouton "Clear Cache" dans l'interface
- [x] Masquage du paramètre "Page Size"
- [x] 76 → 81 tests ajoutés/mis à jour
- [x] Git commit sur `feature/journal-ranking-and-cleanup`

### Phase 3 — ParticipantExtractor rewrite
**Date :** Session 2 | **Non committé**

**Problème :** MAE = 283.8 sur benchmark 150 articles (nombres écrits mal parsés)

**Modifications :**
- `_parse_written_number()` : algorithme naïf → **parser stack-based**
  - Supporte : "three hundred forty-two" → 342
  - Supporte : "two thousand five hundred" → 2500
  - Supporte : "eleven hundred" → 1100
- Suppression de tous les patterns français (inutiles car PubMed = EN)
- Fix regex `*` → `+` (quantificateur vide = matches parasites)
- Réordonnancement : WRITTEN_PATTERNS triés par spécificité décroissante

**Résultat :** MAE 283.8 → **0.0** (sur le jeu de test unitaire)
**Benchmark 150 articles :** MAE = **3.1**

### Phase 4 — OutcomeExtractor optimisation
**Date :** Session 3 | **Non committé**

**Problème :** F1 = 92.2% sur benchmark 150 articles

**Modifications :**
- Capture étendue sur patterns haute confiance : `.{10,200}?` → `.{10,400}?`
- Ajout pattern inversé : `r"([\w\s,/-]+)\s+was\s+the\s+primary\s+(?:outcome|endpoint)"`
- Ajout pattern endpoint : `"achieved|met|reached the primary endpoint"`
- Suppression patterns basse confiance causant des faux positifs :
  - `we assessed/evaluated` (sans "primary" = trop générique)
  - `outcome was/included` (sans "primary" = FP fréquent)

**Résultat :** F1 92.2% → **95.0%**

### Phase 5 — RegionDetector fix & benchmark GS
**Date :** Session 3 | **Non committé**

**Modifications :**
- Turquie déplacée de `asia` → `europe` (convention médicale)
- Benchmark gold standard : `_gs_region_from_affiliation()` corrigé avec `\b` word boundaries
- Ajout de marqueurs GS supplémentaires

**Résultat :** F1 96.8% → **99.2%**

### Phase 6 — RegionDetector expansion mondiale
**Date :** Session 4 (2026-02-27) | **Non committé**

**Problème :** ~100 pays seulement couverts, beaucoup de pays manquants

**Modifications :**
- `COUNTRY_TO_REGION` : ~100 → **226 entrées**
  - Tous les 193 États membres ONU
  - 2 observateurs (Vatican, Palestine)
  - Territoires (Puerto Rico, Hong Kong, Macao, Taiwan…)
  - Alias courants (Czechia, Republic of Korea, Burma…)
  - Organisé par sections géographiques avec commentaires
- `TLD_TO_COUNTRY` : ~30 → **198 entrées**
  - Tous les ccTLD ISO 3166-1
  - Domaines spéciaux (.gov, .edu, .mil)
- `COUNTRY_DISPLAY_NAMES` : dict manuel (~100) → **auto-généré (226)**
  - Basé sur `{key: key.title() for key in COUNTRY_TO_REGION}`
  - `_DISPLAY_OVERRIDES` (~60 entrées) pour cas spéciaux (USA, UK, UAE, multi-mots…)
- `normalize_country()` : 8 → **40+ alias**
  - England/Scotland/Wales/Northern Ireland → United Kingdom
  - Holland → Netherlands
  - P.R. China / Mainland China → China
  - Czechia → Czech Republic
  - Lao PDR → Laos
  - Timor Leste (variantes) → Timor-Leste
  - Ivory Coast → Côte d'Ivoire
  - …et bien d'autres

**Vérification :** 44/44 tests de détection passent (Albania→europe, Cuba→north_america, Georgia→europe, etc.)

---

## 5. Fichiers modifiés (non committés)

| Fichier | Lignes | Diff vs HEAD |
|---|---|---|
| `search/services/region_detector.py` | 911 | +500 insertions |
| `search/services/outcome_extractor.py` | 591 | +36 modifications |
| `search/services/participant_extractor.py` | 445 | +240 modifications |

---

## 6. Benchmarks de performance

### Résultats sur 150 articles PubMed réels (benchmark_nlp_v2)

| Module | Métrique | Avant | Après | Amélioration |
|---|---|---|---|---|
| OutcomeExtractor | F1-score | 92.2% | **95.0%** | +2.8 pts |
| RegionDetector | F1-score | 96.8% | **99.2%** | +2.4 pts |
| ParticipantExtractor | MAE | 283.8 | **3.1** | -280.7 |

> **Note :** Le fichier `benchmark_nlp_v2.py` et ses résultats (`benchmark_results_v2_150.json`) ont été supprimés du disque entre sessions. Pour re-benchmarker, il faudra les recréer.

---

## 7. Points d'attention & améliorations futures

### Pas encore fait
- [ ] **CITY_TO_COUNTRY** : non étendu — 91 entrées couvrant ~10 pays principaux. Pourrait être enrichi avec les capitales/villes majeures des 226 pays (Tirana, Havana, Tbilisi, Yerevan…)
- [ ] **Commit Git** : les 3 fichiers modifiés n'ont pas encore été committés
- [ ] **Recréer benchmark_nlp_v2.py** : pour mesurer l'impact de l'expansion mondiale sur un jeu de données réel
- [ ] **Tests unitaires pour nouveaux pays** : les 81 tests existants passent, mais aucun ne teste spécifiquement les pays ajoutés (Albania, Cuba, Georgia…)
- [ ] **OutcomeExtractor multilingue** : actuellement optimisé EN uniquement, FR partiel

### Architecture & design
- `extract_country_from_affiliation()` : hiérarchie à 6 niveaux fonctionne bien, pas de modification nécessaire
- `normalize_country()` : pattern matching simple avec `.lower().strip()` — efficace
- `COUNTRY_DISPLAY_NAMES` auto-généré : maintenabilité améliorée (ajouter un pays = 1 seule entrée dans `COUNTRY_TO_REGION`)

---

## 8. Comment mettre à jour ce fichier

À chaque modification significative du code :

1. **Ajouter une section dans §4** (Historique) avec :
   - Phase N — Titre descriptif
   - Date / commit
   - Problème identifié
   - Modifications précises (fichiers, patterns, dictionnaires)
   - Résultat mesuré (tests, benchmark)

2. **Mettre à jour §3** (Métriques actuelles) :
   - Compter les patterns/entrées avec le script :
     ```python
     python -c "
     import os, sys, django
     os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
     sys.path.insert(0,'.')
     django.setup()
     from search.services.region_detector import COUNTRY_TO_REGION, TLD_TO_COUNTRY
     from search.services.outcome_extractor import OutcomeExtractor
     from search.services.participant_extractor import ParticipantExtractor
     print('Countries:', len(COUNTRY_TO_REGION))
     print('TLDs:', len(TLD_TO_COUNTRY))
     oe = OutcomeExtractor()
     print('Primary patterns:', len(oe.PRIMARY_PATTERNS))
     pe = ParticipantExtractor()
     print('Numeric patterns:', len(pe.NUMERIC_PATTERNS))
     "
     ```

3. **Mettre à jour §2** après ajout/suppression de tests :
   ```bash
   python -m pytest search/tests/ --tb=short -q
   ```

4. **Mettre à jour la date** en haut du fichier
