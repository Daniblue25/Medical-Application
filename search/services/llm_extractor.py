"""
LLM-based participant extraction using Ollama
Supports local models like Llama3.2, Meditron, BioMistral
"""

import requests
import json
import logging
import re
from typing import Optional, Dict
import os

logger = logging.getLogger(__name__)

class LLMParticipantExtractor:
    """
    Extract participant information using Ollama local LLM
    Automatically falls back to regex if Ollama is unavailable
    """
    
    # Ollama API configuration
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))
    
    # Model priority: fast models first, specialized models optional
    PREFERRED_MODELS = [
        "llama3.2:3b",      # Fast, lightweight (3GB) - RECOMMENDED
        "llama3.2:1b",      # Ultra-fast (1.3GB)
        "meditron:7b",      # Medical-specialized (4.1GB)
        "biomistral:7b",    # Biomedical-specialized (4.1GB)
        "llama3:8b"         # Larger general model
    ]
    
    @classmethod
    def _check_ollama_available(cls) -> bool:
        """Check if Ollama is running locally"""
        try:
            response = requests.get(
                "http://localhost:11434/api/tags", 
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    @classmethod
    def _get_available_model(cls) -> Optional[str]:
        """Get first available model from preferred list"""
        try:
            response = requests.get(
                "http://localhost:11434/api/tags", 
                timeout=2
            )
            if response.status_code == 200:
                installed_models = [m['name'] for m in response.json().get('models', [])]
                
                # Check for preferred models
                for preferred in cls.PREFERRED_MODELS:
                    if preferred in installed_models:
                        logger.info(f"✓ Using Ollama model: {preferred}")
                        return preferred
                
                # Fallback to first installed model
                if installed_models:
                    fallback_model = installed_models[0]
                    logger.warning(f"Using fallback Ollama model: {fallback_model}")
                    return fallback_model
                    
        except Exception as e:
            logger.error(f"Error checking Ollama models: {e}")
        
        return None
    
    @classmethod
    def extract_sample_size_llm(cls, abstract: str) -> Dict:
        """
        Extract sample size using Ollama LLM with intelligent fallback
        
        Args:
            abstract: Medical abstract text
            
        Returns:
            dict: {
                'sample_size': int or None,
                'confidence': 'high' | 'medium' | 'low' | 'none',
                'matched_text': str,
                'method': 'llm' | 'regex_fallback'
            }
        """
        
        if not abstract or len(abstract.strip()) < 20:
            return {
                'sample_size': None,
                'confidence': 'none',
                'matched_text': '',
                'method': 'no_abstract'
            }
        
        # Check if Ollama is available
        if not cls._check_ollama_available():
            logger.debug("Ollama not available, using regex fallback")
            return cls._regex_fallback(abstract)
        
        model = cls._get_available_model()
        if not model:
            logger.debug("No Ollama model found, using regex fallback")
            return cls._regex_fallback(abstract)
        
        # Construct optimized prompt for medical abstract
        prompt = cls._build_prompt(abstract)
        
        try:
            # Call Ollama API
            response = requests.post(
                cls.OLLAMA_API_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,     # Low temp for factual extraction
                        "top_p": 0.9,
                        "num_predict": 30,      # Short response expected
                        "stop": ["\n", "Explanation:", "Note:"]  # Stop tokens
                    }
                },
                timeout=cls.OLLAMA_TIMEOUT
            )
            
            if response.status_code != 200:
                logger.warning(f"Ollama API returned {response.status_code}, using regex fallback")
                return cls._regex_fallback(abstract)
            
            result = response.json()
            llm_response = result.get('response', '').strip()
            
            logger.debug(f"LLM response: {llm_response}")
            
            # Parse LLM response
            return cls._parse_llm_response(llm_response, abstract)
            
        except requests.exceptions.Timeout:
            logger.warning(f"Ollama timeout after {cls.OLLAMA_TIMEOUT}s, using regex fallback")
            return cls._regex_fallback(abstract)
        except Exception as e:
            logger.error(f"LLM extraction error: {e}, using regex fallback")
            return cls._regex_fallback(abstract)
    
    @classmethod
    def _build_prompt(cls, abstract: str) -> str:
        """Build optimized prompt for sample size extraction"""
        return f"""Extract the TOTAL number of participants from this medical study abstract.

RULES:
1. Find the MAIN study population (e.g., "119 individuals participated")
2. IGNORE subgroups (e.g., "N = 59" in parentheses)
3. Look for phrases like: "total", "participated", "enrolled", "recruited", "included"
4. Return ONLY a number or "NONE"
5. If multiple numbers, return the LARGEST representing the total cohort

ABSTRACT:
{abstract[:800]}

TOTAL PARTICIPANTS (number only):"""

    @classmethod
    def _parse_llm_response(cls, llm_response: str, abstract: str) -> Dict:
        """Parse and validate LLM response"""
        
        # Check for "NONE" response
        if llm_response.upper() in ["NONE", "NOT FOUND", "N/A", "UNKNOWN"]:
            return {
                'sample_size': None,
                'confidence': 'high',
                'matched_text': 'LLM: No sample size found',
                'method': 'llm'
            }
        
        # Extract first number from response
        numbers = re.findall(r'\d+', llm_response)
        
        if not numbers:
            logger.warning(f"LLM returned no number: '{llm_response}', using regex fallback")
            return cls._regex_fallback(abstract)
        
        # Take first number (usually the most relevant)
        sample_size = int(numbers[0])
        
        # Validate reasonable range
        if not (1 <= sample_size <= 1000000):
            logger.warning(f"LLM returned unreasonable number: {sample_size}, using regex fallback")
            return cls._regex_fallback(abstract)
        
        # Verify in abstract for confidence scoring
        confidence = cls._verify_in_abstract(abstract, sample_size)
        
        # Get matched text from abstract if possible
        matched_text = cls._find_matched_text(abstract, sample_size)
        
        return {
            'sample_size': sample_size,
            'confidence': confidence,
            'matched_text': matched_text or f'LLM extracted: {llm_response}',
            'method': 'llm'
        }
    
    @classmethod
    def _verify_in_abstract(cls, abstract: str, sample_size: int) -> str:
        """
        Verify if extracted number appears in abstract with proper context
        Returns confidence level: 'high', 'medium', or 'low'
        """
        size_str = str(sample_size)
        
        # High confidence patterns (number with strong context)
        high_confidence_patterns = [
            rf'(?:in\s+)?total[,\s]+{size_str}\s+(?:participants?|patients?|subjects?|individuals?)',
            rf'{size_str}\s+(?:participants?|patients?|subjects?|individuals?)\s+(?:participated|were\s+enrolled|were\s+included)',
            rf'total\s+of\s+{size_str}\s+(?:participants?|patients?|subjects?)',
            rf'(?:study|trial)\s+(?:enrolled|included|recruited)\s+{size_str}'
        ]
        
        for pattern in high_confidence_patterns:
            if re.search(pattern, abstract, re.IGNORECASE):
                return 'high'
        
        # Medium confidence patterns (number appears with keywords nearby)
        medium_confidence_patterns = [
            rf'{size_str}.*(?:participants?|patients?|subjects?)',
            rf'(?:participants?|patients?|subjects?).*{size_str}',
            rf'[Nn]\s*=\s*{size_str}(?!\s*-)'  # N = X but not N = X-Y (range)
        ]
        
        for pattern in medium_confidence_patterns:
            if re.search(pattern, abstract, re.IGNORECASE):
                return 'medium'
        
        # Low confidence: number exists but without strong context
        if size_str in abstract:
            return 'low'
        
        # Very low confidence: LLM inferred (number not directly in abstract)
        return 'low'
    
    @classmethod
    def _find_matched_text(cls, abstract: str, sample_size: int) -> Optional[str]:
        """Extract the actual sentence/phrase containing the sample size"""
        size_str = str(sample_size)
        
        # Try to find the sentence containing the number
        sentences = abstract.split('.')
        for sentence in sentences:
            if size_str in sentence and any(keyword in sentence.lower() for keyword in 
                ['participant', 'patient', 'subject', 'individual', 'enrolled', 'recruited']):
                return sentence.strip()[:100]  # Max 100 chars
        
        return None
    
    @classmethod
    def _regex_fallback(cls, abstract: str) -> Dict:
        """Fallback to improved regex-based extraction"""
        from .participant_extractor import ParticipantExtractor
        result = ParticipantExtractor.extract_sample_size(abstract)
        result['method'] = 'regex_fallback'
        return result


# Convenience function for direct usage
def extract_participants(abstract: str, use_llm: bool = True) -> Dict:
    """
    Extract participants from abstract with optional LLM enhancement
    
    Args:
        abstract: Medical abstract text
        use_llm: If True, try LLM first then fallback to regex. If False, use regex only.
    
    Returns:
        dict with sample_size, confidence, matched_text, method
    """
    if use_llm:
        return LLMParticipantExtractor.extract_sample_size_llm(abstract)
    else:
        from .participant_extractor import ParticipantExtractor
        return ParticipantExtractor.extract_sample_size(abstract)
