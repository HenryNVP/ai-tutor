from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from ai_tutor.agents.llm_client import LLMClient
from ai_tutor.config.schema import ModelConfig

logger = logging.getLogger(__name__)


# Predefined domain categories and tags
DOMAIN_CATEGORIES = {
    "math": {
        "primary": "mathematics",
        "tags": [
            "algebra", "calculus", "geometry", "trigonometry", "statistics",
            "probability", "linear-algebra", "differential-equations",
            "number-theory", "topology", "analysis", "discrete-math"
        ],
        "keywords": [
            "equation", "theorem", "proof", "derivative", "integral",
            "matrix", "vector", "function", "limit", "series"
        ]
    },
    "physics": {
        "primary": "physics",
        "tags": [
            "mechanics", "thermodynamics", "electromagnetism", "optics",
            "quantum-mechanics", "relativity", "astrophysics", "particle-physics",
            "statistical-mechanics", "wave-mechanics", "fluid-dynamics"
        ],
        "keywords": [
            "force", "energy", "momentum", "wave", "particle", "field",
            "electric", "magnetic", "quantum", "relativity", "thermodynamics"
        ]
    },
    "cs": {
        "primary": "computer-science",
        "tags": [
            "programming", "algorithms", "data-structures", "software-engineering",
            "machine-learning", "artificial-intelligence", "networking", "databases",
            "operating-systems", "computer-architecture", "cybersecurity", "web-development"
        ],
        "keywords": [
            "algorithm", "programming", "code", "software", "data structure",
            "computer", "network", "database", "system", "application"
        ]
    },
    "chemistry": {
        "primary": "chemistry",
        "tags": [
            "organic-chemistry", "inorganic-chemistry", "physical-chemistry",
            "biochemistry", "analytical-chemistry", "thermodynamics", "kinetics"
        ],
        "keywords": [
            "molecule", "reaction", "compound", "element", "bond", "catalyst",
            "organic", "inorganic", "synthesis", "equilibrium"
        ]
    },
    "biology": {
        "primary": "biology",
        "tags": [
            "cell-biology", "genetics", "evolution", "ecology", "anatomy",
            "physiology", "molecular-biology", "biochemistry", "microbiology"
        ],
        "keywords": [
            "cell", "DNA", "gene", "organism", "evolution", "ecosystem",
            "protein", "enzyme", "metabolism", "organism"
        ]
    },
    "general": {
        "primary": "general",
        "tags": ["general-knowledge", "education", "reference"],
        "keywords": []
    }
}

# Valid domain names
VALID_DOMAINS = set(DOMAIN_CATEGORIES.keys())


@dataclass
class DomainClassification:
    """Result of domain classification for a document."""
    
    primary_domain: str
    secondary_domains: List[str]
    confidence: float
    tags: List[str]
    reasoning: Optional[str] = None
    
    def to_metadata(self) -> Dict[str, any]:
        """Convert to metadata dictionary for storage."""
        return {
            "primary_domain": self.primary_domain,
            "secondary_domains": ",".join(self.secondary_domains) if self.secondary_domains else "",
            "domain_tags": ",".join(self.tags) if self.tags else "",
            "domain_confidence": self.confidence,
        }


class DomainClassifier:
    """
    Classifies documents into domains using rule-based heuristics and AI detection.
    
    Supports:
    - Predefined domain categories (math, physics, cs, chemistry, biology, general)
    - Primary and secondary domain assignment
    - Tag-based classification
    - AI-powered detection for ambiguous documents
    """
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        use_ai_detection: bool = True,
    ):
        """
        Initialize domain classifier.
        
        Parameters
        ----------
        llm_client : Optional[LLMClient]
            LLM client for AI-based domain detection. If None, only rule-based
            classification is used.
        use_ai_detection : bool
            Whether to use AI detection for ambiguous cases. Default True.
        """
        self.llm_client = llm_client
        self.use_ai_detection = use_ai_detection and llm_client is not None
        self.domain_categories = DOMAIN_CATEGORIES
        self.valid_domains = VALID_DOMAINS
    
    def classify_from_path(self, path: Path) -> DomainClassification:
        """
        Classify domain from file path using filename and directory heuristics.
        
        This is a fast, rule-based method suitable for initial classification.
        For more accurate results, use classify_from_content().
        
        The method checks:
        1. Parent directory name (if matches a valid domain, high confidence)
        2. Filename keywords and tags
        """
        filename_lower = path.name.lower()
        
        # Check parent directory name first (strong signal)
        parent_dir = path.parent.name.lower() if path.parent.name else ""
        directory_domain = None
        if parent_dir in self.valid_domains:
            directory_domain = parent_dir
        
        # Check each domain's keywords in filename
        domain_scores: Dict[str, float] = {}
        for domain, info in self.domain_categories.items():
            score = 0.0
            
            # Strong boost if parent directory matches domain
            if directory_domain == domain:
                score += 5.0  # High confidence for directory match
            
            # Check tags in filename
            for tag in info["tags"]:
                if tag.replace("-", " ") in filename_lower or tag in filename_lower:
                    score += 2.0
            
            # Check keywords in filename
            for keyword in info["keywords"]:
                if keyword in filename_lower:
                    score += 1.0
            
            if score > 0:
                domain_scores[domain] = score
        
        # Determine primary and secondary domains
        if domain_scores:
            sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
            primary = sorted_domains[0][0]
            secondary = [d for d, _ in sorted_domains[1:3] if _ > 0]  # Top 2 secondary
            
            # Higher confidence if directory matched
            if directory_domain == primary:
                confidence = 0.9  # High confidence for directory match
            else:
                confidence = min(1.0, sorted_domains[0][1] / 5.0)  # Normalize confidence
        else:
            # If no matches but directory is a valid domain, use it
            if directory_domain:
                primary = directory_domain
                secondary = []
                confidence = 0.8  # Good confidence for directory-only match
            else:
                primary = "general"
                secondary = []
                confidence = 0.3
        
        # Extract tags from filename
        tags = self._extract_tags_from_text(filename_lower)
        
        # Build reasoning message
        if directory_domain:
            reasoning = f"Inferred from directory '{path.parent.name}' and filename: {path.name}"
        else:
            reasoning = f"Inferred from filename: {path.name}"
        
        return DomainClassification(
            primary_domain=primary,
            secondary_domains=secondary,
            confidence=confidence,
            tags=tags,
            reasoning=reasoning
        )
    
    def classify_from_content(
        self,
        text: str,
        filename: Optional[str] = None,
        initial_classification: Optional[DomainClassification] = None,
    ) -> DomainClassification:
        """
        Classify domain from document content using AI detection.
        
        This method uses an LLM to analyze document content and determine
        the most appropriate domain(s). Falls back to rule-based classification
        if AI detection is unavailable or fails.
        
        Parameters
        ----------
        text : str
            Document text content (can be a sample, e.g., first 2000 chars)
        filename : Optional[str]
            Optional filename for context
        initial_classification : Optional[DomainClassification]
            Initial classification from path-based heuristics. Used as fallback
            and for comparison.
        
        Returns
        -------
        DomainClassification
            Classification result with primary/secondary domains and tags
        """
        # If AI detection is disabled or unavailable, use rule-based
        if not self.use_ai_detection:
            if initial_classification:
                return initial_classification
            return self._classify_from_text_rules(text, filename)
        
        try:
            # Use AI to classify
            ai_result = self._classify_with_ai(text, filename)
            
            # Validate AI result
            if ai_result.primary_domain in self.valid_domains:
                return ai_result
            else:
                logger.warning(
                    f"AI returned invalid domain '{ai_result.primary_domain}', "
                    f"falling back to rule-based classification"
                )
        except Exception as e:
            logger.warning(f"AI domain detection failed: {e}, falling back to rule-based")
        
        # Fallback to rule-based
        if initial_classification:
            return initial_classification
        return self._classify_from_text_rules(text, filename)
    
    def _classify_with_ai(
        self,
        text: str,
        filename: Optional[str] = None,
    ) -> DomainClassification:
        """Use LLM to classify document domain."""
        # Sample text for efficiency (first 2000 chars should be enough)
        sample_text = text[:2000] if len(text) > 2000 else text
        
        # Build prompt
        domain_list = ", ".join(sorted(self.valid_domains))
        prompt = f"""Analyze the following document and classify its domain(s).

Available domains: {domain_list}

Document filename: {filename or "unknown"}
Document sample:
---
{sample_text}
---

For each domain, consider:
- Primary domain: The main subject area (required, must be one of: {domain_list})
- Secondary domains: Related subject areas (0-2 domains, comma-separated)
- Tags: Specific topics within the domain (3-5 tags, comma-separated)
- Confidence: How confident you are (0.0-1.0)

Respond in JSON format:
{{
    "primary_domain": "math",
    "secondary_domains": ["physics"],
    "tags": ["calculus", "mechanics", "differential-equations"],
    "confidence": 0.95,
    "reasoning": "Brief explanation of classification"
}}

Only respond with valid JSON, no additional text."""

        messages = [
            {
                "role": "system",
                "content": "You are a domain classification expert. Analyze educational documents and classify them into appropriate academic domains."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = self.llm_client.generate(messages, temperature=0.1)
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            response_clean = response.strip()
            if response_clean.startswith("```"):
                # Remove markdown code block
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1])
            if response_clean.startswith("```json"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1])
            
            result = json.loads(response_clean)
            
            # Validate and construct classification
            primary = result.get("primary_domain", "general")
            if primary not in self.valid_domains:
                primary = "general"
            
            secondary = result.get("secondary_domains", [])
            if isinstance(secondary, str):
                secondary = [s.strip() for s in secondary.split(",") if s.strip()]
            secondary = [s for s in secondary if s in self.valid_domains][:2]  # Max 2, validate
            
            tags = result.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            
            confidence = float(result.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
            
            reasoning = result.get("reasoning", "AI classification")
            
            return DomainClassification(
                primary_domain=primary,
                secondary_domains=secondary,
                confidence=confidence,
                tags=tags[:5],  # Limit to 5 tags
                reasoning=reasoning
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse AI classification response: {e}")
            logger.debug(f"Response was: {response}")
            raise
    
    def _classify_from_text_rules(
        self,
        text: str,
        filename: Optional[str] = None,
    ) -> DomainClassification:
        """Rule-based classification from text content."""
        text_lower = text.lower()
        
        domain_scores: Dict[str, float] = {}
        for domain, info in self.domain_categories.items():
            if domain == "general":
                continue
            
            score = 0.0
            # Count keyword matches in text
            for keyword in info["keywords"]:
                count = text_lower.count(keyword)
                score += count * 0.5
            
            # Check for tag mentions
            for tag in info["tags"]:
                tag_variants = [tag, tag.replace("-", " "), tag.replace("-", "")]
                for variant in tag_variants:
                    if variant in text_lower:
                        score += 1.0
                        break
            
            if score > 0:
                domain_scores[domain] = score
        
        # Determine primary and secondary
        if domain_scores:
            sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
            primary = sorted_domains[0][0]
            secondary = [d for d, _ in sorted_domains[1:3] if _ > 0.5]
            confidence = min(1.0, sorted_domains[0][1] / 10.0)
        else:
            primary = "general"
            secondary = []
            confidence = 0.3
        
        tags = self._extract_tags_from_text(text_lower)
        
        return DomainClassification(
            primary_domain=primary,
            secondary_domains=secondary,
            confidence=confidence,
            tags=tags,
            reasoning="Rule-based classification from content"
        )
    
    def _extract_tags_from_text(self, text: str) -> List[str]:
        """Extract relevant tags from text based on domain categories."""
        tags = []
        text_lower = text.lower()
        
        for domain, info in self.domain_categories.items():
            for tag in info["tags"]:
                tag_variants = [tag, tag.replace("-", " "), tag.replace("-", "")]
                for variant in tag_variants:
                    if variant in text_lower and tag not in tags:
                        tags.append(tag)
                        break
                if len(tags) >= 5:  # Limit tags
                    break
            if len(tags) >= 5:
                break
        
        return tags[:5]
    
    def get_collection_name(self, primary_domain: str) -> str:
        """
        Get ChromaDB collection name for a domain.
        
        Parameters
        ----------
        primary_domain : str
            Primary domain name
        
        Returns
        -------
        str
            Collection name in format: "ai_tutor_{domain}"
        """
        if primary_domain not in self.valid_domains:
            primary_domain = "general"
        return f"ai_tutor_{primary_domain}"
    
    @staticmethod
    def get_all_collection_names() -> List[str]:
        """Get list of all possible collection names."""
        return [f"ai_tutor_{domain}" for domain in sorted(VALID_DOMAINS)]

