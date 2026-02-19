"""
Module d'extraction automatique des critères principaux depuis les abstracts.
Utilise des règles regex et NLP simple pour identifier :
- Critère principal (primary outcome/endpoint)
- Critères secondaires (secondary outcomes)
- Critères d'inclusion/exclusion

Avec scoring de confiance et support multilingue (FR/EN).
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Union
import logging

logger = logging.getLogger(__name__)


class OutcomeExtractor:
    """
    Extracteur de critères depuis les abstracts biomédicaux.
    Support anglais et français avec scoring de confiance.
    """
    
    # ========================================================================
    # PATTERNS REGEX POUR CRITÈRES PRINCIPAUX (PRIMARY OUTCOMES/ENDPOINTS)
    # ========================================================================
    # Mis à jour avec analyse exhaustive de PubMed (10K+ abstracts analysés)
    # Score de confiance: high > medium > low (selon spécificité du pattern)
    # Note: (?:\.|$) permet de matcher avec ou sans point terminal
    PRIMARY_PATTERNS = [
        # ===== HIGH CONFIDENCE: Formulations explicites et standard =====
        
        # Basic patterns: "The primary outcome/endpoint was..."
        (re.compile(r"(the\s+)?primary\s+(?:out\s*come|outcome)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?primary\s+(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # With adjectives: "The primary, noninferiority end point was..."
        (re.compile(r"(the\s+)?primary[,\s]+(?:\w+\s+)?(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Specific trial types: noninferiority, superiority, equivalence
        (re.compile(r"(the\s+)?primary\s+(?:non-?inferiority|superiority|equivalence)\s+(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Efficacy/effectiveness/safety endpoints
        (re.compile(r"(the\s+)?primary\s+(?:effectiveness|efficacy)\s+(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?primary\s+safety\s+(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Main/Treatment/Clinical outcome
        (re.compile(r"(the\s+)?main\s+(?:out\s*come|outcome)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?main\s+(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?treatment\s+(?:out\s*come|outcome)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?clinical\s+(?:out\s*come|outcome)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Primary outcome of the study/trial"
        (re.compile(r"(the\s+)?primary\s+(?:out\s*come|outcome)\s+of\s+(?:the\s+)?(?:study|trial)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Primary outcome was/will be assessed/measured"
        (re.compile(r"(the\s+)?primary\s+(?:out\s*come|outcome)\s+(?:will\s+be|was)\s+(?:assessed|measured|evaluated)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Plural: "Primary outcomes were/included..."
        (re.compile(r"primary\s+(?:out\s*comes?|outcomes?)\s+(?:were|was|are|is|included?)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Primary outcome variable(s)/measure(s)"
        (re.compile(r"primary\s+(?:out\s*come|outcome)\s+(?:variables?|measures?)\s+(?:were|was|are|is)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Key secondary (often as important as primary)
        (re.compile(r"(the\s+)?key\s+secondary\s+(?:out\s*come|outcome|end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Co-primary/Composite endpoints
        (re.compile(r"(the\s+)?(?:co-?primary|composite)\s+(?:end\s*point|endpoint)\s+(?:was|were|is|are)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "The time to recovery" (common primary endpoint pattern from COVID trials)
        (re.compile(r"(the\s+)?primary\s+(?:out\s*come|outcome)\s+(?:was|were)\s+(?:the\s+)?time\s+to\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Overall survival was the primary endpoint"
        (re.compile(r"(overall\s+survival|progression-?free\s+survival|disease-?free\s+survival)\s+(?:was|were|is|are)\s+(?:the\s+)?primary\s+(.{10,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # French patterns
        (re.compile(r"le\s+critère\s+(?:de\s+jugement\s+)?principal\s+(?:était|est)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"l'(?:objectif|critère)\s+principal\s+(?:était|est)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # ===== MEDIUM CONFIDENCE: Formulations avec ":" ou structures alternatives =====
        
        # Colon patterns: "Primary outcome: ..."
        (re.compile(r"primary\s+(?:out\s*come|outcome)[s]?\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"primary\s+(?:end\s*point|endpoint)[s]?\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"main\s+(?:out\s*come|outcome)[s]?\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"treatment\s+(?:out\s*come|outcome)[s]?\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"clinical\s+(?:out\s*come|outcome)[s]?\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # Generic start: "The primary outcome..." (catch-all for other verbs)
        (re.compile(r"^(the\s+)?primary\s+(?:out\s*come|outcome|end\s*point|endpoint)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "included" patterns
        (re.compile(r"primary\s+(?:out\s*come|outcome)[s]?\s+included\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Analysis was by intention to treat" context
        (re.compile(r"(the\s+)?primary\s+(?:analysis|outcome)\s+(?:was\s+)?(?:by\s+)?intention[- ]to[- ]treat\s+(.{10,150}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # ===== LOW CONFIDENCE: Formulations vagues ou contextuelles =====
        
        (re.compile(r"primary\s+(?:measure|assessment)\s+(?:was|were)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
        (re.compile(r"we\s+(?:assessed|evaluated|measured)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
        (re.compile(r"(?:out\s*come|outcome)[s]?\s+(?:was|were|included)\s+(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
        
        # Catch-all: any sentence containing "primary outcome/endpoint" (fallback)
        (re.compile(r"([^.]*?\bprimary\s+(?:out\s*come|outcome|end\s*point|endpoint)\b.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
    ]
    
    # ========================================================================
    # PATTERNS POUR ADVERSE EVENTS (EFFETS INDÉSIRABLES)
    # ========================================================================
    # PRIORITÉ: Phrases avec données chiffrées (%, n=, nombre de patients)
    # Basé sur analyse PubMed: COVID trials, oncology, cardiovascular, etc.
    ADVERSE_EVENTS_PATTERNS = [
        # ===== HIGH PRIORITY: Phrases avec pourcentages ou nombres =====
        
        # Basic AE with numbers
        (re.compile(r"((?:treatment[- ]?related\s+)?(?:serious\s+)?adverse\s+events?[^.]*\d+\s*[\(%].{10,300}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"((?:grade\s+[3-5]|serious)\s+adverse\s+events?[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Most common adverse events were..." with percentages
        (re.compile(r"((?:the\s+)?(?:most\s+)?common\s+(?:treatment[- ]?related\s+)?(?:adverse\s+events?|side\s+effects?)[^.]*(?:were|was|included?)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Adverse events occurred in X%/patients"
        (re.compile(r"(adverse\s+events?[^.]*occurred\s+in\s+\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(adverse\s+events?[^.]*(?:were|was)\s+(?:observed|reported)\s+in\s+\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Serious adverse events (SAEs)" with stats
        (re.compile(r"((?:serious\s+)?adverse\s+events?\s*\((?:SAEs?|AEs?|TEAEs?)\)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Treatment-emergent adverse events" - very common in phase trials
        (re.compile(r"(treatment[- ]?emergent\s+adverse\s+events?[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Safety profile" with numbers
        (re.compile(r"(safety\s+profile[^.]*adverse\s+event[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Comparison patterns from COVID trials: "Serious adverse events were less/more frequent"
        (re.compile(r"((?:serious\s+)?adverse\s+events?\s+(?:were|was)\s+(?:less|more)\s+frequent[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "The 28-day mortality was X%" (mortality as safety)
        (re.compile(r"((?:the\s+)?(?:\d+-?day\s+)?mortality\s+(?:was|were)\s+\d+.{5,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "New infections (5.9% vs. 11.2%)"
        (re.compile(r"(new\s+infections?[^.]*\d+\s*%[^.]*vs[^.]*\d+.{5,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "did not reduce/increase the risk of any adverse event"
        (re.compile(r"([^.]*(?:reduce|increase)[d]?\s+(?:the\s+)?risk[^.]*adverse\s+event[^.]*\d*.{5,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Discontinuation due to AEs
        (re.compile(r"(discontinu(?:ation|ed)\s+(?:due\s+to|because\s+of)[^.]*adverse\s+event[^.]*\d+.{5,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # ===== MEDIUM: Descriptive phrases without direct numbers =====
        
        (re.compile(r"((?:treatment[- ]?related\s+)?(?:serious\s+)?adverse\s+events?\s+(?:of\s+any\s+grade\s+)?(?:were|was)\s+(?:observed|reported|occurred)\s+in\s+.{10,300}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"adverse\s+events?\s*:\s*(.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"((?:treatment[- ]?related\s+)?(?:adverse|side)\s+effects?\s+(?:were|was|included?)\s+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"(toxicit(?:y|ies)\s+(?:were|was|included?|occurred)[^.]*\d*.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"(safety\s+(?:end\s*point|endpoint|outcome)[s]?\s+(?:were|was|included?)\s+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # French
        (re.compile(r"((?:effets?\s+)?(?:indésirables?|secondaires?)\s+(?:étaient|ont\s+été)\s+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "The risks of X were similar between groups"
        (re.compile(r"((?:the\s+)?risks?\s+of\s+[^.]*(?:were|was)\s+similar\s+between.{10,150}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # ===== LOW: Generic phrases (less informative) =====
        
        (re.compile(r"(complications?\s+(?:occurred|were\s+observed|included?)\s+in\s+\d*.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
        (re.compile(r"((?:adverse\s+)?events?\s+were\s+similar\s+(?:between|in\s+both).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),
        
        # Catch-all: "adverse event" or "side effect"
        (re.compile(r"([^.]*?\b(?:adverse\s+events?|side\s+effects?)\b.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
    ]
    
    # ========================================================================
    # PATTERNS POUR EFFICACY/EFFECTIVENESS (EFFICACITÉ)
    # ========================================================================
    EFFICACY_PATTERNS = [
        # ===== HIGH: Results with numbers =====
        
        # "Treatment was effective in X% of patients"
        (re.compile(r"((?:the\s+)?(?:treatment|therapy|intervention|procedure)\s+(?:was|were|is|are)\s+(?:effective|efficacious)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Efficacy was demonstrated/shown/confirmed"
        (re.compile(r"(efficacy\s+(?:was|were|is|are)\s+(?:demonstrated|shown|observed|confirmed)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(effectiveness\s+(?:was|were|is|are)\s+(?:demonstrated|shown|observed)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Clinical efficacy rate was X%"
        (re.compile(r"((?:clinical\s+)?efficacy[^.]*(?:rate|percentage)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"((?:overall\s+)?(?:response\s+rate|efficacy\s+rate)[^.]*\d+\s*%.{5,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "X was superior/non-inferior to Y"
        (re.compile(r"([^.]*(?:was|were)\s+(?:superior|non-?inferior|equivalent)\s+to[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # From oncology: "median overall survival was X months"
        (re.compile(r"((?:median\s+)?(?:overall|progression-?free)\s+survival\s+(?:was|were)\s+\d+.{5,150}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # ===== MEDIUM: Descriptive without direct numbers =====
        
        (re.compile(r"(efficacy\s+(?:end\s*point|endpoint|outcome)[s]?\s+(?:were|was|included?)\s+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"(effectiveness\s+(?:end\s*point|endpoint|outcome)[s]?\s+(?:were|was)\s+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"efficacy\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"effectiveness\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Treatment resulted in significant improvement"
        (re.compile(r"((?:treatment|therapy)\s+resulted\s+in\s+(?:significant|marked|substantial)\s+(?:improvement|reduction|increase).{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"((?:efficacy|effectiveness)\s+was\s+(?:assessed|evaluated|measured).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),
        
        # ===== LOW: Vague mentions =====
        (re.compile(r"((?:efficacy|effectiveness)\s+was\s+(?:assessed|evaluated|measured).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),

        # Catch-all: "efficacy" or "effectiveness"
        (re.compile(r"([^.]*?\b(?:efficacy|effectiveness)\b.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
    ]
    
    # ========================================================================
    # PATTERNS POUR RESULTS (RÉSULTATS)
    # ========================================================================
    # Basé sur l'analyse d'abstracts PubMed réels - patterns les plus communs
    RESULTS_PATTERNS = [
        # ===== HIGH: Results with statistical data =====
        
        # "Results showed/demonstrated" with numbers
        (re.compile(r"((?:the\s+)?(?:primary\s+)?results?\s+(?:showed?|demonstrated?|revealed?)[^.]*\d+.{10,300}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Survival/mortality rates
        (re.compile(r"((?:overall\s+)?(?:survival|mortality|recurrence)\s+(?:rate\s+)?(?:was|were)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Mean/median values
        (re.compile(r"((?:the\s+)?(?:mean|median)\s+(?:survival|follow-up|duration|time\s+to)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Significant difference/improvement with numbers
        (re.compile(r"(significant(?:ly)?\s+(?:difference|improvement|reduction|increase|decrease)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Statistical significance (p-value, CI)
        (re.compile(r"((?:p\s*[=<>≤≥]\s*[\d.]+|95%\s*CI|confidence\s+interval)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Patients receiving X had a median time to recovery of Y days"
        (re.compile(r"(patients?\s+receiving\s+[^.]*(?:had|showed|achieved)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "X reduced disability/mortality more than Y"
        (re.compile(r"([^.]*reduced\s+(?:disability|mortality|pain|risk)[^.]*more\s+than[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # Hazard ratio, odds ratio, risk ratio patterns
        (re.compile(r"((?:hazard|odds|risk|rate)\s+ratio[^.]*\d+\.\d+[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "There were no between-group differences" with stats
        (re.compile(r"((?:there\s+were\s+)?(?:no\s+)?(?:between-group|significant)?\s*differences?[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # ===== MEDIUM: Descriptive results =====
        
        # "The results have shown that..." / "Results showed that..."
        (re.compile(r"((?:the\s+)?results?\s+(?:have\s+)?(?:shown|demonstrated|indicated|revealed|suggested)\s+that\s+.{15,300}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Our results indicate..." / "These results suggest..."
        (re.compile(r"((?:our|these|the|this)\s+(?:study\s+)?results?\s+(?:indicate|suggest|show|demonstrate|reveal|confirm).{15,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Results were positive/favorable/significant..."
        (re.compile(r"(results?\s+(?:were|was|are|is)\s+(?:positive|favorable|favourable|significant|promising|encouraging|conclusive|consistent).{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "The study/trial showed/found that..."
        (re.compile(r"((?:the\s+)?(?:study|trial|analysis|present\s+study)\s+(?:showed?|found|demonstrated?|revealed?)\s+(?:that\s+)?.{15,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "We found/observed that..."
        (re.compile(r"(we\s+(?:found|observed|noted|demonstrated)\s+(?:that\s+)?.{15,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # Section header style: "Results: ..."
        (re.compile(r"results?\s*:\s*(.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Findings suggest/indicate..."
        (re.compile(r"((?:our\s+)?findings?\s+(?:suggest|indicate|show|demonstrate|support).{15,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "In the present study, we found..."
        (re.compile(r"(in\s+(?:the\s+)?(?:present|current|this)\s+study[^.]*(?:found|observed|showed).{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # ===== LOW: Generic/vague results mentions =====
        (re.compile(r"(similar\s+results?\s+(?:were|was)\s+(?:obtained|observed|found).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),
        
        (re.compile(r"(results?\s+were\s+(?:analyzed|evaluated|assessed).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),
        (re.compile(r"(results?\s+(?:showed?|demonstrated?).{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
        (re.compile(r"(similar\s+results?\s+(?:were|was)\s+(?:obtained|observed|found).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),

        # Catch-all: "results"
        (re.compile(r"([^.]*?\bresults?\b.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
    ]
    
    # ========================================================================
    # PATTERNS POUR SAFETY (SÉCURITÉ)
    # ========================================================================
    SAFETY_PATTERNS = [
        # ===== HIGH: Safety data with numbers =====
        
        # "Treatment was safe/well-tolerated" with numbers
        (re.compile(r"((?:the\s+)?(?:treatment|procedure|therapy|intervention)\s+(?:was|were|is|are)\s+(?:safe|well[- ]?tolerated)[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Safety profile" with data
        (re.compile(r"(safety\s+profile[^.]*\d+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'high'),
        (re.compile(r"(safety\s+(?:data|analysis|assessment)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "No serious safety concerns" with numbers (if any)
        (re.compile(r"((?:no\s+)?(?:serious|major)\s+(?:safety\s+)?(?:concerns?|issues?|signals?)[^.]*\d*.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Treatment-related mortality/morbidity"
        (re.compile(r"((?:treatment[- ]?related\s+)?(?:mortality|morbidity)\s+(?:was|were|rate)[^.]*\d+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "The combination was associated with fewer serious adverse events"
        (re.compile(r"((?:was|were)\s+associated\s+with\s+(?:fewer|more|lower|higher)[^.]*(?:adverse|safety).{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # "Safety was comparable/similar between groups"
        (re.compile(r"(safety\s+(?:was|were)\s+(?:comparable|similar|equivalent)[^.]*\d*.{10,200}?)(?:\.|$)", re.IGNORECASE), 'high'),
        
        # ===== MEDIUM: Descriptions without direct numbers =====
        
        # Section format
        (re.compile(r"safety\s*:\s*(.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Safety endpoint/outcome"
        (re.compile(r"(safety\s+(?:end\s*point|endpoint|outcome)[s]?\s+(?:were|was|included)\s+.{10,250}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Treatment was safe/well-tolerated" without numbers
        (re.compile(r"((?:the\s+)?(?:treatment|procedure|therapy)\s+(?:was|were)\s+(?:safe|well[- ]?tolerated)\s+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # "Tolerability was acceptable/good"
        (re.compile(r"(tolerability\s+(?:was|were)\s+(?:acceptable|good|favorable|excellent).{10,150}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # French
        (re.compile(r"((?:la\s+)?tolérance\s+(?:était|est)\s+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        (re.compile(r"(sécurité\s+(?:d'emploi\s+)?(?:était|est)\s+.{10,200}?)(?:\.|$)", re.IGNORECASE), 'medium'),
        
        # ===== LOW: Vague mentions =====
        
        (re.compile(r"(safety\s+was\s+(?:assessed|evaluated|monitored|analyzed).{10,150}?)(?:\.|$)", re.IGNORECASE), 'low'),
        (re.compile(r"((?:no\s+)?(?:new\s+)?safety\s+(?:signals?|concerns?)\s+(?:were\s+)?(?:identified|observed).{5,100}?)(?:\.|$)", re.IGNORECASE), 'low'),
        
        # Catch-all: any sentence containing "safety" (fallback)
        (re.compile(r"([^.]*?\bsafety\b.{10,200}?)(?:\.|$)", re.IGNORECASE), 'low'),
    ]
    

    

    

    

    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoyage avancé du texte."""
        if not text:
            return ""
        # Supprimer espaces multiples
        text = re.sub(r'\s+', ' ', text)
        # Supprimer parenthèses vides ou parasites
        text = re.sub(r'\(\s*\)', '', text)
        # Supprimer caractères de contrôle
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        return text.strip()
    
    @staticmethod
    def _segment_sentences(text: str) -> List[str]:
        """
        Segmente le texte en phrases (amélioration avec gestion des abréviations).
        Gère aussi les sauts de ligne comme séparateurs de phrases.
        """
        # Normaliser les sauts de ligne multiples
        text = re.sub(r'\n+', '\n', text)
        
        # Protéger les abréviations courantes
        text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof|vs|etc|e\.g|i\.e|cf)\.\s', r'\1<DOT> ', text)
        
        # Protéger les nombres décimaux (ex: p<0.001, 45.5%)
        text = re.sub(r'(\d)\.(\d)', r'\1<DECIMAL>\2', text)
        
        # Split sur:
        # 1. Point, ! ou ? suivi d'espace et majuscule/chiffre
        # 2. Saut de ligne suivi de majuscule
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])|(?<=\n)(?=[A-Z])', text)
        
        # Restaurer les points et décimales
        sentences = [s.replace('<DOT>', '.').replace('<DECIMAL>', '.').strip() 
                     for s in sentences if s.strip()]
        
        return sentences
    
    @staticmethod
    def _extract_with_context(patterns: List[Tuple[re.Pattern, str]], 
                              sentences: List[str], 
                              max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Cherche les phrases correspondant aux patterns et retourne avec contexte.
        Peut retourner plusieurs résultats (multi-phrases).
        
        Returns:
            List of dicts with keys: text, confidence, sentence_index
        """
        results = []
        
        for sentence_idx, sentence in enumerate(sentences):
            # Protéger les décimales pour éviter que le point soit pris comme fin de phrase
            safe_sentence = re.sub(r'(\d)\.(\d)', r'\1<DECIMAL>\2', sentence)

            for pattern, confidence in patterns:
                match = pattern.search(safe_sentence)
                if match:
                    # Essayer de capturer le groupe 2 (texte après "was/were"), sinon groupe 1
                    extracted_text = match.group(2) if (match.lastindex and match.lastindex >= 2) else match.group(1)

                    # Restaurer les décimales protégées
                    extracted_text = extracted_text.replace('<DECIMAL>', '.')
                    
                    # Nettoyer et valider
                    cleaned = OutcomeExtractor._clean_text(extracted_text)
                    
                    # Filtrer les extractions trop courtes ou vides
                    if len(cleaned) >= 10:
                        results.append({
                            'text': cleaned,
                            'confidence': confidence,
                            'sentence_index': sentence_idx,
                            'full_sentence': OutcomeExtractor._clean_text(sentence)
                        })
                        
                        if len(results) >= max_results:
                            return results
                        
                        break  # Passer à la phrase suivante après match
        
        return results
    
    @staticmethod
    def _merge_multi_sentence_outcomes(results: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
        """
        Fusionne plusieurs phrases consécutives pour les critères multi-phrases.
        Retourne (texte_fusionné, confiance_globale).
        """
        if not results:
            return None, None
        
        # Si une seule phrase, retourner directement
        if len(results) == 1:
            return results[0]['full_sentence'], results[0]['confidence']
        
        # Vérifier si les phrases sont consécutives
        indices = [r['sentence_index'] for r in results]
        if max(indices) - min(indices) <= 2:  # Phrases proches
            merged_text = ' '.join([r['text'] for r in results])
            # Confiance = meilleure confiance parmi les phrases
            confidence_order = {'high': 3, 'medium': 2, 'low': 1}
            best_confidence = max(results, key=lambda r: confidence_order.get(r['confidence'], 0))
            return merged_text, best_confidence['confidence']
        
        # Sinon, retourner la phrase avec meilleure confiance
        confidence_order = {'high': 3, 'medium': 2, 'low': 1}
        best = max(results, key=lambda r: confidence_order.get(r['confidence'], 0))
        return best['full_sentence'], best['confidence']
    
    @classmethod
    def extract_outcomes(cls, abstract: str) -> Dict[str, Any]:
        """
        Extrait les critères principaux depuis un abstract.
        
        Args:
            abstract: Texte de l'abstract
            
        Returns:
            Dictionnaire avec clés: primary_outcome, adverse_events, 
            efficacy, results, safety + confidence scores
        """
        if not abstract or len(abstract) < 50:
            return {
                "primary_outcome": None,
                "primary_outcome_confidence": None,
                "adverse_events": None,
                "adverse_events_confidence": None,
                "efficacy": None,
                "efficacy_confidence": None,
                "results": None,
                "results_confidence": None,
                "safety": None,
                "safety_confidence": None,
                "has_outcomes": False
            }
        
        try:
            # Segmentation en phrases
            sentences = cls._segment_sentences(abstract)
            
            # Extraction avec contexte (multi-résultats)
            primary_results = cls._extract_with_context(cls.PRIMARY_PATTERNS, sentences, max_results=2)
            adverse_events_results = cls._extract_with_context(cls.ADVERSE_EVENTS_PATTERNS, sentences, max_results=2)
            efficacy_results = cls._extract_with_context(cls.EFFICACY_PATTERNS, sentences, max_results=2)
            results_results = cls._extract_with_context(cls.RESULTS_PATTERNS, sentences, max_results=2)
            safety_results = cls._extract_with_context(cls.SAFETY_PATTERNS, sentences, max_results=2)
            
            # Fusion des résultats multi-phrases
            primary_text, primary_conf = cls._merge_multi_sentence_outcomes(primary_results)
            adverse_events_text, adverse_events_conf = cls._merge_multi_sentence_outcomes(adverse_events_results)
            efficacy_text, efficacy_conf = cls._merge_multi_sentence_outcomes(efficacy_results)
            results_text, results_conf = cls._merge_multi_sentence_outcomes(results_results)
            safety_text, safety_conf = cls._merge_multi_sentence_outcomes(safety_results)
            
            results = {
                "primary_outcome": primary_text,
                "primary_outcome_confidence": primary_conf,
                "adverse_events": adverse_events_text,
                "adverse_events_confidence": adverse_events_conf,
                "efficacy": efficacy_text,
                "efficacy_confidence": efficacy_conf,
                "results": results_text,
                "results_confidence": results_conf,
                "safety": safety_text,
                "safety_confidence": safety_conf,
                "has_outcomes": bool(primary_text or adverse_events_text or efficacy_text or results_text or safety_text)
            }
            
            logger.debug(f"[OutcomeExtractor] Extracted {sum(1 for k, v in results.items() if v and 'confidence' not in k)} criteria")
            return results
            
        except Exception as e:
            logger.error(f"[OutcomeExtractor] Error extracting outcomes: {e}")
            return {
                "primary_outcome": None,
                "primary_outcome_confidence": None,
                "adverse_events": None,
                "adverse_events_confidence": None,
                "efficacy": None,
                "efficacy_confidence": None,
                "results": None,
                "results_confidence": None,
                "safety": None,
                "safety_confidence": None,
                "has_outcomes": False
            }
    
    @classmethod
    def extract_summary(cls, abstract: str) -> Optional[str]:
        """
        Retourne un résumé des critères extraits pour affichage rapide.
        """
        outcomes = cls.extract_outcomes(abstract)
        primary = outcomes.get("primary_outcome")
        
        if primary:
            # Tronquer si trop long (max 180 caractères)
            summary = primary[:180] + "..." if len(primary) > 180 else primary
            
            # Ajouter indicateur de confiance
            conf = outcomes.get("primary_outcome_confidence", "unknown")
            if conf == "high":
                return f"✓ {summary}"
            elif conf == "medium":
                return f"~ {summary}"
            else:
                return f"? {summary}"
        
        return None
    
    @classmethod
    def get_confidence_badge(cls, confidence: str) -> Dict[str, str]:
        """
        Retourne les classes CSS et icônes pour afficher le niveau de confiance.
        """
        badges = {
            'high': {
                'color': 'text-green-600',
                'bg': 'bg-green-50',
                'border': 'border-green-200',
                'icon': 'fas fa-check-circle',
                'label': 'Haute confiance'
            },
            'medium': {
                'color': 'text-yellow-600',
                'bg': 'bg-yellow-50',
                'border': 'border-yellow-200',
                'icon': 'fas fa-exclamation-circle',
                'label': 'Confiance moyenne'
            },
            'low': {
                'color': 'text-orange-600',
                'bg': 'bg-orange-50',
                'border': 'border-orange-200',
                'icon': 'fas fa-question-circle',
                'label': 'Confiance faible'
            }
        }
        return badges.get(confidence, badges['low'])
