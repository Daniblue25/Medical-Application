# MedSearch — Benchmark & Historique des modifications

> **Dernière mise à jour :** 2026-02-27
> **Branche :** `feature/journal-ranking-and-cleanup`
> **Dernier commit :** `c053390` — NLP improvements
> **Statut :** Tout committé ✓

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
| `test_region_detector.py` | 66 | 270 | RegionDetector — pays (9 classes), villes (6), display names (5), complétude (5) |
| `test_views.py` | 17 | 268 | API endpoints — search, sample, export, batch, health |
| **Total** | **130** | **848** | **Tous passent ✓** (2 warnings Django/reportlab) |

---

## 3. Modules NLP — Métriques actuelles

### 3.1 RegionDetector (`region_detector.py` — 1103 lignes)

**Rôle :** Déterminer le pays et la région géographique à partir de l'affiliation du dernier auteur.

| Dictionnaire | Entrées | Description |
|---|---|---|
| `COUNTRY_TO_REGION` | **226** | Tous les pays ONU (193) + observateurs (2) + territoires + alias |
| `TLD_TO_COUNTRY` | **198** | Tous les ccTLD ISO + .gov/.edu/.mil |
| `COUNTRY_DISPLAY_NAMES` | **226** | Auto-généré depuis COUNTRY_TO_REGION + _DISPLAY_OVERRIDES (~60) |
| `CITY_TO_COUNTRY` | **382** | Capitales + villes de recherche médicale du monde entier |
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

**Benchmark (200 articles PubMed réels) :** F1 = **100.0%** (122/122 correct, 0 erreur)

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

**Benchmark (200 articles) :** F1 = **94.8%** (Precision 95.3%, Recall 94.4%)

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

**Benchmark (200 articles) :** F1 = **81.7%** (MAE = 175.9 — tirée par quelques outliers)

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
**Date :** Session 2 | **Commit :** `c053390`

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

### Phase 4 — OutcomeExtractor optimisation
**Date :** Session 3 | **Commit :** `c053390`

**Problème :** F1 = 92.2% sur benchmark 150 articles

**Modifications :**
- Capture étendue sur patterns haute confiance : `.{10,200}?` → `.{10,400}?`
- Ajout pattern inversé : `r"([\w\s,/-]+)\s+was\s+the\s+primary\s+(?:outcome|endpoint)"`
- Ajout pattern endpoint : `"achieved|met|reached the primary endpoint"`
- Suppression patterns basse confiance causant des faux positifs :
  - `we assessed/evaluated` (sans "primary" = trop générique)
  - `outcome was/included` (sans "primary" = FP fréquent)

**Résultat :** F1 92.2% → **94.8%**

### Phase 5 — RegionDetector fix & benchmark GS
**Date :** Session 3 | **Commit :** `c053390`

**Modifications :**
- Turquie déplacée de `asia` → `europe` (convention médicale)
- Benchmark gold standard : `_gs_region_from_affiliation()` corrigé avec `\b` word boundaries
- Ajout de marqueurs GS supplémentaires

**Résultat :** F1 96.8% → **99.2%**

### Phase 6 — RegionDetector expansion mondiale
**Date :** Session 4 (2026-02-27) | **Commit :** `c053390`

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

**Résultat :** F1 99.2% → **100.0%** (122/122 sur benchmark 200 articles)

### Phase 7 — Améliorations futures réalisées
**Date :** Session 5 (2026-02-27) | **Commit :** `c053390`

**Modifications :**
- `CITY_TO_COUNTRY` : 91 → **382 entrées**
  - Capitales de tous les pays du monde
  - Villes de recherche médicale majeures par région
  - Couverture : USA (26), Canada (9), Caraïbes (16), Amérique du Sud (15), UK (15), France (30), Allemagne (14), Italie (9), Espagne (6), Benelux (11), Suisse (5), Scandinavie (14), Europe de l'Est (22), Méditerranée (18), Japon (9), Chine (12), Corée du Sud (5), Inde (9), Asie du Sud-Est (16), Asie Centrale (8), Moyen-Orient (22), Asie du Sud (9), Afrique Nord (8), Afrique Ouest (20), Afrique Est (12), Afrique Australe (15), Afrique Centrale (6), Océanie (15)
- Tests : 81 → **130 tests** (+49 nouveaux)
  - 8 classes de tests ajoutées : NewCountriesEurope (8), NewCountriesAmericas (6), NewCountriesAsia (7), NewCountriesAfrica (8), NewCountriesOceania (4), CityBasedDetection (6), DisplayNames (5), DictionaryCompleteness (5)
- `benchmark_nlp_v2.py` recréé — script complet pour benchmarker les 3 modules NLP
- `BENCHMARK.md` créé puis mis à jour
- Git commit `c053390` avec tous les changements

**Résultat :** RegionDetector F1 = **100.0%** confirmé sur 200 articles diversifiés

---

## 5. Fichiers du projet

| Fichier | Lignes | Description |
|---|---|---|
| `search/services/region_detector.py` | ~1100 | Détection pays/région (226 pays, 382 villes, 198 TLD) |
| `search/services/outcome_extractor.py` | 591 | Extraction critères principaux (32 patterns) |
| `search/services/participant_extractor.py` | 445 | Extraction nombre participants (32+6 patterns) |
| `search/tests/test_region_detector.py` | 270 | 66 tests RegionDetector |
| `search/tests/test_outcome_extractor.py` | 163 | 24 tests OutcomeExtractor |
| `search/tests/test_participant_extractor.py` | 147 | 23 tests ParticipantExtractor |
| `search/tests/test_views.py` | 268 | 17 tests API |
| `benchmark_nlp_v2.py` | ~310 | Script benchmark NLP (PubMed réel) |

---

## 6. Benchmarks de performance

### Résultats sur 200 articles PubMed réels (2026-02-27)

Query : `"surgery OR chemotherapy OR clinical trial"` (RCT only)

| Module | Métrique | Score | Détails |
|---|---|---|---|
| **RegionDetector** | F1 | **100.0%** | 122/122 correct, 0 mismatch |
| **OutcomeExtractor** | F1 | **94.8%** | P=95.3% R=94.4% (TP=101 FP=5 FN=6) |
| **ParticipantExtractor** | F1 | **81.7%** | P=69.7% R=98.7% (MAE=175.9, outliers) |

### Résultats sur 93 articles (liver resection, 2026-02-27)

| Module | Métrique | Score |
|---|---|---|
| **RegionDetector** | F1 | **100.0%** (60/60) |
| **OutcomeExtractor** | F1 | **85.3%** |
| **ParticipantExtractor** | F1 | **82.6%** (MAE=14.9) |

### Historique des benchmarks

| Date | Articles | PE MAE | PE F1 | OE F1 | RD F1 |
|---|---|---|---|---|---|
| Session 2 (initial) | 150 | 283.8 | — | 92.2% | 96.8% |
| Session 3 (post-fix) | 150 | 3.1 | — | 95.0% | 99.2% |
| **2026-02-27** | **200** | **175.9** | **81.7%** | **94.8%** | **100.0%** |

> Note : MAE varie beaucoup entre jeux d'articles (articles multi-bras→parsing erroné).
> Le script `benchmark_nlp_v2.py` est maintenant versionné pour reproductibilité.

---

## 7. Points d'attention & améliorations futures

### Réalisé ✓
- [x] **CITY_TO_COUNTRY** : étendu 91 → 382 (capitales de tous les pays du monde)
- [x] **Commit Git** : `c053390` — tout committé
- [x] **Recréer benchmark_nlp_v2.py** : script complet avec GS heuristique + rapport
- [x] **Tests unitaires nouveaux pays** : 49 tests ajoutés (130 total)

### Pas encore fait
- [ ] **ParticipantExtractor** : améliorer le parsing des études multi-bras (source principale du MAE élevé)
- [ ] **OutcomeExtractor multilingue** : actuellement optimisé EN uniquement, FR partiel
- [ ] **UNIVERSITY_TO_COUNTRY** : reste à 86 entrées — pourrait être enrichi
- [ ] **Push Git** : `git push origin feature/journal-ranking-and-cleanup`

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
     from search.services.region_detector import COUNTRY_TO_REGION, TLD_TO_COUNTRY, CITY_TO_COUNTRY
     from search.services.outcome_extractor import OutcomeExtractor
     from search.services.participant_extractor import ParticipantExtractor
     print('Countries:', len(COUNTRY_TO_REGION))
     print('TLDs:', len(TLD_TO_COUNTRY))
     print('Cities:', len(CITY_TO_COUNTRY))
     oe = OutcomeExtractor()
     print('Primary patterns:', len(oe.PRIMARY_PATTERNS))
     pe = ParticipantExtractor()
     print('Numeric patterns:', len(pe.NUMERIC_PATTERNS))
     "
     ```

3. **Re-lancer le benchmark** :
   ```bash
   python benchmark_nlp_v2.py --articles 200 --query "surgery OR chemotherapy OR clinical trial"
   ```

4. **Mettre à jour §2** après ajout/suppression de tests :
   ```bash
   python -m pytest search/tests/ --tb=short -q
   ```

5. **Mettre à jour la date et le commit** en haut du fichier
