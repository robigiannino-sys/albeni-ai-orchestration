"""
AI Content Generation Engine (70/30 Model)
Generates personalized content for each cluster using Google Gemini or OpenAI.
70% AI-generated, 30% Human-in-the-loop review required.

Brand Axiom: "Same Silhouette, Superior Substance"
"""
import logging
import json
import time
from typing import Dict, Optional
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from config import get_settings
from models.database import ContentGenerationLog
from models.schemas import ContentGenerationRequest, ContentGenerationResponse, IntentStage

logger = logging.getLogger(__name__)
settings = get_settings()


# System prompts per cluster
SYSTEM_PROMPT_BASE = """Sei il Creative Director di Albeni 1905.
Assioma fondamentale: "Same Silhouette, Superior Substance".
Tone of Voice: Autorevole, sobrio, colto. Mai posizionare come abbigliamento sportivo o intimo.
Brand heritage: 270+ anni di eccellenza tessile (Albeni 1905 + Reda 1865).
Materiale: Fibra Merino 17 micron Reda, costruzione Cut & Sewn (non knit).
Non menzionare mai: abbigliamento sportivo, underwear, fast fashion, sconti aggressivi."""
# Voice Guidelines v1.0 — Anti-AI-tell (Voice Baseline universale, rubric v1.1)
# Reference: voice-baseline-albeni-content.md
VOICE_GUIDELINES_v1 = """
LINEE GUIDA DI VOCE — REGOLE ANTI-AI-TELL (Voice Baseline v1.0, Rubric v1.1)

Applica queste 4 regole-base prima di emettere QUALSIASI contenuto editoriale:

1. APERTURA ANCORATA AL FATTO, NON ALLA SCENA.
   - VIETATO aprire con: "C'e un X che", "Immagina un mondo in cui", "Per N giorni Y ha smesso", "Quando il X incontra".
   - OBBLIGATORIO aprire con: data + soggetto + verbo + numero/fonte.

2. ANTITESI MAX UNA NEL PEZZO.
   - VIETATO in cascata: "Non X, ma Y" / "Non e X: e Y" / "Non e X, non e Y, non e Z. E W".
   - 3+ antitesi = hard-fail AI-tell. Riformulare le ulteriori in forma affermativa.

3. CHIUSURA = CTA AL LEAD MAGNET DEL CLUSTER, NON LEZIONE.
   - VIETATO chiudere con: "Forse la lezione piu semplice", "Era solo bastato dirlo", "comincia da questa domanda".
   - OBBLIGATORIO chiudere con rimando esplicito al Lead Magnet del cluster bersaglio:
     C1 Business Professional -> Business Layering Guide
     C2 Heritage Mature -> La Guida Definitiva ai Tessuti Nobili
     C3 Conscious Premium -> Filiera Reda - 270 anni di responsabilita
     C4 Modern Minimalist -> Wardrobe Essentials Minimalist Edition
     C5 Italian Authentic -> Guida all'uso quotidiano (150/190)

4. IL MERCATO NON PARLA, LE PERSONE PARLANO.
   - VIETATO: "Il mercato ha preso parola", "L'industria sta dicendo", "La filiera sussurra".
   - VIETATO ammicco al lettore: "di nuovo", "come sapevamo", "per chi vuole ascoltare".
   - Soggetti narranti: autore (giornalistico) + fonti nominate (McKinsey, Commissione UE, AgResearch, Reda).

BLACKLIST IMMEDIATA - Se generi anche UNA di queste, RIGENERA:
- rivoluzionario, straordinario, incredibile, epocale, iconico
- must-have, deve avere, ogni guardaroba, intramontabile
- "non e un caso che", "in un'epoca in cui", "in un mondo in cui"
- "Immagina un mondo in cui", "Non e utopia: e"
- "vale la pena ricordare/sottolineare/fissare"

Self-check post-output: scansiona il testo contro questa lista. Se 1+ pattern -> riscrivi.
"""


CLUSTER_PROMPTS = {
    "business_professional": {
        "focus": "Alleata del lavoro quotidiano. Enfatizza stabilita termica 12 ore e vestibilita sotto blazer.",
        "tone": "Diretto, efficiente, orientato alla performance.",
        "pain_points": "Sudorazione sotto la giacca, pieghe dopo voli lunghi, disagio termico in riunioni.",
        "key_messages": [
            "La fibra Merino 17 micron Reda gestisce l'umidita prima che diventi sudore",
            "Stabilita termica dalla boardroom alla cena",
            "Zero pieghe dopo 12 ore di volo"
        ],
        "routing_domain": "perfectmerinoshirt.com"
    },
    "heritage_mature": {
        "focus": "Investimento e qualita permanente. 270 anni di storia Albeni+Reda, lusso discreto, Cut & Sewn.",
        "tone": "Profondo, elegante, colto. Evoca tradizione e valore duraturo.",
        "pain_points": "Stanchezza del consumismo, ricerca di qualita permanente, desiderio di distinzione discreta.",
        "key_messages": [
            "L'eredita di 270 anni: un investimento che non invecchia mai",
            "Costruzione Cut & Sewn per stabilita dimensionale decennale",
            "Smetti di comprare per la persona che vorresti sembrare"
        ],
        "routing_domain": "albeni1905.com"
    },
    "conscious_premium": {
        "focus": "Sostenibilita e lusso etico. Certificazione ZQ, tracciabilita, impatto ambientale positivo.",
        "tone": "Consapevole, informato, empatico. Dati concreti su sostenibilita.",
        "pain_points": "Greenwashing, mancanza di trasparenza, senso di colpa nel consumo.",
        "key_messages": [
            "Certificazione ZQ: tracciabilita dal pascolo al prodotto finito",
            "Fibra naturale rinnovabile che si rigenera con l'aria",
            "Lusso che rispetta chi lo produce e chi lo indossa"
        ],
        "routing_domain": "worldofmerino.com"
    },
    "modern_minimalist": {
        "focus": "Design pulito, versatilita, capsule wardrobe. Un capo, infinite combinazioni.",
        "tone": "Essenziale, diretto, moderno. Meno e meglio.",
        "pain_points": "Armadio pieno di capi inutili, decisioni quotidiane sul vestirsi, ricerca dell'essenziale.",
        "key_messages": [
            "Un capo progettato per eliminare le decisioni superflue",
            "La base perfetta per il tuo guardaroba essenziale",
            "Design invisibile, sostanza superiore"
        ],
        "routing_domain": "perfectmerinoshirt.com"
    },
    "italian_authentic": {
        "focus": "Made in Italy, artigianalita, comfort termico. La tradizione tessile italiana al servizio del quotidiano.",
        "tone": "Caldo, autentico, orgoglioso. Celebra l'eccellenza italiana.",
        "pain_points": "Disagio termico estivo, capi sintetici irritanti, perdita del saper fare italiano.",
        "key_messages": [
            "La t-shirt che non fa sudare: fibra Merino che regola la temperatura",
            "Fatto in Italia da chi lo fa da 270 anni",
            "Il comfort invisibile che solo la lana merino puo dare"
        ],
        "routing_domain": "albeni1905.com"
    }
}

# Content templates per type
CONTENT_TEMPLATES = {
    "email_copy": {
        "instruction": "Genera un'email di conversione con: Subject (max 60 char), Headline (max 80 char), Body (120-180 parole), CTA (max 6 parole).",
        "format": "JSON con campi: subject, headline, body, cta_label, cta_link"
    },
    "blog_draft": {
        "instruction": "Genera una bozza di articolo pillar (800-1200 parole) ottimizzato SEO con H1, H2, meta description (155 char).",
        "format": "JSON con campi: title, meta_description, sections (array di {heading, content})"
    },
    "landing_copy": {
        "instruction": "Genera copy per landing page BOFU con hero headline, subheadline, 3 benefit points, social proof, CTA.",
        "format": "JSON con campi: hero_headline, subheadline, benefits (array), social_proof, cta_label"
    },
    "lead_magnet": {
        "instruction": "Genera outline per un lead magnet (guida PDF) con titolo, sottotitolo, 5-7 capitoli con abstract.",
        "format": "JSON con campi: title, subtitle, chapters (array di {title, abstract})"
    }
}

# Language-specific instructions
LANGUAGE_INSTRUCTIONS = {
    "it": "Scrivi in italiano. Registro: formale ma accessibile.",
    "en": "Write in English. Never use 'fresh wool' (semantic error), use 'lightweight superfine wool'. Register: sophisticated, warm.",
    "fr": "Ecris en francais. Registre: elegant, raffine. Vouvoiement obligatoire.",
    "de": "Schreibe auf Deutsch. Register: Sachlich-elegant (formell, prazise, warm aber engineering-oriented). Siezen ist Pflicht.",
    "es": "Escribe en espanol. Registro: elegante, sofisticado. Usted obligatorio."
}

# Non-translatable terms
PROTECTED_TERMS = [
    "Albeni 1905", "Reda 1865", "CompACT", "ZQ", "Merino",
    "Cut & Sewn", "Material Science", "Invisible Luxury"
]


class ContentGenerator:
    """
    Generates personalized content following the 70/30 model.
    AI produces 70%, human editor reviews and refines 30%.
    Supports Google Gemini (default) and OpenAI as providers.
    """

    def __init__(self, db: DBSession):
        self.db = db
        self.provider = settings.AI_PROVIDER  # "gemini" or "openai"
        self.gemini_model = None
        self.openai_client = None

        if self.provider == "gemini" and settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
                logger.info(f"Gemini initialized with model: {settings.GEMINI_MODEL}")
            except Exception as e:
                logger.warning(f"Gemini init failed: {e}")

        elif self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info(f"OpenAI initialized with model: {settings.OPENAI_MODEL}")
            except Exception as e:
                logger.warning(f"OpenAI init failed: {e}")

    async def generate(self, request: ContentGenerationRequest) -> ContentGenerationResponse:
        """Generate personalized content for a specific cluster and language."""

        cluster = request.cluster.value
        language = request.language
        content_type = request.content_type

        # Build the prompt
        system_prompt = self._build_system_prompt(cluster, language)
        user_prompt = self._build_user_prompt(cluster, language, content_type, request.custom_context)

        # --- DATA HUB CONTEXT INJECTION ---
        try:
            from services.context_provider import DataHubContextProvider
            ctx_provider = DataHubContextProvider()
            context = ctx_provider.get_context(
                agent_id="content_generator",
                task_type=content_type,
                market=language,
                max_chars=4000,
            )
            if context["instructions_text"]:
                system_prompt = context["instructions_text"] + "\n\n" + system_prompt
                logger.info(f"Content Generator enriched with {context['total_sources']} Data Hub sources ({context['categories_covered']})")
        except Exception as e:
            logger.debug(f"Data Hub context not available: {e}")
        # --- END CONTEXT INJECTION ---

        # Generate content
        generated_content = {}
        tokens_used = 0
        model_used = "fallback"

        # P0.2a (2026-05-12): log esplicito quando il provider configurato
        # ma il client non si è inizializzato → root cause del fallback silente.
        if self.provider == "gemini" and not self.gemini_model:
            logger.warning(
                "Provider=gemini ma gemini_model is None. "
                f"GEMINI_API_KEY set: {bool(settings.GEMINI_API_KEY)}. "
                "Vedi /v1/diagnostics/ai-provider per dettagli init."
            )
        elif self.provider == "openai" and not self.openai_client:
            logger.warning("Provider=openai ma openai_client is None. OPENAI_API_KEY may be missing.")

        # Try Gemini first (default provider) with retry for rate limits
        if self.provider == "gemini" and self.gemini_model:
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(
                        full_prompt,
                        generation_config={
                            "temperature": 0.7,
                            "response_mime_type": "application/json"
                        }
                    )

                    raw_content = response.text
                    # Clean JSON from potential markdown code blocks
                    if raw_content.startswith("```"):
                        raw_content = raw_content.split("```")[1]
                        if raw_content.startswith("json"):
                            raw_content = raw_content[4:]

                    generated_content = json.loads(raw_content.strip())
                    model_used = settings.GEMINI_MODEL

                    # Estimate tokens (Gemini doesn't always return exact count)
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        tokens_used = getattr(response.usage_metadata, 'total_token_count', 0)
                    else:
                        tokens_used = len(full_prompt.split()) + len(raw_content.split())

                    logger.info(f"Gemini content generated successfully on attempt {attempt + 1}")
                    break  # Success, exit retry loop

                except Exception as e:
                    error_str = str(e)
                    is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower()
                    if is_rate_limit and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 15  # 15s, 30s
                        logger.warning(f"Gemini rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Gemini content generation failed after {attempt + 1} attempts: {e}")
                        generated_content = self._get_fallback_content(cluster, language, content_type)
                        break

        # Try OpenAI as alternative
        elif self.provider == "openai" and self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )

                raw_content = response.choices[0].message.content
                generated_content = json.loads(raw_content)
                tokens_used = response.usage.total_tokens if response.usage else 0
                model_used = settings.OPENAI_MODEL

            except Exception as e:
                logger.error(f"OpenAI content generation failed: {e}")
                generated_content = self._get_fallback_content(cluster, language, content_type)

        else:
            # No provider configured: return template content
            generated_content = self._get_fallback_content(cluster, language, content_type)

        # Calculate quality score (simplified heuristic)
        quality_score = self._estimate_quality(generated_content, cluster, content_type)

        # Log to database
        log_entry = ContentGenerationLog(
            target_cluster=cluster,
            target_language=language,
            content_type=content_type,
            target_domain=CLUSTER_PROMPTS.get(cluster, {}).get("routing_domain", ""),
            intent_stage=request.intent_stage.value,
            generated_content=json.dumps(generated_content, ensure_ascii=False),
            content_quality_score=quality_score,
            human_review_status="pending",
            model_used=model_used,
            prompt_tokens=tokens_used // 2 if tokens_used else 0,
            completion_tokens=tokens_used // 2 if tokens_used else 0,
        )
        self.db.add(log_entry)
        self.db.commit()

        return ContentGenerationResponse(
            cluster=cluster,
            language=language,
            content_type=content_type,
            generated_content=generated_content,
            content_quality_score=quality_score,
            model_used=model_used,
            review_status="pending",
            tokens_used=tokens_used
        )

    def _build_system_prompt(self, cluster: str, language: str) -> str:
        """Build the system prompt combining base + cluster + language."""
        cluster_config = CLUSTER_PROMPTS.get(cluster, {})
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["it"])
        protected = ", ".join(PROTECTED_TERMS)

        return f"""{SYSTEM_PROMPT_BASE}

{VOICE_GUIDELINES_v1}

CLUSTER FOCUS: {cluster_config.get('focus', '')}
TONE: {cluster_config.get('tone', '')}
PAIN POINTS del target: {cluster_config.get('pain_points', '')}

MESSAGGI CHIAVE:
{chr(10).join('- ' + m for m in cluster_config.get('key_messages', []))}

LINGUA: {lang_instruction}

TERMINI PROTETTI (mai tradurre): {protected}

REGOLA CRITICA: Tutti i micronaggi (17 micron) e le grammature (150g/190g) devono rimanere identici alla fonte."""

    def _build_user_prompt(self, cluster: str, language: str, content_type: str, custom_context: Optional[str] = None) -> str:
        """Build the user prompt for content generation."""
        template = CONTENT_TEMPLATES.get(content_type, CONTENT_TEMPLATES["email_copy"])
        cluster_config = CLUSTER_PROMPTS.get(cluster, {})

        prompt = f"""Genera contenuto per il cluster "{cluster}" in lingua "{language}".
Dominio di destinazione: {cluster_config.get('routing_domain', 'albeni1905.com')}

{template['instruction']}

Formato output: {template['format']}

Rispondi SOLO con un JSON valido."""

        if custom_context:
            prompt += f"\n\nContesto aggiuntivo: {custom_context}"

        return prompt

    def _estimate_quality(self, content: dict, cluster: str, content_type: str) -> float:
        """
        Estimate content quality score (CQS).
        Simplified heuristic based on completeness and keyword presence.
        Target: >= 76/100
        """
        score = 50.0  # Base score

        # Check completeness
        expected_fields = {
            "email_copy": ["subject", "headline", "body", "cta_label"],
            "blog_draft": ["title", "meta_description"],
            "landing_copy": ["hero_headline", "subheadline", "benefits"],
            "lead_magnet": ["title", "subtitle", "chapters"]
        }

        expected = expected_fields.get(content_type, ["subject"])
        present = sum(1 for f in expected if f in content and content[f])
        completeness = present / len(expected) if expected else 0
        score += completeness * 25  # Up to +25

        # Check for protected terms usage
        content_str = json.dumps(content).lower()
        cluster_config = CLUSTER_PROMPTS.get(cluster, {})
        key_messages = cluster_config.get("key_messages", [])
        keyword_hits = sum(1 for msg in key_messages if any(
            word.lower() in content_str for word in msg.split() if len(word) > 4
        ))
        score += min(15, keyword_hits * 5)  # Up to +15

        # Length check
        total_length = len(content_str)
        if total_length > 200:
            score += 10  # Substantial content

        return min(100, round(score, 1))

    def _get_fallback_content(self, cluster: str, language: str, content_type: str) -> dict:
        """Return template content when OpenAI is unavailable."""
        cluster_config = CLUSTER_PROMPTS.get(cluster, CLUSTER_PROMPTS["business_professional"])

        if content_type == "email_copy":
            return {
                "subject": f"[{cluster.replace('_', ' ').title()}] Scopri il lusso invisibile",
                "headline": cluster_config["key_messages"][0] if cluster_config["key_messages"] else "Invisible Luxury",
                "body": f"Focus: {cluster_config['focus']}",
                "cta_label": "Scopri ora",
                "cta_link": f"https://{cluster_config['routing_domain']}"
            }
        elif content_type == "blog_draft":
            return {
                "title": f"Guida completa: {cluster_config['focus'][:60]}",
                "meta_description": f"Scopri come {cluster_config['pain_points'][:100]}",
                "sections": [{"heading": msg, "content": "..."} for msg in cluster_config["key_messages"]]
            }
        elif content_type == "landing_copy":
            return {
                "hero_headline": cluster_config["key_messages"][0],
                "subheadline": cluster_config["focus"],
                "benefits": cluster_config["key_messages"],
                "social_proof": "Trusted by professionals worldwide",
                "cta_label": "Acquista ora"
            }
        else:
            return {"content": f"[TEMPLATE] Content for {cluster} in {language}"}
