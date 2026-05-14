"""
Content Validation Agent - AI Orchestration Layer
Albeni 1905 - Invisible Luxury Ecosystem

Validates AI-generated content BEFORE it is written to Notion.
Based on the original specification documents:
- AI_orchestartion.docx: CQS >= 76, modello 70/30, HITL
- manuale_procedure_AI Orchestration: CQS threshold, 85/15 SEO balance
- Albeni 1905_control_tower.docx: CQS 79/100 target, AI Routing Accuracy >85%
- 13 — SEO STRATEGIC FRAMEWORK: cluster-keyword alignment, cannibalization <6%
- ARCHITETTURA MULTI DOMINIO: domain-funnel mapping, semantic shielding
- protocolli di resilienza: fallback logic, QA protocols

Validation checks:
1. Brand Compliance — tone of voice, forbidden terms, brand axiom
2. Protected Terms — never translate or alter protected terms
3. Technical Accuracy — micronage (17 micron), weights (150g/190g), certifications
4. Cluster Alignment — tone, pain points, key messages match target cluster
5. SEO Check — keyword presence in title/meta, domain-funnel coherence
6. Anti-hallucination — Gemini second-pass verification
7. Domain Coherence — content matches the correct domain's funnel stage
"""
import logging
import json
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ValidationResult:
    """Result of content validation with detailed scoring."""
    overall_score: float = 0.0
    passed: bool = False
    checks: Dict[str, Dict] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "overall_score": self.overall_score,
            "passed": self.passed,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


# ===================================================================
# VALIDATION RULES (from specification documents)
# ===================================================================

# Brand axiom — must be respected, never contradicted
BRAND_AXIOM = "Same Silhouette, Superior Substance"

# Protected terms — NEVER translate, alter, or omit
PROTECTED_TERMS = [
    "Albeni 1905", "Reda 1865", "CompACT", "ZQ",
    "Cut & Sewn", "Material Science", "Invisible Luxury",
    "Merino", "Super 120's"
]

# Forbidden terms — NEVER appear in content (from AI_orchestartion.docx)
FORBIDDEN_TERMS = {
    "it": ["abbigliamento sportivo", "underwear", "fast fashion", "sconto", "saldi",
           "economico", "low cost", "cheap", "offerta speciale", "promozione aggressiva",
           "lana fresca"],
    "en": ["sportswear", "underwear", "fast fashion", "discount", "sale",
           "cheap", "low cost", "budget", "bargain", "fresh wool"],
    "de": ["Sportbekleidung", "Unterwäsche", "Fast Fashion", "Rabatt", "Schlussverkauf",
           "billig", "günstig", "frische Wolle"],
    "fr": ["vêtement de sport", "sous-vêtement", "fast fashion", "soldes", "remise",
           "pas cher", "bon marché", "laine fraîche"],
}

# Technical facts that MUST be accurate (from manuale_procedure)
TECHNICAL_FACTS = {
    "micronage": "17",          # Always 17 micron, never other values
    "weights": ["150g", "190g"],  # Only these two weights
    "certifications": ["ZQ"],
    "construction": "Cut & Sewn",  # Never "knit" or "knitted"
    "heritage_years": "270",       # 270+ years (Albeni 1905 + Reda 1865)
}

# Cluster-specific validation rules (from AI_orchestartion.docx)
CLUSTER_VALIDATION = {
    "business_professional": {
        "required_themes": ["performance", "thermal", "blazer", "travel", "boardroom"],
        "tone": "direct, efficient, performance-oriented",
        "forbidden_themes": ["heritage", "artisan", "craft", "tradition"],
        "target_domain": "perfectmerinoshirt.com",
    },
    "heritage_mature": {
        "required_themes": ["heritage", "quality", "investment", "tradition", "270"],
        "tone": "elegant, cultured, deep",
        "forbidden_themes": ["trendy", "modern", "minimalist", "capsule"],
        "target_domain": "albeni1905.com",
    },
    "conscious_premium": {
        "required_themes": ["sustainability", "ZQ", "ethical", "transparent", "environment"],
        "tone": "conscious, informed, empathetic",
        "forbidden_themes": ["luxury excess", "status symbol", "exclusive"],
        "target_domain": "worldofmerino.com",
    },
    "modern_minimalist": {
        "required_themes": ["minimal", "capsule", "versatile", "essential", "design"],
        "tone": "essential, direct, modern",
        "forbidden_themes": ["baroque", "ornate", "traditional", "vintage"],
        "target_domain": "perfectmerinoshirt.com",
    },
    "italian_authentic": {
        "required_themes": ["Italy", "made in Italy", "artisan", "thermal", "comfort"],
        "tone": "warm, authentic, proud",
        "forbidden_themes": ["clinical", "cold", "technical only"],
        "target_domain": "albeni1905.com",
    },
}

# Domain-Funnel coherence rules (from ARCHITETTURA MULTI DOMINIO)
DOMAIN_FUNNEL_MAP = {
    "worldofmerino.com": {
        "allowed_stages": ["TOFU"],
        "role": "hub informativo tecnico, lifestyle, cultura merino",
        "forbidden_content": ["pricing", "buy now", "add to cart"],
    },
    "merinouniversity.com": {
        "allowed_stages": ["TOFU", "MOFU"],
        "role": "contenuti formativi, guide, comparazioni",
        "forbidden_content": ["pricing", "buy now"],
    },
    "perfectmerinoshirt.com": {
        "allowed_stages": ["MOFU", "BOFU"],
        "role": "educational + MOFU orientato all'acquisto",
        "forbidden_content": [],
    },
    "albeni1905.com": {
        "allowed_stages": ["BOFU"],
        "role": "commerciale, heritage, conversione",
        "forbidden_content": [],
    },
}

# Language-specific register rules (from manuale_procedure)
LANGUAGE_REGISTER = {
    "it": {"register": "formale ma accessibile", "check": None},
    "en": {"register": "sophisticated, warm", "forbidden": ["fresh wool"], "use": "lightweight superfine wool"},
    "de": {"register": "Sachlich-elegant, formell", "check": "Sie", "forbidden": ["du ", " dir ", " dich "]},
    "fr": {"register": "élégant, raffiné", "check": "vous", "forbidden": [" tu ", " te ", " toi "]},
}


class ContentValidator:
    """
    Validates AI-generated content against brand rules, technical accuracy,
    cluster alignment, SEO requirements, and domain coherence.

    Uses Gemini for anti-hallucination second-pass when available.
    """

    def __init__(self):
        self.gemini_model = None
        if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
            except Exception as e:
                logger.warning(f"Gemini init for validator failed: {e}")

    async def validate(self, content: Dict, cluster: str, language: str,
                       content_type: str, domain: str = "",
                       keyword_target: str = "", funnel_stage: str = "") -> ValidationResult:
        """
        Run all validation checks on generated content.
        Returns ValidationResult with score, pass/fail, and detailed feedback.
        """
        result = ValidationResult()
        content_str = json.dumps(content, ensure_ascii=False).lower()

        # 1. Brand Compliance (max 20 points)
        brand_score, brand_details = self._check_brand_compliance(content_str, language)
        result.checks["brand_compliance"] = {"score": brand_score, "max": 20, **brand_details}

        # 2. Protected Terms (max 10 points)
        protected_score, protected_details = self._check_protected_terms(content, content_str)
        result.checks["protected_terms"] = {"score": protected_score, "max": 10, **protected_details}

        # 3. Technical Accuracy (max 20 points)
        tech_score, tech_details = self._check_technical_accuracy(content_str)
        result.checks["technical_accuracy"] = {"score": tech_score, "max": 20, **tech_details}

        # 4. Cluster Alignment (max 20 points)
        cluster_score, cluster_details = self._check_cluster_alignment(content_str, cluster)
        result.checks["cluster_alignment"] = {"score": cluster_score, "max": 20, **cluster_details}

        # 5. SEO Check (max 15 points)
        seo_score, seo_details = self._check_seo(content, keyword_target, content_type)
        result.checks["seo_compliance"] = {"score": seo_score, "max": 15, **seo_details}

        # 6. Domain Coherence (max 10 points)
        domain_score, domain_details = self._check_domain_coherence(content_str, domain, funnel_stage, cluster)
        result.checks["domain_coherence"] = {"score": domain_score, "max": 10, **domain_details}

        # 7. Language Register (max 5 points)
        lang_score, lang_details = self._check_language_register(content_str, language)
        result.checks["language_register"] = {"score": lang_score, "max": 5, **lang_details}

        # 8. Voice Compliance — Anti-AI-tell (Voice Baseline v1.0, Rubric v1.1)
        # Score modifier (negative penalty, max -25) + HARD FAIL gate
        voice_score, voice_details, voice_hard_fail = self._check_voice_compliance(content_str)
        result.checks["voice_compliance"] = {
            "score": voice_score,
            "max": 0,  # additive penalty (negative)
            "hard_fail": voice_hard_fail,
            **voice_details,
        }

        # Calculate overall score (voice_score is negative modifier 0..-25)
        total_score = brand_score + protected_score + tech_score + cluster_score + seo_score + domain_score + lang_score + voice_score
        result.overall_score = round(max(0, total_score), 1)
        # Voice HARD FAIL forces passed=False regardless of score
        result.passed = (total_score >= settings.CONTENT_QUALITY_MIN) and (not voice_hard_fail)

        # Collect all errors and warnings
        for check_name, check_data in result.checks.items():
            for error in check_data.get("errors", []):
                result.errors.append(f"[{check_name}] {error}")
            for warning in check_data.get("warnings", []):
                result.warnings.append(f"[{check_name}] {warning}")
            for suggestion in check_data.get("suggestions", []):
                result.suggestions.append(f"[{check_name}] {suggestion}")

        logger.info(f"Content validation: CQS={result.overall_score}/100, passed={result.passed}, "
                     f"errors={len(result.errors)}, warnings={len(result.warnings)}")

        return result

    async def validate_with_ai(self, content: Dict, cluster: str, language: str,
                                keyword_target: str = "") -> Dict:
        """
        Second-pass AI validation using Gemini for anti-hallucination check.
        Asks Gemini to verify factual claims in the generated content.
        """
        if not self.gemini_model:
            return {"ai_validation": "skipped", "reason": "Gemini not available"}

        content_str = json.dumps(content, ensure_ascii=False)

        # --- DATA HUB CONTEXT INJECTION ---
        hub_context = ""
        try:
            from services.context_provider import DataHubContextProvider
            ctx_provider = DataHubContextProvider()
            context = ctx_provider.get_context(
                agent_id="content_validator",
                task_type="validation",
                market=language,
                max_chars=2000,
            )
            if context["instructions_text"]:
                hub_context = context["instructions_text"] + "\n\n"
                logger.info(f"Content Validator enriched with {context['total_sources']} Data Hub sources")
        except Exception as e:
            logger.debug(f"Data Hub context not available for validator: {e}")
        # --- END CONTEXT INJECTION ---

        validation_prompt = f"""{hub_context}Sei il Quality Assurance Agent di Albeni 1905.
Analizza il seguente contenuto generato dall'AI e verifica:

1. ACCURATEZZA TECNICA: Il micronaggio è SEMPRE 17 micron? Le grammature sono solo 150g o 190g? La costruzione Albeni è Cut & Sewn (MAI "knit"). ECCEZIONE: in articoli comparativi (es. "Cut & Sew vs Knit") l'uso di "knit" per contrasto è ammesso.
2. COERENZA BRAND: Il tono rispetta "Same Silhouette, Superior Substance"? Non ci sono riferimenti a sportswear, underwear, fast fashion?
3. TERMINI PROTETTI: Albeni 1905, Reda 1865, ZQ, Cut & Sewn, Material Science, Invisible Luxury sono presenti e corretti?
4. HALLUCINATION CHECK: Ci sono affermazioni inventate, statistiche false, o claim non verificabili?
5. CLUSTER CHECK: Il contenuto è coerente con il cluster "{cluster}"?

CONTENUTO DA VALIDARE:
{content_str[:3000]}

Rispondi SOLO con un JSON valido:
{{
    "factual_accuracy": true/false,
    "brand_coherence": true/false,
    "protected_terms_ok": true/false,
    "hallucinations_found": [],
    "issues": [],
    "overall_verdict": "PASS" o "FAIL" o "REVIEW",
    "confidence": 0.0-1.0
}}"""

        try:
            import time
            time.sleep(2)  # Rate limit buffer
            response = self.gemini_model.generate_content(
                validation_prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for factual analysis
                    "response_mime_type": "application/json"
                }
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())

        except Exception as e:
            logger.error(f"AI validation failed: {e}")
            return {"ai_validation": "error", "reason": str(e)}

    # ===================================================================
    # INDIVIDUAL VALIDATION CHECKS
    # ===================================================================

    def _check_brand_compliance(self, content_str: str, language: str) -> Tuple[float, Dict]:
        """Check brand axiom, forbidden terms, tone of voice."""
        score = 20.0
        details = {"errors": [], "warnings": [], "suggestions": []}

        # Check forbidden terms
        forbidden = FORBIDDEN_TERMS.get(language, FORBIDDEN_TERMS["it"])
        found_forbidden = [term for term in forbidden if term.lower() in content_str]
        if found_forbidden:
            penalty = min(10, len(found_forbidden) * 3)
            score -= penalty
            details["errors"].append(f"Termini vietati trovati: {', '.join(found_forbidden)}")

        # Check brand axiom presence (at least spirit of it)
        axiom_keywords = ["silhouette", "substance", "superior", "invisible luxury"]
        axiom_present = sum(1 for k in axiom_keywords if k in content_str)
        if axiom_present == 0:
            score -= 3
            details["warnings"].append("Nessun riferimento al brand axiom 'Same Silhouette, Superior Substance' o 'Invisible Luxury'")

        # Check for competitor mentions (should never appear)
        competitors = ["smartwool", "icebreaker", "allbirds", "asket", "unbound merino", "uniqlo"]
        found_competitors = [c for c in competitors if c in content_str]
        if found_competitors:
            score -= 5
            details["errors"].append(f"Menzione competitor: {', '.join(found_competitors)}")

        details["found_forbidden"] = found_forbidden
        return max(0, score), details

    def _check_protected_terms(self, content: Dict, content_str: str) -> Tuple[float, Dict]:
        """Check that protected terms are present and not altered."""
        score = 10.0
        details = {"errors": [], "warnings": [], "suggestions": [], "found": [], "missing": []}

        for term in PROTECTED_TERMS:
            if term.lower() in content_str:
                details["found"].append(term)
            else:
                # Not all terms need to be in every piece of content
                # But key ones like brand names should be
                if term in ["Albeni 1905", "Merino"]:
                    score -= 2
                    details["warnings"].append(f"Termine protetto mancante: {term}")
                details["missing"].append(term)

        # Check for mistranslations of protected terms
        mistranslations = {
            "taglio e cucito": "Cut & Sewn",
            "scienza dei materiali": "Material Science",
            "lusso invisibile": "Invisible Luxury",
            "schnitt und naht": "Cut & Sewn",
            "coupe et couture": "Cut & Sewn",
        }
        for wrong, correct in mistranslations.items():
            if wrong in content_str:
                score -= 3
                details["errors"].append(f"Termine protetto tradotto: '{wrong}' dovrebbe restare '{correct}'")

        return max(0, score), details

    def _check_technical_accuracy(self, content_str: str) -> Tuple[float, Dict]:
        """Check micronage, weights, construction method, heritage years."""
        score = 20.0
        details = {"errors": [], "warnings": [], "suggestions": []}

        # Check micronage — must be 17, never other values
        micron_pattern = r'(\d+)\s*micron'
        micron_matches = re.findall(micron_pattern, content_str)
        for match in micron_matches:
            if match != "17":
                score -= 8
                details["errors"].append(f"Micronaggio errato: {match} micron (deve essere 17 micron)")

        if "17" in content_str and "micron" in content_str:
            pass  # Correct
        elif "micron" in content_str:
            score -= 3
            details["warnings"].append("Mancato riferimento esplicito a '17 micron'")

        # Check weights — only 150g or 190g
        weight_pattern = r'(\d+)\s*g(?:ramm|/)'
        weight_matches = re.findall(weight_pattern, content_str)
        for match in weight_matches:
            if match not in ["150", "190"]:
                score -= 5
                details["errors"].append(f"Grammatura errata: {match}g (solo 150g o 190g)")

        # Check construction — must be Cut & Sewn, not knit
        # EXCEPTION: comparative content (e.g. "Cut & Sew vs Knit") may legitimately mention knit
        is_comparative = any(kw in content_str for kw in [
            " vs ", " versus ", " contro ", " rispetto ", " compared ",
            " comparison ", " confronto ", " vergleich ", " comparaison ",
            " vs. ", " differ", " alternativ"
        ])
        knit_terms = ["knit", "knitted", "maglia", "tricot", "strick", "gestrickt"]
        found_knit = [t for t in knit_terms if t in content_str]
        if found_knit:
            if is_comparative:
                # In comparative content, knit mentions are expected — just warn, no penalty
                details["suggestions"].append(
                    f"Contenuto comparativo: '{', '.join(found_knit)}' usato per contrasto con Cut & Sewn (OK)")
            else:
                score -= 8
                details["errors"].append(
                    f"Costruzione errata: trovato '{', '.join(found_knit)}' — deve essere 'Cut & Sewn'")

        # Check heritage years
        heritage_pattern = r'(\d+)\+?\s*(?:anni|years|jahre|ans)'
        heritage_matches = re.findall(heritage_pattern, content_str)
        for match in heritage_matches:
            if int(match) < 250 or int(match) > 300:
                if int(match) not in [120, 160, 161]:  # Allow individual brand ages
                    score -= 3
                    details["warnings"].append(f"Heritage errato: {match} anni (dovrebbe essere 270+)")

        return max(0, score), details

    def _check_cluster_alignment(self, content_str: str, cluster: str) -> Tuple[float, Dict]:
        """Check content matches the target cluster's themes and tone."""
        score = 20.0
        details = {"errors": [], "warnings": [], "suggestions": [], "themes_found": [], "themes_missing": []}

        cluster_rules = CLUSTER_VALIDATION.get(cluster, {})
        if not cluster_rules:
            details["warnings"].append(f"Nessuna regola di validazione per cluster: {cluster}")
            return 15.0, details

        # Check required themes
        required = cluster_rules.get("required_themes", [])
        found_themes = [t for t in required if t.lower() in content_str]
        missing_themes = [t for t in required if t.lower() not in content_str]

        details["themes_found"] = found_themes
        details["themes_missing"] = missing_themes

        if len(found_themes) == 0:
            score -= 12
            details["errors"].append(f"Nessun tema del cluster {cluster} trovato. Attesi: {', '.join(required)}")
        elif len(found_themes) < len(required) / 2:
            penalty = min(8, (len(required) - len(found_themes)) * 2)
            score -= penalty
            details["warnings"].append(f"Temi mancanti: {', '.join(missing_themes)}")

        # Check forbidden themes for this cluster
        forbidden = cluster_rules.get("forbidden_themes", [])
        found_forbidden = [t for t in forbidden if t.lower() in content_str]
        if found_forbidden:
            score -= min(5, len(found_forbidden) * 2)
            details["warnings"].append(f"Temi non coerenti con il cluster: {', '.join(found_forbidden)}")

        return max(0, score), details

    def _check_seo(self, content: Dict, keyword_target: str, content_type: str) -> Tuple[float, Dict]:
        """Check SEO elements: keyword in title, meta description, content length."""
        score = 15.0
        details = {"errors": [], "warnings": [], "suggestions": []}

        if not keyword_target:
            details["suggestions"].append("Nessuna keyword target specificata — SEO check parziale")
            return 10.0, details

        keyword_lower = keyword_target.lower()

        # Check keyword in title
        title = str(content.get("title", content.get("hero_headline", content.get("subject", "")))).lower()
        if keyword_lower not in title:
            score -= 5
            details["warnings"].append(f"Keyword target '{keyword_target}' non presente nel titolo")

        # Check keyword in meta description
        meta = str(content.get("meta_description", "")).lower()
        if meta and keyword_lower not in meta:
            score -= 3
            details["warnings"].append(f"Keyword target '{keyword_target}' non presente nella meta description")

        # Check meta description length (from SEO STRATEGIC FRAMEWORK: 155 chars)
        if meta:
            if len(meta) > 160:
                score -= 2
                details["warnings"].append(f"Meta description troppo lunga: {len(meta)} chars (max 155)")
            elif len(meta) < 80:
                score -= 1
                details["suggestions"].append(f"Meta description troppo corta: {len(meta)} chars (ideale 120-155)")

        # Check content length
        content_str = json.dumps(content, ensure_ascii=False)
        if content_type == "blog_draft" and len(content_str) < 1000:
            score -= 3
            details["warnings"].append("Contenuto blog troppo corto (minimo 800-1200 parole)")

        return max(0, score), details

    def _check_domain_coherence(self, content_str: str, domain: str,
                                 funnel_stage: str, cluster: str) -> Tuple[float, Dict]:
        """Check content matches the target domain's funnel role."""
        score = 10.0
        details = {"errors": [], "warnings": [], "suggestions": []}

        if not domain:
            return 8.0, details

        domain_rules = DOMAIN_FUNNEL_MAP.get(domain, {})
        if not domain_rules:
            return 8.0, details

        # Check funnel stage alignment
        allowed_stages = domain_rules.get("allowed_stages", [])
        if funnel_stage and funnel_stage not in allowed_stages:
            score -= 5
            details["errors"].append(
                f"Fase funnel '{funnel_stage}' non coerente con dominio {domain} "
                f"(ammesse: {', '.join(allowed_stages)})"
            )

        # Check forbidden content for domain
        forbidden = domain_rules.get("forbidden_content", [])
        found_forbidden = [f for f in forbidden if f.lower() in content_str]
        if found_forbidden:
            score -= 3
            details["warnings"].append(
                f"Contenuto non appropriato per {domain}: {', '.join(found_forbidden)}"
            )

        # Check cluster-domain alignment
        cluster_rules = CLUSTER_VALIDATION.get(cluster, {})
        target_domain = cluster_rules.get("target_domain", "")
        if target_domain and domain and target_domain != domain:
            score -= 2
            details["suggestions"].append(
                f"Cluster '{cluster}' ha come dominio target '{target_domain}', "
                f"ma il contenuto è per '{domain}'"
            )

        return max(0, score), details

    def _check_language_register(self, content_str: str, language: str) -> Tuple[float, Dict]:
        """Check formal register compliance per language."""
        score = 5.0
        details = {"errors": [], "warnings": [], "suggestions": []}

        lang_rules = LANGUAGE_REGISTER.get(language, {})
        if not lang_rules:
            return 5.0, details

        # Check forbidden informal forms
        forbidden = lang_rules.get("forbidden", [])
        found_informal = [f for f in forbidden if f.lower() in content_str]
        if found_informal:
            score -= 3
            details["errors"].append(
                f"Registro informale rilevato in lingua '{language}': "
                f"trovato {', '.join(found_informal)} — usare registro formale"
            )

        return max(0, score), details

    def _check_voice_compliance(self, content_str: str):
        """
        Voice Baseline v1.0 + Rubric v1.1 — anti-AI-tell compliance check.
        Returns: (score_modifier, details, hard_fail_flag)
          score_modifier: 0 to -25 (negative penalty deducted from total_score)
          hard_fail_flag: True if blacklist HARD_FAIL pattern matches → forces passed=False
        Patterns embedded in code (Voice Baseline universale §2.1-§2.5).
        Reference: voice-baseline-albeni-content.md v1.0, rubric-v1.1.md
        """
        import re
        score_modifier = 0.0
        details = {"errors": [], "warnings": [], "suggestions": []}
        hard_fail = False

        text = content_str  # already lowercased by validate()

        # §2.1 Superlativi / parole-bandiera
        BLACKLIST_SUPER = [
            r"\brivoluzionari[oae]\b", r"\bstraordinari[oae]\b",
            r"\bincredibil[ei]\b", r"\bepocali?\b", r"\biconic[oae]\b",
            r"\bmust[\s-]have\b", r"\bintramontabil[ei]\b",
            r"\b(deve|devono) avere\b", r"\bogni guardarob[ao]\b",
        ]
        for pat in BLACKLIST_SUPER:
            if re.search(pat, text):
                score_modifier -= 3
                details["errors"].append(f"§2.1 superlativo AI-tell vietato: {pat}")
                hard_fail = True
                break

        # §2.2 Connettori retorici AI
        BLACKLIST_CONN = [
            r"\bnon e un caso che\b", r"\bnon e' un caso che\b",
            r"\bnon a caso\b",
            r"\bin un'epoca in cui\b", r"\bin un epoca in cui\b",
            r"\bin un mondo (in cui|dove)\b", r"\bnel cuore di\b",
            r"\bimmagina (un mondo|un'epoca|un futuro|un guardaroba) in cui\b",
            r"\bnon e (utopia|fantascienza|magia|fantasia)[:.]\s*(e|e solo)\b",
        ]
        for pat in BLACKLIST_CONN:
            if re.search(pat, text):
                score_modifier -= 5
                details["errors"].append(f"§2.2 connettore retorico AI-tell: {pat}")
                hard_fail = True
                break

        # §2.3 Antitesi cascata (3+ occorrenze = HARD)
        ANTITESI_PATTERNS = [
            r"\b[nN]on (e|sono|fa|si tratta|porta|si celebra|riguarda)\s+.{1,80}?,\s+(ma|e|porta|si rende|si tratta)\s+",
            r"\b[nN]on (e|sono|si tratta)( solo| soltanto)?\s+.{1,80}?[:.]\s*[eE]\b",
        ]
        antitesi_count = 0
        for pat in ANTITESI_PATTERNS:
            antitesi_count += len(re.findall(pat, text, re.IGNORECASE))
        if antitesi_count >= 3:
            score_modifier -= 10
            details["errors"].append(f"§2.3 antitesi cascata: {antitesi_count} occorrenze (>=3 = HARD FAIL)")
            hard_fail = True
        elif antitesi_count >= 1:
            score_modifier -= 3 * antitesi_count
            details["warnings"].append(f"§2.3 antitesi: {antitesi_count} occorrenza/e (soft penalty)")

        # §2.4 Chiusure morali / aforistiche
        BLACKLIST_CLOSURE = [
            r"\buna lezione (che|da)\b",
            r"\bforse (la|e|sembra)\s+.{1,30}?\b(lezione|verita|lettura|chiave)\b",
            r"\b(era|e stato) solo bastato (dirlo|capirlo|notarlo|nominarlo)\b",
            r"\bcomincia da (questa|questo|quella|quello)\s+(domanda|gesto|capo|silenzio|scelta)\b",
            r"\b(porta|reca) (in se)?\s*.{1,30}?\s+(impronta|traccia|memoria) di\b",
            r"\bvale la pena\s+(fissare|sottolineare|notare|ricordare|considerare)\b",
        ]
        for pat in BLACKLIST_CLOSURE:
            if re.search(pat, text):
                score_modifier -= 5
                details["errors"].append(f"§2.4 chiusura morale/aforistica AI-tell: {pat}")
                hard_fail = True
                break

        # §2.5 Apertura narrativo-letteraria (prime 200 char)
        opening = text[:200].strip()
        OPENING_PATTERNS = [
            r"^[c]'(?:e|era) (?:un|una|un')\s+\w+",
            r"^immagina\s+(?:un|una|un')\s+(?:mondo|epoca|futuro|capo|guardaroba)",
            r"^per\s+\w+\s+\w+,?\s+\w+\s+(?:ha|e|si e)\s+(?:smesso|tornato|chiuso|aperto|cominciato)",
            r"^quando\s+(?:il|la|lo|i|le|gli|un|una)\s+\w+\s+(?:incontra|si chiude|comincia|si apre|ha smesso)",
        ]
        for pat in OPENING_PATTERNS:
            if re.search(pat, opening, re.IGNORECASE):
                score_modifier -= 8
                details["errors"].append(f"§2.5 apertura narrativo-letteraria AI-tell: {pat}")
                hard_fail = True
                break

        score_modifier = max(score_modifier, -25)

        if hard_fail:
            details["errors"].append(
                "VOICE HARD FAIL — rigenerare il contenuto applicando le 4 regole di "
                "voice-baseline-albeni-content.md: (1) apertura ancora al fatto NOT scena, "
                "(2) max 1 antitesi, (3) chiusura = CTA al Lead Magnet del cluster NOT lezione, "
                "(4) il mercato non parla (no personificazione). Vedere wom-radar-validator/rubric-v1.1.md per dettagli."
            )

        if score_modifier == 0 and not hard_fail:
            details["suggestions"].append("Voice compliance OK — nessun pattern AI-tell rilevato.")

        return score_modifier, details, hard_fail

