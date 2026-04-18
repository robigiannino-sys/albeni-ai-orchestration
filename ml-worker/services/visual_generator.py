"""
Visual Brief Generator — Phase 6 del Merino News Scanner
Genera immagini editoriali per il brief quotidiano Albeni 1905
usando Google Imagen 4 via Gemini API.
"""
import json
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Prompt Templates (embedded for Railway deployment) ──────────────────────

STYLE_GUIDES = {
    "wom": {
        "name": "World of Merino — Lifestyle Mood",
        "base_style": "editorial fashion photography, warm natural light, muted earth tones, quiet luxury aesthetic, Italian elegance, no visible logos, soft depth of field, 35mm film grain",
        "palette": "warm beige, deep navy blue, stone grey, cream white, soft terracotta, muted olive",
        "negative_prompt": "neon colors, artificial lighting, studio backdrop, bold text overlay, clipart, cartoon style, stock photo generic poses, bright saturated colors, logos, brand names",
    },
    "mu": {
        "name": "Merino University — Technical Mood",
        "base_style": "clean minimalist infographic, scientific illustration, data visualization, white background, precise geometric shapes, professional diagram, sans-serif typography",
        "palette": "academic blue, white, light grey, sustainability green accents, warm charcoal for text",
        "negative_prompt": "clipart, cartoon, amateur design, cluttered layout, neon colors, stock photo, photographic style, hand-drawn sketch, childish illustration",
    }
}

TOPIC_TEMPLATES = {
    "W1": {
        "topic": "Quiet Luxury & Nuove Proporzioni del Guardaroba",
        "prompt": "Editorial photograph of a professional adjusting a merino wool blazer cuff, in a sunlit minimalist Italian apartment, warm beige and deep blue palette, natural window light, focus on fabric texture and drape, Vogue Italia editorial aesthetic, quiet luxury, shallow depth of field",
    },
    "W2": {
        "topic": "Efficienza Intelligente e Consumo Consapevole",
        "prompt": "Editorial still life photograph of a curated selection of five essential garments laid flat, on a linen surface with morning light, warm natural tones, thoughtful composition suggesting intentionality, muted earth palette, clean minimal background, contemplative mood",
    },
    "W3": {
        "topic": "Svolta Normativa sulla Sostenibilità",
        "prompt": "Editorial photograph of raw merino wool fibers next to a green plant sprout, in a pastoral Italian landscape, earth tones and green accents, natural textures, warm light suggesting hope and renewal, documentary editorial style, sustainability without preachiness",
    },
    "W4": {
        "topic": "Innovazione nei Viaggi — Micro-viaggi e Bleisure",
        "prompt": "Editorial travel photograph of a leather weekender bag with a single merino outfit visible, at a European boutique hotel entrance, warm golden light, sense of movement and freedom, compact elegance, beige and navy palette, aspirational but attainable",
    },
    "W5": {
        "topic": "Tutela dell'Artigianalità e del Made in Italy",
        "prompt": "Editorial documentary photograph of artisan hands examining merino wool fabric on a loom, inside a historic textile mill in Biella with original machinery, warm amber light, hands as the hero, focus on craft and precision, rich textures, Italian artisanal tradition",
    },
    "M1": {
        "topic": "Scienza delle Fibre e Bio-Ingegneria",
        "prompt": "Clean scientific infographic on white background showing cross-section diagram of a merino wool fiber showing cortex layers, with measurement scales and micron values, academic blue and charcoal color scheme, precise geometric elements, microscopy aesthetic, labeled diagrams with clean sans-serif typography",
    },
    "M2": {
        "topic": "Tracciabilità Istituzionale e Standard Globali",
        "prompt": "Clean minimalist infographic on white background showing supply chain traceability flowchart from farm to finished garment, with certification badge icons at each stage, blue and green color scheme, institutional and authoritative, clean data visualization",
    },
    "M3": {
        "topic": "Sostenibilità Misurabile — LCA",
        "prompt": "Clean scientific infographic on white background showing LCA comparison bar chart merino wool vs polyester vs cotton environmental impact, with CO2 equivalent values and ISO 14067 reference, green and blue sustainability palette, comparative data visualization, precise percentages",
    },
    "M4": {
        "topic": "Innovazioni Tecniche nei Processi Produttivi",
        "prompt": "Clean technical diagram on white background showing CompACT spinning process diagram showing anti-pilling mechanism, with magnified fiber detail callouts, blue and warm charcoal color scheme, engineering blueprint aesthetic, process flow visualization",
    },
    "M5": {
        "topic": "Dermatologia e Salute",
        "prompt": "Clean medical-scientific infographic on white background showing skin microclimate diagram showing wool thermoregulation against skin, with dermatological layer labels and moisture indicators, blue and soft green palette, clinical accuracy combined with accessibility",
    },
}

TOPIC_KEYWORDS = {
    "W1": ["quiet luxury", "guardaroba", "capsule wardrobe", "eleganza", "dress code", "moda", "stile"],
    "W2": ["consumo consapevole", "decision fatigue", "investire", "cost per wear", "acquisto"],
    "W3": ["sostenibilità", "microplastic", "biodegradabil", "circolare", "rinnov", "ban", "normativ"],
    "W4": ["viaggio", "travel", "bleisure", "micro-trip", "bagaglio", "luggage", "mobilità"],
    "W5": ["made in italy", "artigian", "biella", "lanificio", "tessile", "manifattur", "sartori", "distretto"],
    "M1": ["fibra", "fiber", "keratina", "micron", "nociceptor", "prickle", "bio-ingegneria", "termoregol"],
    "M2": ["IWTO", "tracciabilità", "eBale", "Fibercoin", "ZQ", "ZQRX", "EMI", "standard", "certificaz"],
    "M3": ["LCA", "carbon", "biodegradabil", "microplastic", "impatto ambient", "ISO 14067", "biogenic"],
    "M4": ["CompACT", "Plasma Tech", "spinning", "filatura", "tessitura", "pilling", "cut and sewn"],
    "M5": ["dermatolog", "atopic", "dermatit", "Staphylococcus", "sleep", "cutaneo", "microclima", "pelle"],
}


# ─── Brief Parser ────────────────────────────────────────────────────────────

def parse_brief(brief_text: str) -> list:
    """Parse a brief markdown string and extract structured data for each FATTO."""
    facts = []
    fatto_blocks = re.split(r'(?=## FATTO #\d+)', brief_text)

    for block in fatto_blocks:
        if not block.strip() or "FATTO #" not in block:
            continue

        fact = {}
        title_match = re.search(r'## FATTO #(\d+)\s*[—–-]\s*(.+)', block)
        if title_match:
            fact["number"] = int(title_match.group(1))
            fact["title"] = title_match.group(2).strip()

        class_match = re.search(r'Classificazione\s*\|?\s*\*?\*?(LIFESTYLE|TECHNICAL|CROSSOVER)', block, re.IGNORECASE)
        if class_match:
            fact["classification"] = class_match.group(1).upper()

        dest_match = re.search(r'Destinazione primaria\s*\|?\s*\*?\*?(WoM|MU|BOTH)', block, re.IGNORECASE)
        if dest_match:
            fact["destination"] = dest_match.group(1)

        # Topic detection by keyword scoring
        block_topics = re.findall(r'\b([WM]\d)\b', block[:500])
        if not block_topics:
            block_lower = block.lower()
            topic_scores = {}
            for topic_code, keywords in TOPIC_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw.lower() in block_lower)
                if score > 0:
                    topic_scores[topic_code] = score
            block_topics = sorted(topic_scores.keys(), key=lambda t: topic_scores[t], reverse=True)
        fact["topics"] = block_topics if block_topics else []

        # Extract narrative angles
        wom_angle = re.search(r'\*\*Narrativo\*\*:\s*(.+?)(?=\n\n|\n\*\*)', block, re.DOTALL)
        if wom_angle:
            fact["wom_narrative"] = wom_angle.group(1).strip()

        mu_angle = re.search(r'\*\*Angolo tecnico\*\*:\s*(.+?)(?=\n\n|\n\*\*)', block, re.DOTALL)
        if mu_angle:
            fact["mu_narrative"] = mu_angle.group(1).strip()

        score_match = re.search(r'Punteggio\s*\|?\s*\*?\*?(\d+(?:\.\d+)?)/10', block)
        if score_match:
            fact["score"] = float(score_match.group(1))

        if fact.get("title"):
            facts.append(fact)

    return facts


# ─── Prompt Composer ─────────────────────────────────────────────────────────

def compose_prompt(fact: dict, destination: str) -> dict:
    """Compose an image generation prompt for a fact + destination."""
    style_key = "wom" if destination == "WoM" else "mu"
    style = STYLE_GUIDES[style_key]

    # Find best matching topic
    prefix = "W" if destination == "WoM" else "M"
    topics = fact.get("topics", [])
    matched = [t for t in topics if t.startswith(prefix) and t in TOPIC_TEMPLATES]
    topic_key = matched[0] if matched else None

    if not topic_key:
        available = [t for t in topics if t in TOPIC_TEMPLATES]
        topic_key = available[0] if available else None

    if topic_key:
        specific_prompt = TOPIC_TEMPLATES[topic_key]["prompt"]
    else:
        if destination == "WoM":
            specific_prompt = f"Editorial photograph inspired by: {fact.get('title', 'merino wool luxury')}. Person in elegant merino wool clothing, Italian setting, warm natural light."
        else:
            specific_prompt = f"Clean minimalist infographic about: {fact.get('title', 'merino wool science')}. Data visualization, white background, blue color scheme."

    final_prompt = f"{style['base_style']}. {specific_prompt}. Color palette: {style['palette']}."

    # Add narrative context
    narrative = fact.get("wom_narrative" if destination == "WoM" else "mu_narrative", "")
    if narrative:
        final_prompt += f" Editorial context: {narrative[:200]}"

    return {
        "prompt": final_prompt,
        "negative_prompt": style["negative_prompt"],
        "aspect_ratio": "16:9",
        "description": f"{'Lifestyle' if destination == 'WoM' else 'Technical'} visual for: {fact.get('title', 'Unknown')}",
        "topic": topic_key or "generic",
        "destination": destination,
    }


# ─── Image Generator ─────────────────────────────────────────────────────────

class VisualGenerator:
    """Generates editorial images for Merino News Scanner briefs."""

    def __init__(self, api_key: str, model: str = "imagen-4.0-generate-001"):
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate_image(self, prompt_data: dict) -> Optional[bytes]:
        """Generate an image from a composed prompt. Returns image bytes or None."""
        from google.genai import types

        try:
            result = self.client.models.generate_images(
                model=self.model,
                prompt=prompt_data["prompt"],
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=prompt_data["aspect_ratio"],
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                )
            )
            if result.generated_images:
                return result.generated_images[0].image.image_bytes
            else:
                logger.warning("No image generated (safety filter)")
                return None
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            raise

    def generate_for_brief(self, brief_text: str, max_facts: int = 2) -> list:
        """
        Parse a brief and generate visuals for top facts.
        Returns list of dicts with prompt_data + image_bytes.
        """
        facts = parse_brief(brief_text)
        if not facts:
            return []

        facts_sorted = sorted(facts, key=lambda f: f.get("score", 0), reverse=True)
        results = []

        for fact in facts_sorted[:max_facts]:
            dest = fact.get("destination", "WoM")
            classification = fact.get("classification", "LIFESTYLE")

            destinations = []
            if dest == "BOTH" or classification == "CROSSOVER":
                destinations = ["WoM", "MU"]
            elif dest == "WoM" or classification == "LIFESTYLE":
                destinations = ["WoM"]
            elif dest == "MU" or classification == "TECHNICAL":
                destinations = ["MU"]
            else:
                destinations = ["WoM"]

            for d in destinations:
                prompt_data = compose_prompt(fact, d)
                try:
                    image_bytes = self.generate_image(prompt_data)
                    results.append({
                        "fact_number": fact.get("number", 0),
                        "fact_title": fact.get("title", ""),
                        "destination": d,
                        "topic": prompt_data["topic"],
                        "description": prompt_data["description"],
                        "prompt": prompt_data["prompt"],
                        "image_bytes": image_bytes,
                        "success": image_bytes is not None,
                        "error": None,
                    })
                except Exception as e:
                    results.append({
                        "fact_number": fact.get("number", 0),
                        "fact_title": fact.get("title", ""),
                        "destination": d,
                        "topic": prompt_data["topic"],
                        "description": prompt_data["description"],
                        "prompt": prompt_data["prompt"],
                        "image_bytes": None,
                        "success": False,
                        "error": str(e),
                    })

        return results

    def dry_run(self, brief_text: str, max_facts: int = 2) -> list:
        """Parse brief and compose prompts without generating images."""
        facts = parse_brief(brief_text)
        if not facts:
            return []

        facts_sorted = sorted(facts, key=lambda f: f.get("score", 0), reverse=True)
        results = []

        for fact in facts_sorted[:max_facts]:
            dest = fact.get("destination", "WoM")
            classification = fact.get("classification", "LIFESTYLE")

            destinations = []
            if dest == "BOTH" or classification == "CROSSOVER":
                destinations = ["WoM", "MU"]
            elif dest == "WoM" or classification == "LIFESTYLE":
                destinations = ["WoM"]
            elif dest == "MU" or classification == "TECHNICAL":
                destinations = ["MU"]
            else:
                destinations = ["WoM"]

            for d in destinations:
                prompt_data = compose_prompt(fact, d)
                results.append({
                    "fact_number": fact.get("number", 0),
                    "fact_title": fact.get("title", ""),
                    "destination": d,
                    "topic": prompt_data["topic"],
                    "description": prompt_data["description"],
                    "prompt": prompt_data["prompt"],
                })

        return results
