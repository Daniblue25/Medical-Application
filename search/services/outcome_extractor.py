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
    
    # Patterns regex pour critères principaux (score de confiance selon spécificité)
    PRIMARY_PATTERNS = [
        # High confidence (formulations explicites et complètes)
        (re.compile(r"(the\s+)?primary\s+outcome\s+(?:was|were|is|are)\s+([^.]{10,150}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?primary\s+endpoint\s+(?:was|were|is|are)\s+([^.]{10,150}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"(the\s+)?main\s+outcome\s+(?:was|were|is|are)\s+([^.]{10,150}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"le\s+critère\s+principal\s+(?:était|est)\s+([^.]{10,150}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"l'objectif\s+principal\s+(?:était|est)\s+([^.]{10,150}\.)", re.IGNORECASE), 'high'),
        
        # Medium confidence (formulations avec ":" ou sans verbe explicite)
        (re.compile(r"primary\s+outcome[s]?\s*:\s*([^.]{10,150}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"primary\s+endpoint[s]?\s*:\s*([^.]{10,150}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"main\s+outcome[s]?\s*:\s*([^.]{10,150}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"primary\s+outcome[s]?\s+included\s+([^.]{10,150}\.)", re.IGNORECASE), 'medium'),
        
        # Low confidence (formulations vagues ou courtes)
        (re.compile(r"primary\s+(?:measure|assessment)\s+(?:was|were)\s+([^.]{10,150}\.)", re.IGNORECASE), 'low'),
        (re.compile(r"we\s+(?:assessed|evaluated|measured)\s+([^.]{10,150}\.)", re.IGNORECASE), 'low'),
    ]
    
    # Patterns pour critères secondaires
    SECONDARY_PATTERNS = [
        (re.compile(r"secondary\s+outcome[s]?\s+(?:was|were|is|are|included?)\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"secondary\s+endpoint[s]?\s+(?:was|were|is|are|included?)\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"secondary\s+outcome[s]?\s*:\s*([^.]{10,200}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"critère[s]?\s+secondaire[s]?\s+([^.]{10,200}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"other\s+outcome[s]?\s+included\s+([^.]{10,200}\.)", re.IGNORECASE), 'low'),
    ]
    
    # Patterns pour inclusion
    INCLUSION_PATTERNS = [
        (re.compile(r"inclusion\s+criteria\s+(?:were|was|included?)\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"patients\s+were\s+eligible\s+if\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"eligibility\s+criteria\s+(?:were|included?)\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"critères?\s+d'inclusion\s*:\s*([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"we\s+included\s+patients?\s+(?:who|with|aged)\s+([^.]{10,200}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"patients?\s+aged\s+([^.]{10,150}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"participants?\s+(?:were|included)\s+([^.]{10,150}\.)", re.IGNORECASE), 'low'),
    ]
    
    # Patterns pour exclusion
    EXCLUSION_PATTERNS = [
        (re.compile(r"exclusion\s+criteria\s+(?:were|was|included?)\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"patients\s+were\s+excluded\s+if\s+([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"critères?\s+d'exclusion\s*:\s*([^.]{10,200}\.)", re.IGNORECASE), 'high'),
        (re.compile(r"we\s+excluded\s+patients?\s+(?:who|with)\s+([^.]{10,200}\.)", re.IGNORECASE), 'medium'),
        (re.compile(r"exclusion\s+criteria\s*:\s*([^.]{10,200}\.)", re.IGNORECASE), 'medium'),
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
        """
        # Protéger les abréviations courantes
        text = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof|vs|etc|e\.g|i\.e|cf)\.\s', r'\1<DOT> ', text)
        
        # Split sur . ! ? suivi d'espace et majuscule/chiffre
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text)
        
        # Restaurer les points
        sentences = [s.replace('<DOT>', '.').strip() for s in sentences if s.strip()]
        
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
            for pattern, confidence in patterns:
                match = pattern.search(sentence)
                if match:
                    # Essayer de capturer le groupe 2 (texte après "was/were"), sinon groupe 1
                    extracted_text = match.group(2) if (match.lastindex and match.lastindex >= 2) else match.group(1)
                    
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
            Dictionnaire avec clés: primary_outcome, secondary_outcome, 
            inclusion_criteria, exclusion_criteria + confidence scores
        """
        if not abstract or len(abstract) < 50:
            return {
                "primary_outcome": None,
                "primary_outcome_confidence": None,
                "secondary_outcome": None,
                "secondary_outcome_confidence": None,
                "inclusion_criteria": None,
                "inclusion_confidence": None,
                "exclusion_criteria": None,
                "exclusion_confidence": None,
                "has_outcomes": False
            }
        
        try:
            # Segmentation en phrases
            sentences = cls._segment_sentences(abstract)
            
            # Extraction avec contexte (multi-résultats)
            primary_results = cls._extract_with_context(cls.PRIMARY_PATTERNS, sentences, max_results=2)
            secondary_results = cls._extract_with_context(cls.SECONDARY_PATTERNS, sentences, max_results=2)
            inclusion_results = cls._extract_with_context(cls.INCLUSION_PATTERNS, sentences, max_results=2)
            exclusion_results = cls._extract_with_context(cls.EXCLUSION_PATTERNS, sentences, max_results=2)
            
            # Fusion des résultats multi-phrases
            primary_text, primary_conf = cls._merge_multi_sentence_outcomes(primary_results)
            secondary_text, secondary_conf = cls._merge_multi_sentence_outcomes(secondary_results)
            inclusion_text, inclusion_conf = cls._merge_multi_sentence_outcomes(inclusion_results)
            exclusion_text, exclusion_conf = cls._merge_multi_sentence_outcomes(exclusion_results)
            
            results = {
                "primary_outcome": primary_text,
                "primary_outcome_confidence": primary_conf,
                "secondary_outcome": secondary_text,
                "secondary_outcome_confidence": secondary_conf,
                "inclusion_criteria": inclusion_text,
                "inclusion_confidence": inclusion_conf,
                "exclusion_criteria": exclusion_text,
                "exclusion_confidence": exclusion_conf,
                "has_outcomes": bool(primary_text or secondary_text or inclusion_text or exclusion_text)
            }
            
            logger.debug(f"[OutcomeExtractor] Extracted {sum(1 for k, v in results.items() if v and 'confidence' not in k)} criteria")
            return results
            
        except Exception as e:
            logger.error(f"[OutcomeExtractor] Error extracting outcomes: {e}")
            return {
                "primary_outcome": None,
                "primary_outcome_confidence": None,
                "secondary_outcome": None,
                "secondary_outcome_confidence": None,
                "inclusion_criteria": None,
                "inclusion_confidence": None,
                "exclusion_criteria": None,
                "exclusion_confidence": None,
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
