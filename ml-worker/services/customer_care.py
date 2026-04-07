"""
Customer Care AI — Multilingua Chatbot
Albeni 1905 — Invisible Luxury Ecosystem

Agente conversazionale che:
1. Risponde in < 22 secondi a domande su sizing, care, materiali
2. Traccia l'intent dell'utente e lo guida nel funnel (IDS routing)
3. Escalation HITL via Klaviyo tag + Notion task quando rileva insoddisfazione
4. Supporta IT, EN, DE, FR con terminologia brand-safe

Architettura:
- Ogni conversazione ha un session_id
- Il bot usa Gemini per risposte AI o un knowledge base statico come fallback
- L'IDS viene aggiornato in base alle domande dell'utente
- Escalation crea un task su Notion + tagga il profilo Klaviyo
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ================================================================
# PRODUCT KNOWLEDGE BASE
# ================================================================

SIZING_GUIDE = {
    "150g": {
        "name": "Lightweight (150g/m²)",
        "season": "Primavera/Estate",
        "temp_range": "18°C–35°C",
        "description": {
            "it": "La versione estiva. Tessuto Reda 150g/m² in fibra Merino Super 120's da 17 micron. Freschezza termica attiva: la fibra gestisce l'umidità prima che diventi sudore. Ideale sotto la giacca nelle giornate calde.",
            "en": "The summer edition. Reda 150g/m² fabric in Super 120's 17-micron Merino fiber. Active thermal freshness: the fiber manages moisture before it becomes sweat. Perfect under a blazer on warm days.",
            "de": "Die Sommerversion. Reda-Gewebe 150g/m² aus Super 120's 17-Mikron-Merinofaser. Aktive thermische Frische: Die Faser reguliert Feuchtigkeit, bevor sie zu Schweiß wird. Ideal unter dem Sakko an warmen Tagen.",
            "fr": "La version estivale. Tissu Reda 150g/m² en fibre Mérinos Super 120's de 17 microns. Fraîcheur thermique active : la fibre gère l'humidité avant qu'elle ne devienne transpiration.",
        },
    },
    "190g": {
        "name": "All-Season (190g/m²)",
        "season": "Tutto l'anno / 4 Stagioni",
        "temp_range": "5°C–28°C",
        "description": {
            "it": "La versione 4 stagioni. Tessuto Reda 190g/m² con la stessa fibra Merino 17 micron ma grammatura più sostanziosa. Regolazione termica che funziona dalla boardroom alla cena. Il capo che elimina la decisione 'cosa mi metto?'.",
            "en": "The all-season edition. Reda 190g/m² fabric with the same 17-micron Merino fiber but a more substantial weight. Thermal regulation that works from the boardroom to dinner. The garment that eliminates the 'what do I wear?' decision.",
            "de": "Die Ganzjahresversion. Reda-Gewebe 190g/m² mit derselben 17-Mikron-Merinofaser, aber mit höherem Gewicht. Thermoregulation, die vom Büro bis zum Abendessen funktioniert.",
            "fr": "La version 4 saisons. Tissu Reda 190g/m² avec la même fibre Mérinos 17 microns mais un grammage plus conséquent. Régulation thermique du bureau au dîner.",
        },
    },
}

# ================================================================
# SIZE & FIT FINDER — Interactive Sizing Calculator
# Mirrors the Shopify widget on albeni1905.com
# ================================================================

# Size data: garment chest measurements in cm per size
# Slim Fit = body + 2cm ease | Regular Fit = body + 6cm ease
SIZE_FIT_DATA = {
    "slim": {
        "ease_cm": 2,
        "label": "Slim Fit",
        "description": {
            "it": "Vestibilità aderente. Silhouette definita che segue il corpo. Ideale sotto giacca o blazer.",
            "en": "Close fit. Defined silhouette that follows the body. Perfect under a jacket or blazer.",
            "de": "Körpernahe Passform. Definierte Silhouette, die dem Körper folgt. Ideal unter Sakko oder Blazer.",
            "fr": "Coupe ajustée. Silhouette définie qui suit le corps. Idéal sous une veste ou un blazer.",
        },
        "sizes": {
            "XS":   {"chest_cm": 92,  "body_range": "86-90"},
            "S":    {"chest_cm": 96,  "body_range": "90-94"},
            "M":    {"chest_cm": 100, "body_range": "94-98"},
            "L":    {"chest_cm": 104, "body_range": "98-102"},
            "XL":   {"chest_cm": 108, "body_range": "102-106"},
            "XXL":  {"chest_cm": 112, "body_range": "106-110"},
            "XXXL": {"chest_cm": 116, "body_range": "110-114"},
        },
    },
    "regular": {
        "ease_cm": 6,
        "label": "Regular Fit",
        "description": {
            "it": "Vestibilità comoda. Più spazio nel busto per libertà di movimento. Perfetta per l'uso quotidiano.",
            "en": "Comfortable fit. More room in the chest for freedom of movement. Perfect for everyday wear.",
            "de": "Bequeme Passform. Mehr Platz im Brustbereich für Bewegungsfreiheit. Perfekt für den Alltag.",
            "fr": "Coupe confortable. Plus d'espace au buste pour la liberté de mouvement. Parfaite au quotidien.",
        },
        "sizes": {
            "XS":   {"chest_cm": 102, "body_range": "86-96"},
            "S":    {"chest_cm": 106, "body_range": "90-100"},
            "M":    {"chest_cm": 110, "body_range": "94-104"},
            "L":    {"chest_cm": 114, "body_range": "98-108"},
            "XL":   {"chest_cm": 118, "body_range": "102-112"},
            "XXL":  {"chest_cm": 124, "body_range": "106-118"},
            "XXXL": {"chest_cm": 128, "body_range": "110-122"},
        },
    },
}

STRETCH_TOLERANCE_CM = 1.0  # Merino stretch factor


def calculate_best_sizes(user_chest: float) -> Dict[str, Any]:
    """
    Calculate the best size for both Slim Fit and Regular Fit
    given the user's chest circumference in cm.

    Algorithm (same as Shopify widget):
        Find first size where: garment_measure + stretch_tolerance >= user_chest + ease
    """
    results = {}

    for fit_key, fit_data in SIZE_FIT_DATA.items():
        ease = fit_data["ease_cm"]
        target = user_chest + ease
        best_size = None

        for size_label, size_info in fit_data["sizes"].items():
            garment = size_info["chest_cm"]
            if garment + STRETCH_TOLERANCE_CM >= target:
                best_size = size_label
                break

        if best_size is None:
            # User exceeds largest size
            largest = list(fit_data["sizes"].keys())[-1]
            largest_cm = fit_data["sizes"][largest]["chest_cm"]
            results[fit_key] = {
                "recommended_size": None,
                "fit_label": fit_data["label"],
                "note": "exceeds_range",
                "largest_available": largest,
                "largest_chest_cm": largest_cm,
            }
        else:
            size_info = fit_data["sizes"][best_size]
            results[fit_key] = {
                "recommended_size": best_size,
                "fit_label": fit_data["label"],
                "garment_chest_cm": size_info["chest_cm"],
                "body_range": size_info["body_range"],
                "ease_cm": ease,
            }

    return {
        "user_chest_cm": user_chest,
        "stretch_tolerance_cm": STRETCH_TOLERANCE_CM,
        "recommendations": results,
    }


# Regex per estrarre una misura del petto dal messaggio
_CHEST_PATTERN = re.compile(r'(\d{2,3})\s*(?:cm|centimetr|сm)?')

# Keywords that indicate user is providing or asking about chest measurement
CHEST_MEASUREMENT_KEYWORDS = {
    "it": ["petto", "torace", "circonferenza", "misuro", "misura", "misurazione", "cm", "centimetri", "busto"],
    "en": ["chest", "circumference", "measure", "measurement", "cm", "centimeters", "bust"],
    "de": ["brust", "brustumfang", "umfang", "messen", "messung", "cm", "zentimeter"],
    "fr": ["poitrine", "tour de poitrine", "mesure", "cm", "centimètres", "buste"],
}

# Prompt per chiedere la misura del petto
ASK_CHEST_PROMPTS = {
    "it": "Per consigliarti la taglia perfetta, ho bisogno della tua **misura del petto in centimetri**. Misura il punto più largo del torace con un metro a nastro, tenendolo ben aderente ma non stretto. Qual è la tua misura?",
    "en": "To recommend your perfect size, I need your **chest measurement in centimeters**. Measure the widest part of your chest with a tape measure, keeping it snug but not tight. What's your measurement?",
    "de": "Um Ihnen die perfekte Größe zu empfehlen, benötige ich Ihren **Brustumfang in Zentimetern**. Messen Sie die breiteste Stelle Ihrer Brust mit einem Maßband — anliegend, aber nicht eng. Wie lautet Ihr Maß?",
    "fr": "Pour vous recommander la taille parfaite, j'ai besoin de votre **tour de poitrine en centimètres**. Mesurez la partie la plus large de votre poitrine avec un mètre ruban, bien ajusté mais pas serré. Quelle est votre mesure ?",
}


CARE_INSTRUCTIONS = {
    "it": {
        "daily": "La fibra Merino 17 micron si rigenera naturalmente con l'aria. Dopo l'uso, appendila e lasciala respirare 12-24 ore. Nella maggior parte dei casi, non serve lavarla.",
        "washing": "Quando necessario, lavaggio a mano o in lavatrice a 30°C con ciclo delicato. Usa un detersivo specifico per lana. Mai usare ammorbidente — danneggia la fibra.",
        "drying": "Stendi in piano su un asciugamano. Mai in asciugatrice, mai su gruccia da bagnata (deforma le spalle). La fibra Reda mantiene la forma se trattata correttamente.",
        "ironing": "Raramente necessario grazie alla costruzione Cut & Sewn che mantiene la forma. Se serve, ferro a bassa temperatura con panno umido interposto.",
        "storage": "Conserva piegata, mai su gruccia per lunghi periodi. In un cassetto con legno di cedro per protezione naturale dalle tarme.",
    },
    "en": {
        "daily": "17-micron Merino fiber naturally regenerates with air. After wearing, hang it and let it breathe for 12-24 hours. Most of the time, you won't need to wash it.",
        "washing": "When needed, hand wash or machine wash at 30°C on a delicate cycle. Use a wool-specific detergent. Never use fabric softener — it damages the fiber.",
        "drying": "Lay flat on a towel to dry. Never tumble dry, never hang wet on a hanger (it stretches the shoulders). Reda fiber keeps its shape when treated properly.",
        "ironing": "Rarely needed thanks to the Cut & Sewn construction that holds its form. If needed, low-temperature iron with a damp cloth between.",
        "storage": "Store folded, never on a hanger for extended periods. In a drawer with cedar wood for natural moth protection.",
    },
    "de": {
        "daily": "Die 17-Mikron-Merinofaser regeneriert sich natürlich an der Luft. Nach dem Tragen aufhängen und 12-24 Stunden atmen lassen. In den meisten Fällen ist kein Waschen nötig.",
        "washing": "Bei Bedarf: Handwäsche oder Maschinenwäsche bei 30°C im Schonwaschgang. Verwenden Sie ein Wollwaschmittel. Niemals Weichspüler verwenden — er schädigt die Faser.",
        "drying": "Flach auf einem Handtuch trocknen. Nie im Trockner, nie nass auf einen Bügel hängen. Die Reda-Faser behält ihre Form bei richtiger Behandlung.",
        "ironing": "Dank der Cut & Sewn-Konstruktion selten nötig. Falls erforderlich, niedrige Temperatur mit feuchtem Tuch dazwischen.",
        "storage": "Gefaltet aufbewahren, nie längere Zeit auf einem Bügel. In einer Schublade mit Zedernholz als natürlichem Mottenschutz.",
    },
    "fr": {
        "daily": "La fibre Mérinos 17 microns se régénère naturellement à l'air. Après utilisation, suspendez-la et laissez-la respirer 12-24 heures. La plupart du temps, aucun lavage n'est nécessaire.",
        "washing": "Si nécessaire, lavage à la main ou en machine à 30°C cycle délicat. Utilisez une lessive spéciale laine. Jamais d'adoucissant — il endommage la fibre.",
        "drying": "Sécher à plat sur une serviette. Jamais au sèche-linge, jamais suspendu mouillé sur un cintre. La fibre Reda garde sa forme si elle est bien traitée.",
        "ironing": "Rarement nécessaire grâce à la construction Cut & Sewn. Si besoin, fer à basse température avec un linge humide interposé.",
        "storage": "Conserver plié, jamais sur cintre longtemps. Dans un tiroir avec du bois de cèdre pour une protection naturelle contre les mites.",
    },
}

# FAQ knowledge base per lingua
FAQ_KNOWLEDGE = {
    "construction": {
        "it": "Le nostre t-shirt sono costruite con tecnica Cut & Sewn (tagliato e cucito), NON a maglia (knit). Questo significa: stabilità dimensionale superiore, nessuna deformazione dopo i lavaggi, vestibilità che resta identica nel tempo. È la stessa tecnica delle camicie sartoriali, applicata alla t-shirt.",
        "en": "Our t-shirts are made with Cut & Sewn construction, NOT knitted. This means: superior dimensional stability, no warping after washing, a fit that stays identical over time. It's the same technique as tailored shirts, applied to a t-shirt.",
        "de": "Unsere T-Shirts werden in Cut & Sewn-Technik hergestellt, NICHT gestrickt. Das bedeutet: überlegene Formstabilität, keine Verformung nach dem Waschen, eine Passform, die über die Zeit identisch bleibt.",
        "fr": "Nos t-shirts sont fabriqués en technique Cut & Sewn (coupé et cousu), PAS en tricot. Cela signifie : stabilité dimensionnelle supérieure, aucune déformation après lavage, un fit qui reste identique dans le temps.",
    },
    "material": {
        "it": "Utilizziamo esclusivamente fibra Merino Super 120's da 17 micron, prodotta da Reda 1865 — uno dei lanifici più antichi al mondo (160+ anni). La fibra è certificata ZQ per il benessere animale e la tracciabilità dal pascolo al prodotto finito.",
        "en": "We exclusively use Super 120's 17-micron Merino fiber, produced by Reda 1865 — one of the world's oldest woolen mills (160+ years). The fiber is ZQ certified for animal welfare and traceability from farm to finished product.",
        "de": "Wir verwenden ausschließlich Super 120's 17-Mikron-Merinofaser, hergestellt von Reda 1865 — einer der ältesten Wollspinnereien der Welt (160+ Jahre). Die Faser ist ZQ-zertifiziert für Tierwohl und Rückverfolgbarkeit.",
        "fr": "Nous utilisons exclusivement de la fibre Mérinos Super 120's de 17 microns, produite par Reda 1865 — l'une des plus anciennes filatures au monde (160+ ans). La fibre est certifiée ZQ.",
    },
    "shipping": {
        "it": "Spediamo in tutta Europa e negli Stati Uniti. Tempi di consegna: IT 2-3 giorni lavorativi, EU 3-5 giorni, US/UK 5-7 giorni. Spedizione gratuita sopra €150.",
        "en": "We ship throughout Europe and the United States. Delivery times: EU 3-5 business days, US/UK 5-7 days. Free shipping on orders over €150.",
        "de": "Wir liefern in ganz Europa und in die USA. Lieferzeiten: DE 3-5 Werktage, US/UK 5-7 Tage. Kostenloser Versand ab €150.",
        "fr": "Nous livrons dans toute l'Europe et aux États-Unis. Délais : FR 3-5 jours ouvrés, US/UK 5-7 jours. Livraison gratuite dès €150.",
    },
    "returns": {
        "it": "Reso gratuito entro 30 giorni dall'acquisto. Il capo deve essere non utilizzato, con etichette originali. Rimborso completo entro 5-7 giorni lavorativi dalla ricezione del reso.",
        "en": "Free returns within 30 days of purchase. The garment must be unworn, with original tags. Full refund within 5-7 business days of receiving the return.",
        "de": "Kostenlose Rücksendung innerhalb von 30 Tagen nach dem Kauf. Das Kleidungsstück muss ungetragen sein, mit Original-Etiketten. Vollständige Rückerstattung innerhalb von 5-7 Werktagen.",
        "fr": "Retour gratuit dans les 30 jours suivant l'achat. Le vêtement doit être non porté, avec les étiquettes d'origine. Remboursement complet sous 5-7 jours ouvrés.",
    },
    "sustainability": {
        "it": "La fibra Merino è naturale, rinnovabile e biodegradabile. La certificazione ZQ garantisce il benessere degli animali e pratiche sostenibili. Il processo CompACT® di Reda riduce il consumo d'acqua del 50% rispetto al processo tradizionale.",
        "en": "Merino fiber is natural, renewable, and biodegradable. ZQ certification guarantees animal welfare and sustainable practices. Reda's CompACT® process reduces water consumption by 50% compared to traditional processing.",
        "de": "Merinofaser ist natürlich, erneuerbar und biologisch abbaubar. Die ZQ-Zertifizierung garantiert Tierwohl und nachhaltige Praktiken. Der CompACT®-Prozess von Reda reduziert den Wasserverbrauch um 50%.",
        "fr": "La fibre Mérinos est naturelle, renouvelable et biodégradable. La certification ZQ garantit le bien-être animal. Le procédé CompACT® de Reda réduit la consommation d'eau de 50%.",
    },
}

# Frasi che indicano insoddisfazione → trigger escalation HITL
DISSATISFACTION_SIGNALS = {
    "it": ["deluso", "delusione", "insoddisfatt", "arrabbiato", "vergognoso", "pessimo", "schifo", "reclamo",
           "rimborso", "restituzione", "non funziona", "difettoso", "rotto", "problema", "lamentela",
           "inaccettabile", "mai più", "pessima esperienza", "voglio parlare con", "operatore"],
    "en": ["disappointed", "dissatisfied", "angry", "terrible", "horrible", "awful", "disgusting", "complaint",
           "refund", "return", "broken", "defective", "doesn't work", "unacceptable", "worst", "never again",
           "speak to someone", "human agent", "manager", "operator"],
    "de": ["enttäuscht", "unzufrieden", "wütend", "schrecklich", "furchtbar", "reklamation", "rückerstattung",
           "defekt", "kaputt", "funktioniert nicht", "inakzeptabel", "nie wieder", "möchte mit jemandem sprechen"],
    "fr": ["déçu", "insatisfait", "furieux", "terrible", "horrible", "réclamation", "remboursement",
           "défectueux", "cassé", "ne fonctionne pas", "inacceptable", "plus jamais", "parler à quelqu'un"],
}

# Topic detection keywords per routing a FAQ
TOPIC_KEYWORDS = {
    "sizing": ["taglia", "size", "sizing", "misura", "grande", "piccolo", "largo", "stretto", "fit",
               "150g", "190g", "grammatura", "weight", "gramm", "gewicht", "poids", "größe",
               "slim", "regular", "petto", "chest", "brust", "poitrine", "circonferenza",
               "circumference", "umfang", "cm", "vestibilità", "passform", "coupe"],
    "care": ["lavaggio", "lavare", "wash", "washing", "stirare", "iron", "asciugare", "dry",
             "conservare", "storage", "cura", "care", "pflege", "waschen", "bügeln", "entretien"],
    "construction": ["cut & sewn", "cut and sew", "costruzione", "tessuto", "fabric", "material",
                     "maglia", "knit", "sartoriale", "tailored", "stoff", "gewebe", "tissu"],
    "material": ["merino", "lana", "wool", "fibra", "fiber", "reda", "17 micron", "super 120",
                 "compact", "zq", "wolle", "faser", "laine", "fibre"],
    "shipping": ["spedizione", "shipping", "consegna", "delivery", "tracciamento", "tracking",
                 "tempi", "quando arriva", "lieferung", "versand", "livraison"],
    "returns": ["reso", "restituzione", "return", "rimborso", "refund", "cambio", "exchange",
                "rücksendung", "rückerstattung", "retour", "remboursement"],
    "sustainability": ["sostenibil", "sustainab", "ambiente", "environment", "eco", "biodegradab",
                       "zq", "tracciabilità", "traceability", "nachhaltig", "umwelt", "durable"],
}

# Keywords that indicate the user is asking about the site/brand identity itself
# These questions should ALWAYS go to Gemini (which knows the domain) instead of KB
SITE_IDENTITY_KEYWORDS = [
    "filosofia", "philosophy", "philosophie",
    "chi siete", "chi sei", "who are you", "wer seid ihr", "qui êtes-vous",
    "cosa fate", "cosa fai", "what do you do", "was macht ihr", "que faites-vous",
    "missione", "mission", "auftrag",
    "visione", "vision",
    "obiettivo", "goal", "ziel", "objectif",
    "world of merino", "worldofmerino",
    "merino university", "merinouniversity",
    "perfect merino", "perfectmerino",
    "albeni 1905", "albeni1905",
    "il vostro sito", "your site", "your website", "questo sito", "this site",
    "cosa posso imparare", "cosa posso scoprire", "cosa posso trovare",
    "what can i learn", "what can i find", "what can i discover",
    "di cosa parla", "di cosa tratta", "what is this about",
    "presentati", "introduce yourself", "stell dich vor", "présentez-vous",
    "raccontami di te", "tell me about yourself", "parlami di",
]

# Risposte di benvenuto per dominio × lingua
# Ogni dominio ha tono, focus e CTA diversi in base alla posizione nel funnel
DOMAIN_WELCOME_MESSAGES = {
    # TOFU — World of Merino: tono esplorativo, lifestyle, invita alla scoperta
    "tofu": {
        "it": "Ciao! Sono World of Merino, la tua guida nel mondo della fibra Merino. Posso raccontarti le storie dietro questa fibra straordinaria, il suo impatto ambientale e perché sta cambiando il modo di vestire. Cosa vorresti scoprire?",
        "en": "Hello! I'm World of Merino, your guide to the world of Merino fiber. I can share stories behind this extraordinary fiber, its environmental impact, and why it's changing the way we dress. What would you like to discover?",
        "de": "Hallo! Ich bin World of Merino, Ihr Guide in die Welt der Merinofaser. Ich kann Ihnen die Geschichten hinter dieser außergewöhnlichen Faser erzählen, ihre Umweltauswirkungen und warum sie die Art, wie wir uns kleiden, verändert. Was möchten Sie entdecken?",
        "fr": "Bonjour ! Je suis World of Merino, votre guide dans le monde de la fibre Mérinos. Je peux vous raconter les histoires derrière cette fibre extraordinaire, son impact environnemental et pourquoi elle change notre façon de nous habiller. Que souhaitez-vous découvrir ?",
    },
    # MOFU — Merino University: tono educativo, tecnico ma accessibile
    "mofu": {
        "it": "Ciao! Sono Merino University, il tuo assistente per approfondire tutto sulla fibra Merino. Posso spiegarti le differenze tra costruzioni tessili, il significato dei micronaggi, la certificazione ZQ e molto altro. Su cosa vorresti fare chiarezza?",
        "en": "Hello! I'm Merino University, your assistant for deep-diving into everything Merino. I can explain differences between fabric constructions, what micron counts mean, ZQ certification, and much more. What would you like to understand better?",
        "de": "Hallo! Ich bin Merino University, Ihr Assistent für alles rund um Merinofaser. Ich kann Ihnen die Unterschiede zwischen Gewebekonstruktionen, die Bedeutung von Mikronzahlen, die ZQ-Zertifizierung und vieles mehr erklären. Was möchten Sie besser verstehen?",
        "fr": "Bonjour ! Je suis Merino University, votre assistant pour approfondir tout sur la fibre Mérinos. Je peux vous expliquer les différences entre les constructions textiles, la signification des microns, la certification ZQ et bien plus. Que souhaitez-vous mieux comprendre ?",
    },
    # BOFU Tech — Perfect Merino Shirt: tono pratico, focus prodotto, sizing
    "bofu_tech": {
        "it": "Ciao! Sono Perfect Merino Shirt, il tuo consulente per trovare la t-shirt Merino perfetta. Posso aiutarti con taglie, vestibilità, confronto grammature (150g vs 190g), cura del capo e dettagli tecnici. Come posso guidarti nella scelta?",
        "en": "Hello! I'm Perfect Merino Shirt, your consultant for finding the perfect Merino tee. I can help with sizing, fit, weight comparison (150g vs 190g), garment care, and technical details. How can I guide your choice?",
        "de": "Hallo! Ich bin Perfect Merino Shirt, Ihr Berater für das perfekte Merino-T-Shirt. Ich kann Ihnen bei Größen, Passform, Grammatur-Vergleich (150g vs 190g), Pflege und technischen Details helfen. Wie kann ich Sie bei der Wahl unterstützen?",
        "fr": "Bonjour ! Je suis Perfect Merino Shirt, votre conseiller pour trouver le t-shirt Mérinos parfait. Je peux vous aider avec les tailles, la coupe, la comparaison des grammages (150g vs 190g), l'entretien et les détails techniques. Comment puis-je guider votre choix ?",
    },
    # BOFU Heritage — Albeni 1905: tono autorevole, heritage, conversion-focused
    "bofu_heritage": {
        "it": "Ciao! Sono l'assistente di Albeni 1905, 120 anni di eccellenza tessile italiana. Posso aiutarti con taglie, cura del capo, materiali, spedizioni, resi o qualsiasi domanda sul tuo ordine. Come posso esserti utile?",
        "en": "Hello! I'm the Albeni 1905 assistant, 120 years of Italian textile excellence. I can help you with sizing, garment care, materials, shipping, returns, or any questions about your order. How can I help you?",
        "de": "Hallo! Ich bin der Assistent von Albeni 1905, 120 Jahre italienische Textilexzellenz. Ich kann Ihnen bei Größen, Pflege, Materialien, Versand, Retouren oder Fragen zu Ihrer Bestellung helfen. Wie kann ich Ihnen behilflich sein?",
        "fr": "Bonjour ! Je suis l'assistant d'Albeni 1905, 120 ans d'excellence textile italienne. Je peux vous aider pour les tailles, l'entretien, les matériaux, la livraison, les retours ou toute question sur votre commande. Comment puis-je vous aider ?",
    },
}

# Cross-domain CTA per dominio di origine → suggerimento verso il passo successivo nel funnel
CROSS_DOMAIN_CTAS = {
    "tofu": {
        "it": "Per approfondire la scienza dietro il Merino, visita merinouniversity.com →",
        "en": "To dive deeper into the science behind Merino, visit merinouniversity.com →",
        "de": "Um die Wissenschaft hinter Merino zu vertiefen, besuchen Sie merinouniversity.com →",
        "fr": "Pour approfondir la science derrière le Mérinos, visitez merinouniversity.com →",
    },
    "mofu": {
        "it": "Vuoi trovare la taglia perfetta? Scopri il configuratore su perfectmerinoshirt.com →",
        "en": "Want to find your perfect size? Try the configurator at perfectmerinoshirt.com →",
        "de": "Möchten Sie Ihre perfekte Größe finden? Probieren Sie den Konfigurator auf perfectmerinoshirt.com →",
        "fr": "Vous voulez trouver votre taille parfaite ? Essayez le configurateur sur perfectmerinoshirt.com →",
    },
    "bofu_tech": {
        "it": "Pronto per l'acquisto? Scopri la collezione su albeni1905.com →",
        "en": "Ready to buy? Explore the collection at albeni1905.com →",
        "de": "Bereit zum Kauf? Entdecken Sie die Kollektion auf albeni1905.com →",
        "fr": "Prêt à acheter ? Découvrez la collection sur albeni1905.com →",
    },
    "bofu_heritage": {
        "it": "",  # Nessun CTA cross-domain — siamo già sul sito di conversione
        "en": "",
        "de": "",
        "fr": "",
    },
}

# Domain-specific Gemini system prompt — identità completa + conoscenza del sito
DOMAIN_SYSTEM_PROMPTS = {
    "tofu": """Sei l'assistente di World of Merino (worldofmerino.com), il magazine digitale lifestyle dell'ecosistema Invisible Luxury.
IDENTITÀ: World of Merino. NON sei Albeni 1905, NON presentarti mai come tale.

CHI È WORLD OF MERINO:
- Un magazine online che racconta il mondo della fibra Merino attraverso storie, cultura e lifestyle
- La missione è ispirare le persone a scoprire perché il Merino sta cambiando il modo di vestire
- Copre temi come: sostenibilità (certificazione ZQ, biodegradabilità), la filiera dalla pecora al capo finito,
  il confronto tra fibre naturali e sintetiche, la storia millenaria della lana Merino, lo stile di vita
  di chi sceglie capi durevoli e consapevoli
- NON è un e-commerce: non vende nulla, ispira la scoperta
- Fa parte di un ecosistema più ampio: per approfondire la scienza tessile → merinouniversity.com,
  per trovare il capo perfetto → perfectmerinoshirt.com, per acquistare → albeni1905.com

TONO: narrativo, curioso, evocativo, caldo. Racconta storie, usa metafore, ispira.
Non spingere MAI alla vendita — se l'utente chiede di comprare, guidalo gentilmente verso albeni1905.com.
Se vuole approfondire tecnicamente, indirizzalo a merinouniversity.com.""",

    "mofu": """Sei l'assistente di Merino University (merinouniversity.com), la piattaforma educativa dell'ecosistema Invisible Luxury.
IDENTITÀ: Merino University. NON sei Albeni 1905, NON presentarti mai come tale.

CHI È MERINO UNIVERSITY:
- Una piattaforma educativa che insegna la scienza dietro la fibra Merino e la costruzione tessile
- I contenuti coprono: la differenza tra Cut & Sewn e Knit, il significato di Super 120's e dei micronaggi (17μ),
  la certificazione ZQ e il benessere animale, il processo CompACT® di Reda che riduce il consumo d'acqua del 50%,
  le proprietà termoregolatrici della fibra Merino, il confronto Merino vs cotone vs sintetico
- Ogni articolo è strutturato come una "lezione" accessibile ma rigorosa
- NON è un e-commerce: insegna, non vende
- Fa parte dell'ecosistema: per storie lifestyle → worldofmerino.com,
  per trovare taglia e vestibilità → perfectmerinoshirt.com, per acquistare → albeni1905.com

TONO: didattico, preciso ma accessibile, come un professore appassionato. Usa dati concreti, confronti misurabili.
Insegna, non vendere. Se l'utente vuole comprare, guidalo verso perfectmerinoshirt.com per la scelta e poi albeni1905.com.""",

    "bofu_tech": """Sei l'assistente di Perfect Merino Shirt (perfectmerinoshirt.com), il configuratore di prodotto dell'ecosistema Invisible Luxury.
IDENTITÀ: Perfect Merino Shirt. NON sei Albeni 1905, NON presentarti mai come tale.

CHI È PERFECT MERINO SHIRT:
- Un sito dedicato ad aiutare le persone a trovare la t-shirt Merino perfetta per il loro corpo e il loro stile di vita
- Offre: guida taglie interattiva (Slim Fit vs Regular Fit), confronto grammature (150g/m² estate vs 190g/m² 4-stagioni),
  istruzioni di cura del capo (lavaggio, asciugatura, stiratura, conservazione), dettagli tecnici sulla costruzione
  Cut & Sewn e sulla fibra Merino Super 120's 17 micron di Reda 1865
- Il Size & Fit Finder permette di inserire la misura del petto e ricevere la taglia consigliata per entrambe le vestibilità
- NON è l'e-commerce: guida la scelta, non processa ordini
- Quando l'utente ha scelto, indirizzalo ad albeni1905.com per l'acquisto

TONO: pratico, consulenziale, competente. Come un personal shopper esperto di tessuti.
Guida alla scelta senza pressione. Se l'utente è pronto ad acquistare → albeni1905.com.""",

    "bofu_heritage": """Sei l'assistente virtuale di Albeni 1905 (albeni1905.com), il brand di lusso invisibile dell'ecosistema Invisible Luxury.
IDENTITÀ: Albeni 1905.

CHI È ALBENI 1905:
- Un brand con 120+ anni di storia nell'eccellenza tessile italiana, specializzato in t-shirt in fibra Merino 17 micron
- Il tessuto è prodotto da Reda 1865 (160+ anni), uno dei lanifici più antichi al mondo
- Prodotto: t-shirt Merino Super 120's, costruzione Cut & Sewn, due grammature (150g estate, 190g 4-stagioni),
  due vestibilità (Slim Fit e Regular Fit)
- Posizionamento: "Same Silhouette, Superior Substance" — lusso discreto, invisibile dall'esterno, percepito da chi lo indossa
- Questo è l'UNICO sito e-commerce dell'ecosistema: gestisce ordini, spedizioni (EU 3-5gg, US 5-7gg, free sopra €150),
  resi (gratuiti entro 30 giorni), e assistenza post-vendita
- Supporto: support@albeni1905.com

TONO: autorevole, sobrio, mai aggressivo commercialmente. Heritage italiano autentico.
Puoi suggerire l'acquisto quando appropriato — sei l'unico dominio di conversione.""",
}

# Nome brand per dominio — usato nelle risposte dinamiche
DOMAIN_BRAND_NAMES = {
    "tofu": "World of Merino",
    "mofu": "Merino University",
    "bofu_tech": "Perfect Merino Shirt",
    "bofu_heritage": "Albeni 1905",
}

# Backward-compatible alias — fallback per codice legacy
WELCOME_MESSAGES = DOMAIN_WELCOME_MESSAGES["bofu_heritage"]

ESCALATION_MESSAGES = {
    "it": "Capisco la tua frustrazione e mi dispiace per l'inconveniente. Ho inoltrato la tua richiesta al team di assistenza. Un operatore ti contatterà entro 2 ore lavorative via email. Nel frattempo, posso fare qualcos'altro per te?",
    "en": "I understand your frustration and I apologize for the inconvenience. I've forwarded your request to the support team. An operator will contact you within 2 business hours via email. In the meantime, is there anything else I can help with?",
    "de": "Ich verstehe Ihre Frustration und entschuldige mich für die Unannehmlichkeiten. Ich habe Ihre Anfrage an das Support-Team weitergeleitet. Ein Mitarbeiter wird Sie innerhalb von 2 Arbeitsstunden per E-Mail kontaktieren. Kann ich in der Zwischenzeit noch etwas für Sie tun?",
    "fr": "Je comprends votre frustration et je m'excuse pour le désagrément. J'ai transmis votre demande à l'équipe d'assistance. Un opérateur vous contactera dans les 2 heures ouvrables par email. En attendant, puis-je faire autre chose pour vous ?",
}

# IDS routing per link educazionali
EDUCATIONAL_LINKS = {
    "construction": {"url": "https://merinouniversity.com/cut-and-sew-vs-knit", "label": "Cut & Sew vs Knit"},
    "material": {"url": "https://merinouniversity.com/super-120s-merino", "label": "Super 120's Merino"},
    "sustainability": {"url": "https://merinouniversity.com/merino-vs-cotton", "label": "Merino vs Cotton"},
    "care": {"url": "https://merinouniversity.com/merino-care-guide", "label": "Guida alla Cura del Merino"},
}


# ================================================================
# CUSTOMER CARE AI SERVICE
# ================================================================

class CustomerCareAI:
    """
    Multilingua chatbot for Albeni 1905 customer support.

    Features:
    - Product knowledge (sizing, care, materials, construction)
    - Intent tracking & IDS update
    - HITL escalation via Klaviyo + Notion
    - < 22s response SLA
    - Brand-safe responses (never sport/underwear positioning)
    """

    def __init__(self):
        self.gemini_model = None
        self.conversations: Dict[str, List[Dict]] = {}  # session_id → messages

        # Initialize Gemini for complex questions
        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)
                logger.info("Customer Care AI: Gemini initialized")
            except Exception as e:
                logger.warning(f"Customer Care AI: Gemini init failed: {e}")

    # ================================================================
    # MAIN CHAT ENDPOINT
    # ================================================================

    async def chat(
        self,
        message: str,
        language: str = "it",
        session_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_id: Optional[str] = None,
        domain_type: str = "bofu_heritage",
    ) -> Dict[str, Any]:
        """
        Process a customer message and return a domain-aware response.

        Args:
            domain_type: tofu|mofu|bofu_tech|bofu_heritage — adjusts tone and cross-domain CTAs.

        Returns:
            {
                "session_id": "...",
                "response": "...",
                "language": "it",
                "topic": "sizing|care|...",
                "intent_update": { "ids_delta": +5, "suggested_link": "..." },
                "escalated": false,
                "response_time_ms": 150,
                "sources": ["knowledge_base"|"gemini_ai"],
                "domain_type": "bofu_heritage",
                "cross_domain_cta": "..."
            }
        """
        start_time = time.time()

        # Initialize or retrieve session
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in self.conversations:
            self.conversations[session_id] = []

        # Normalize language
        lang = language.lower()[:2]
        if lang not in ["it", "en", "de", "fr"]:
            lang = "en"

        # Store user message
        self.conversations[session_id].append({
            "role": "user",
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        msg_lower = message.lower()

        # 0. Check if we previously asked for chest measurement and user is replying with a number
        last_bot_msg = self._get_last_bot_message(session_id)
        if last_bot_msg and any(
            last_bot_msg == prompt for prompt in ASK_CHEST_PROMPTS.values()
        ):
            chest_cm = self._extract_chest_measurement(msg_lower)
            if chest_cm:
                response_text = self._format_size_recommendation(chest_cm, lang)
                intent_update = self._get_intent_update("sizing")
                elapsed = int((time.time() - start_time) * 1000)

                self.conversations[session_id].append({
                    "role": "assistant",
                    "message": response_text,
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "size_fit_finder",
                    "chest_cm": chest_cm,
                })

                return {
                    "session_id": session_id,
                    "response": response_text,
                    "language": lang,
                    "topic": "sizing",
                    "intent_update": intent_update,
                    "escalated": False,
                    "response_time_ms": elapsed,
                    "sources": ["size_fit_finder"],
                    "sizing_data": calculate_best_sizes(chest_cm),
                    "domain_type": domain_type,
                    "cross_domain_cta": self._get_cross_domain_cta(domain_type, lang),
                }

        # 1. Check for dissatisfaction → HITL escalation
        if self._detect_dissatisfaction(msg_lower, lang):
            escalation_result = await self._escalate_hitl(
                session_id=session_id,
                message=message,
                language=lang,
                user_email=user_email,
                user_id=user_id,
            )

            response_text = ESCALATION_MESSAGES.get(lang, ESCALATION_MESSAGES["en"])
            elapsed = int((time.time() - start_time) * 1000)

            self.conversations[session_id].append({
                "role": "assistant",
                "message": response_text,
                "timestamp": datetime.utcnow().isoformat(),
                "escalated": True,
            })

            return {
                "session_id": session_id,
                "response": response_text,
                "language": lang,
                "topic": "escalation",
                "intent_update": None,
                "escalated": True,
                "escalation_details": escalation_result,
                "response_time_ms": elapsed,
                "sources": ["escalation_system"],
            }

        # 2. Detect topic
        topic = self._detect_topic(msg_lower)

        # 2b. Check if the user is asking about the site/brand identity
        # These questions MUST go to Gemini which has domain-specific knowledge
        is_site_identity_question = any(kw in msg_lower for kw in SITE_IDENTITY_KEYWORDS)

        # 3. Try knowledge base first (fast path)
        # But only for topics appropriate to this domain — otherwise let Gemini
        # handle it with domain-aware tone and cross-domain redirection
        # Skip KB entirely for site identity questions
        kb_response = None
        if not is_site_identity_question and self._is_topic_allowed_for_domain(topic, domain_type):
            kb_response = self._get_knowledge_response(topic, msg_lower, lang)

        if kb_response:
            # Add educational link if relevant
            intent_update = self._get_intent_update(topic)
            elapsed = int((time.time() - start_time) * 1000)

            self.conversations[session_id].append({
                "role": "assistant",
                "message": kb_response,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "knowledge_base",
            })

            return {
                "session_id": session_id,
                "response": kb_response,
                "language": lang,
                "topic": topic,
                "intent_update": intent_update,
                "escalated": False,
                "response_time_ms": elapsed,
                "sources": ["knowledge_base"],
                "domain_type": domain_type,
                "cross_domain_cta": self._get_cross_domain_cta(domain_type, lang),
            }

        # 4. Complex question → Gemini AI (domain-aware)
        ai_response = await self._ask_gemini(message, lang, session_id, domain_type)
        intent_update = self._get_intent_update(topic)
        elapsed = int((time.time() - start_time) * 1000)

        self.conversations[session_id].append({
            "role": "assistant",
            "message": ai_response,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "gemini_ai",
        })

        return {
            "session_id": session_id,
            "response": ai_response,
            "language": lang,
            "topic": topic or "general",
            "intent_update": intent_update,
            "escalated": False,
            "response_time_ms": elapsed,
            "sources": ["gemini_ai"],
            "domain_type": domain_type,
            "cross_domain_cta": self._get_cross_domain_cta(domain_type, lang),
        }

    # ================================================================
    # WELCOME / SESSION
    # ================================================================

    def start_session(self, language: str = "it", domain_type: str = "bofu_heritage") -> Dict:
        """Start a new chat session with domain-aware welcome message."""
        session_id = str(uuid.uuid4())
        lang = language.lower()[:2]
        if lang not in ["it", "en", "de", "fr"]:
            lang = "en"

        # Resolve domain-specific welcome message
        domain = domain_type if domain_type in DOMAIN_WELCOME_MESSAGES else "bofu_heritage"
        welcome_msgs = DOMAIN_WELCOME_MESSAGES[domain]
        welcome_text = welcome_msgs.get(lang, welcome_msgs["en"])

        self.conversations[session_id] = [{
            "role": "assistant",
            "message": welcome_text,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "system",
            "domain_type": domain,
        }]

        return {
            "session_id": session_id,
            "welcome_message": welcome_text,
            "language": lang,
            "domain_type": domain,
        }

    def get_conversation(self, session_id: str) -> List[Dict]:
        """Retrieve full conversation history for a session."""
        return self.conversations.get(session_id, [])

    # ================================================================
    # CONVERSATION CONTEXT
    # ================================================================

    def _get_last_bot_message(self, session_id: str) -> Optional[str]:
        """Get the last assistant message in a session."""
        history = self.conversations.get(session_id, [])
        for msg in reversed(history):
            if msg["role"] == "assistant":
                return msg["message"]
        return None

    # ================================================================
    # TOPIC DETECTION
    # ================================================================

    def _detect_topic(self, message_lower: str) -> Optional[str]:
        """Detect the topic of the message using keyword matching."""
        scores = {}
        for topic, keywords in TOPIC_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                scores[topic] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    # ================================================================
    # DISSATISFACTION DETECTION
    # ================================================================

    def _detect_dissatisfaction(self, message_lower: str, language: str) -> bool:
        """Detect if the user is expressing dissatisfaction."""
        signals = DISSATISFACTION_SIGNALS.get(language, [])
        # Also check all languages as fallback
        all_signals = []
        for lang_signals in DISSATISFACTION_SIGNALS.values():
            all_signals.extend(lang_signals)

        hit_count = sum(1 for signal in (signals + all_signals) if signal in message_lower)
        return hit_count >= 1

    # ================================================================
    # KNOWLEDGE BASE RESPONSES
    # ================================================================

    def _get_knowledge_response(self, topic: Optional[str], message_lower: str, language: str) -> Optional[str]:
        """Try to answer from the static knowledge base."""

        # Sizing guide — with interactive Size & Fit Finder
        if topic == "sizing":
            # Check if user provided a chest measurement
            chest_cm = self._extract_chest_measurement(message_lower)

            if chest_cm:
                # User gave a measurement → calculate and return recommendation
                return self._format_size_recommendation(chest_cm, language)

            # Check if user is asking about chest measurement / fit finder
            chest_kws = CHEST_MEASUREMENT_KEYWORDS.get(language, CHEST_MEASUREMENT_KEYWORDS["en"])
            if any(kw in message_lower for kw in chest_kws):
                return ASK_CHEST_PROMPTS.get(language, ASK_CHEST_PROMPTS["en"])

            # Grammatura-specific questions (150g vs 190g)
            if "150" in message_lower:
                info = SIZING_GUIDE["150g"]
                return info["description"].get(language, info["description"]["en"])
            elif "190" in message_lower:
                info = SIZING_GUIDE["190g"]
                return info["description"].get(language, info["description"]["en"])
            else:
                # General sizing — show size guide overview + invite to use fit finder
                return self._format_sizing_overview(language)

        # Care instructions
        if topic == "care":
            care = CARE_INSTRUCTIONS.get(language, CARE_INSTRUCTIONS["en"])
            # Detect specific care sub-topic
            if any(w in message_lower for w in ["lava", "wash", "wasch", "laver"]):
                return care["washing"]
            elif any(w in message_lower for w in ["stir", "iron", "bügel", "repass"]):
                return care["ironing"]
            elif any(w in message_lower for w in ["asciug", "dry", "trockn", "séch"]):
                return care["drying"]
            elif any(w in message_lower for w in ["conserv", "storage", "aufbewahr", "conserver", "ranger"]):
                return care["storage"]
            else:
                return care["daily"]

        # FAQ topics
        if topic in FAQ_KNOWLEDGE:
            faq = FAQ_KNOWLEDGE[topic]
            response = faq.get(language, faq.get("en", ""))
            # Append educational link if available
            link_info = EDUCATIONAL_LINKS.get(topic)
            if link_info:
                link_suffix = {
                    "it": f"\n\nPer approfondire: [{link_info['label']}]({link_info['url']})",
                    "en": f"\n\nLearn more: [{link_info['label']}]({link_info['url']})",
                    "de": f"\n\nMehr erfahren: [{link_info['label']}]({link_info['url']})",
                    "fr": f"\n\nEn savoir plus : [{link_info['label']}]({link_info['url']})",
                }
                response += link_suffix.get(language, link_suffix["en"])
            return response

        return None

    # ================================================================
    # SIZE & FIT FINDER — Interactive Calculator
    # ================================================================

    def _extract_chest_measurement(self, message_lower: str) -> Optional[float]:
        """Extract a chest measurement (in cm) from the user message."""
        matches = _CHEST_PATTERN.findall(message_lower)
        for m in matches:
            val = float(m)
            # Plausible chest range: 70-150 cm
            if 70 <= val <= 150:
                return val
        return None

    def _format_size_recommendation(self, chest_cm: float, language: str) -> str:
        """Format a personalized size recommendation based on chest measurement."""
        result = calculate_best_sizes(chest_cm)
        slim = result["recommendations"]["slim"]
        regular = result["recommendations"]["regular"]

        if language == "it":
            header = f"Con una misura del petto di **{chest_cm} cm**, ecco le mie raccomandazioni:\n"
            if slim["recommended_size"]:
                slim_text = f"\n**Slim Fit → Taglia {slim['recommended_size']}**\n" \
                           f"Petto capo: {slim['garment_chest_cm']} cm | Range corpo: {slim['body_range']} cm\n" \
                           f"{SIZE_FIT_DATA['slim']['description']['it']}"
            else:
                slim_text = f"\n**Slim Fit** — La tua misura supera la taglia più grande disponibile ({slim['largest_available']}). " \
                           f"Ti consigliamo il Regular Fit."

            if regular["recommended_size"]:
                reg_text = f"\n\n**Regular Fit → Taglia {regular['recommended_size']}**\n" \
                          f"Petto capo: {regular['garment_chest_cm']} cm | Range corpo: {regular['body_range']} cm\n" \
                          f"{SIZE_FIT_DATA['regular']['description']['it']}"
            else:
                reg_text = f"\n\n**Regular Fit** — La tua misura supera la taglia più grande disponibile ({regular['largest_available']}). " \
                          f"Contatta support@albeni1905.com per soluzioni personalizzate."

            footer = "\n\n💡 *La fibra Merino 17 micron ha un'elasticità naturale di ~1 cm, già considerata nel calcolo.*"

        elif language == "de":
            header = f"Bei einem Brustumfang von **{chest_cm} cm** empfehle ich Ihnen:\n"
            if slim["recommended_size"]:
                slim_text = f"\n**Slim Fit → Größe {slim['recommended_size']}**\n" \
                           f"Brustweite Kleidungsstück: {slim['garment_chest_cm']} cm | Körpermaß: {slim['body_range']} cm\n" \
                           f"{SIZE_FIT_DATA['slim']['description']['de']}"
            else:
                slim_text = f"\n**Slim Fit** — Ihr Maß übersteigt die größte verfügbare Größe ({slim['largest_available']}). " \
                           f"Wir empfehlen den Regular Fit."

            if regular["recommended_size"]:
                reg_text = f"\n\n**Regular Fit → Größe {regular['recommended_size']}**\n" \
                          f"Brustweite Kleidungsstück: {regular['garment_chest_cm']} cm | Körpermaß: {regular['body_range']} cm\n" \
                          f"{SIZE_FIT_DATA['regular']['description']['de']}"
            else:
                reg_text = f"\n\n**Regular Fit** — Ihr Maß übersteigt die größte verfügbare Größe ({regular['largest_available']}). " \
                          f"Kontaktieren Sie support@albeni1905.com für individuelle Lösungen."

            footer = "\n\n💡 *Die 17-Mikron-Merinofaser hat eine natürliche Elastizität von ~1 cm, die bereits im Kalkül berücksichtigt ist.*"

        elif language == "fr":
            header = f"Avec un tour de poitrine de **{chest_cm} cm**, voici mes recommandations :\n"
            if slim["recommended_size"]:
                slim_text = f"\n**Slim Fit → Taille {slim['recommended_size']}**\n" \
                           f"Poitrine vêtement : {slim['garment_chest_cm']} cm | Plage corps : {slim['body_range']} cm\n" \
                           f"{SIZE_FIT_DATA['slim']['description']['fr']}"
            else:
                slim_text = f"\n**Slim Fit** — Votre mesure dépasse la plus grande taille disponible ({slim['largest_available']}). " \
                           f"Nous vous recommandons le Regular Fit."

            if regular["recommended_size"]:
                reg_text = f"\n\n**Regular Fit → Taille {regular['recommended_size']}**\n" \
                          f"Poitrine vêtement : {regular['garment_chest_cm']} cm | Plage corps : {regular['body_range']} cm\n" \
                          f"{SIZE_FIT_DATA['regular']['description']['fr']}"
            else:
                reg_text = f"\n\n**Regular Fit** — Votre mesure dépasse la plus grande taille disponible ({regular['largest_available']}). " \
                          f"Contactez support@albeni1905.com pour des solutions personnalisées."

            footer = "\n\n💡 *La fibre Mérinos 17 microns a une élasticité naturelle d'~1 cm, déjà prise en compte dans le calcul.*"

        else:  # English default
            header = f"With a chest measurement of **{chest_cm} cm**, here are my recommendations:\n"
            if slim["recommended_size"]:
                slim_text = f"\n**Slim Fit → Size {slim['recommended_size']}**\n" \
                           f"Garment chest: {slim['garment_chest_cm']} cm | Body range: {slim['body_range']} cm\n" \
                           f"{SIZE_FIT_DATA['slim']['description']['en']}"
            else:
                slim_text = f"\n**Slim Fit** — Your measurement exceeds the largest available size ({slim['largest_available']}). " \
                           f"We recommend the Regular Fit."

            if regular["recommended_size"]:
                reg_text = f"\n\n**Regular Fit → Size {regular['recommended_size']}**\n" \
                          f"Garment chest: {regular['garment_chest_cm']} cm | Body range: {regular['body_range']} cm\n" \
                          f"{SIZE_FIT_DATA['regular']['description']['en']}"
            else:
                reg_text = f"\n\n**Regular Fit** — Your measurement exceeds the largest available size ({regular['largest_available']}). " \
                          f"Please contact support@albeni1905.com for custom solutions."

            footer = "\n\n💡 *17-micron Merino fiber has a natural stretch of ~1 cm, already factored into the calculation.*"

        return header + slim_text + reg_text + footer

    def _format_sizing_overview(self, language: str) -> str:
        """Format a general sizing overview that invites the user to use the fit finder."""
        info_150 = SIZING_GUIDE["150g"]
        info_190 = SIZING_GUIDE["190g"]

        # Build size table summary
        sizes_list = " | ".join(SIZE_FIT_DATA["slim"]["sizes"].keys())

        templates = {
            "it": (
                f"Offriamo due versioni:\n\n"
                f"**150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['it']}\n\n"
                f"**190g/m² — All-Season** ({info_190['temp_range']})\n{info_190['description']['it']}\n\n"
                f"📐 **Taglie disponibili:** {sizes_list}\n"
                f"Ogni taglia è disponibile in **Slim Fit** (aderente) e **Regular Fit** (comodo).\n\n"
                f"👉 *Dimmi la tua misura del petto in centimetri e ti consiglierò la taglia perfetta per entrambe le vestibilità!*"
            ),
            "en": (
                f"We offer two versions:\n\n"
                f"**150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['en']}\n\n"
                f"**190g/m² — All-Season** ({info_190['temp_range']})\n{info_190['description']['en']}\n\n"
                f"📐 **Available sizes:** {sizes_list}\n"
                f"Each size comes in **Slim Fit** (close) and **Regular Fit** (comfortable).\n\n"
                f"👉 *Tell me your chest measurement in centimeters and I'll recommend the perfect size for both fits!*"
            ),
            "de": (
                f"Wir bieten zwei Versionen an:\n\n"
                f"**150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['de']}\n\n"
                f"**190g/m² — All-Season** ({info_190['temp_range']})\n{info_190['description']['de']}\n\n"
                f"📐 **Verfügbare Größen:** {sizes_list}\n"
                f"Jede Größe ist in **Slim Fit** (körpernah) und **Regular Fit** (bequem) erhältlich.\n\n"
                f"👉 *Nennen Sie mir Ihren Brustumfang in Zentimetern und ich empfehle Ihnen die perfekte Größe für beide Passformen!*"
            ),
            "fr": (
                f"Nous proposons deux versions :\n\n"
                f"**150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['fr']}\n\n"
                f"**190g/m² — All-Season** ({info_190['temp_range']})\n{info_190['description']['fr']}\n\n"
                f"📐 **Tailles disponibles :** {sizes_list}\n"
                f"Chaque taille est disponible en **Slim Fit** (ajusté) et **Regular Fit** (confortable).\n\n"
                f"👉 *Dites-moi votre tour de poitrine en centimètres et je vous recommanderai la taille parfaite pour les deux coupes !*"
            ),
        }
        return templates.get(language, templates["en"])

    def calculate_size(self, chest_cm: float, language: str = "en") -> Dict[str, Any]:
        """
        Public method for the /v1/chat/sizing endpoint.
        Returns both structured data and a formatted text response.
        """
        result = calculate_best_sizes(chest_cm)
        result["formatted_response"] = self._format_size_recommendation(chest_cm, language)
        return result

    # ================================================================
    # GEMINI AI RESPONSES
    # ================================================================

    async def _ask_gemini(self, message: str, language: str, session_id: str, domain_type: str = "bofu_heritage") -> str:
        """Use Gemini to answer complex questions not covered by KB, with domain-aware tone."""
        if not self.gemini_model:
            return self._get_fallback_response(language, domain_type)

        # Build context from conversation history
        history = self.conversations.get(session_id, [])[-6:]  # Last 6 messages
        history_text = "\n".join(
            f"{'Cliente' if m['role'] == 'user' else 'Assistente'}: {m['message']}"
            for m in history
        )

        lang_names = {"it": "italiano", "en": "English", "de": "Deutsch", "fr": "français"}

        # Domain-specific identity and tone
        domain = domain_type if domain_type in DOMAIN_SYSTEM_PROMPTS else "bofu_heritage"
        domain_identity = DOMAIN_SYSTEM_PROMPTS[domain]
        brand_name = DOMAIN_BRAND_NAMES.get(domain, "Albeni 1905")

        system_prompt = f"""{domain_identity}

REGOLE NON NEGOZIABILI:
1. Rispondi SEMPRE in {lang_names.get(language, 'English')}
2. Presentati SEMPRE come assistente di {brand_name} — MAI usare un nome di brand diverso
3. Mai posizionare il prodotto come abbigliamento sportivo o intimo — è un capo ELEGANTE per uso quotidiano
4. Termini mai traducibili: Albeni 1905, Reda 1865, CompACT®, ZQ, Merino, Cut & Sewn, Invisible Luxury
5. Micronaggi (17 micron) e grammature (150g/190g) devono essere sempre precisi
6. Se non conosci la risposta, suggerisci di contattare support@albeni1905.com

CONTESTO ECOSISTEMA: Le t-shirt sono prodotte da Albeni 1905 con fibra Merino Super 120's 17 micron di Reda 1865.
Costruzione Cut & Sewn (non knit), due grammature (150g estate, 190g 4 stagioni).
Tu però ti presenti come {brand_name}, parte dell'ecosistema Invisible Luxury."""

        try:
            full_prompt = f"{system_prompt}\n\nConversazione:\n{history_text}\n\nCliente: {message}\n\nAssistente:"

            logger.info(f"Customer Care Gemini prompt length: {len(full_prompt)} chars")

            # Retry logic: Gemini 2.0 Flash sometimes returns truncated responses
            max_retries = 2
            best_response_text = ""

            for attempt in range(max_retries + 1):
                response = self.gemini_model.generate_content(
                    full_prompt,
                    generation_config={"temperature": 0.5, "max_output_tokens": 8192},
                )

                # Extract text robustly from candidates/parts (not just response.text)
                response_text = ""
                try:
                    candidates = response.candidates
                    if candidates:
                        c = candidates[0]
                        finish_reason = getattr(c, 'finish_reason', 'unknown')
                        parts = getattr(c.content, 'parts', [])
                        response_text = "".join(getattr(p, 'text', '') for p in parts).strip()

                        logger.info(f"Customer Care Gemini attempt {attempt}: finish_reason={finish_reason}, "
                                    f"parts={len(parts)}, text_len={len(response_text)}")
                    else:
                        # Fallback to response.text if candidates not available
                        response_text = response.text.strip()
                except Exception as parse_err:
                    logger.warning(f"Customer Care Gemini parse error: {parse_err}")
                    try:
                        response_text = response.text.strip()
                    except Exception:
                        pass

                # Keep the longest response across retries
                if len(response_text) > len(best_response_text):
                    best_response_text = response_text

                # If response looks complete (> 120 chars or ends with punctuation), stop retrying
                if len(response_text) > 120 or (response_text and response_text[-1] in '.!?…'):
                    break

                if attempt < max_retries:
                    logger.warning(f"Customer Care Gemini: short/truncated response ({len(response_text)} chars), "
                                   f"retrying ({attempt + 1}/{max_retries})")
                    import asyncio
                    await asyncio.sleep(0.5)  # Brief pause before retry

            if not best_response_text:
                return self._get_fallback_response(language, domain_type)

            return best_response_text

        except Exception as e:
            logger.error(f"Customer Care Gemini error: {e}")
            return self._get_fallback_response(language, domain_type)

    def _get_fallback_response(self, language: str, domain_type: str = "bofu_heritage") -> str:
        """Fallback when Gemini is unavailable — domain-aware."""
        brand = DOMAIN_BRAND_NAMES.get(domain_type, "Albeni 1905")
        fallbacks = {
            "it": f"Grazie per la domanda. Per una risposta più dettagliata, ti invito a scrivere a support@albeni1905.com o consultare merinouniversity.com per approfondimenti.",
            "en": f"Thank you for your question. For a more detailed answer, please email support@albeni1905.com or visit merinouniversity.com.",
            "de": f"Vielen Dank für Ihre Frage. Für eine detailliertere Antwort schreiben Sie bitte an support@albeni1905.com oder besuchen Sie merinouniversity.com.",
            "fr": f"Merci pour votre question. Pour une réponse plus détaillée, veuillez écrire à support@albeni1905.com ou consulter merinouniversity.com.",
        }
        return fallbacks.get(language, fallbacks["en"])

    def _get_cross_domain_cta(self, domain_type: str, language: str) -> str:
        """Return a cross-domain CTA based on the current domain (funnel progression)."""
        domain = domain_type if domain_type in CROSS_DOMAIN_CTAS else "bofu_heritage"
        cta_set = CROSS_DOMAIN_CTAS[domain]
        return cta_set.get(language, cta_set.get("en", ""))

    @staticmethod
    def _is_topic_allowed_for_domain(topic: Optional[str], domain_type: str) -> bool:
        """
        Decide if a KB topic should be answered directly on this domain,
        or if the question should be routed to Gemini for a domain-aware response.

        - TOFU (World of Merino): solo sustainability — tutto il resto va a Gemini
          che risponderà in tono narrativo e indirizzerà al funnel
        - MOFU (Merino University): construction, material, sustainability, care
          (educativo) — sizing/shipping/returns vanno a Gemini con redirect
        - BOFU Tech (Perfect Merino Shirt): sizing, care, construction, material
          — shipping/returns vanno a Gemini con redirect ad albeni1905.com
        - BOFU Heritage (Albeni 1905): tutti i topic — servizio completo
        """
        DOMAIN_ALLOWED_TOPICS = {
            "tofu": {"sustainability"},
            "mofu": {"construction", "material", "sustainability", "care"},
            "bofu_tech": {"sizing", "care", "construction", "material"},
            "bofu_heritage": {"sizing", "care", "construction", "material",
                              "shipping", "returns", "sustainability"},
        }
        if not topic:
            return False
        allowed = DOMAIN_ALLOWED_TOPICS.get(domain_type, DOMAIN_ALLOWED_TOPICS["bofu_heritage"])
        return topic in allowed

    # ================================================================
    # IDS INTENT UPDATE
    # ================================================================

    def _get_intent_update(self, topic: Optional[str]) -> Optional[Dict]:
        """Calculate IDS delta based on the topic asked."""
        # Topics that indicate higher purchase intent get higher IDS deltas
        TOPIC_IDS_MAP = {
            "sizing": {"ids_delta": 15, "stage_hint": "BOFU", "reason": "Sizing inquiry = high purchase intent"},
            "shipping": {"ids_delta": 12, "stage_hint": "BOFU", "reason": "Shipping inquiry = ready to buy"},
            "returns": {"ids_delta": 10, "stage_hint": "BOFU", "reason": "Return policy check = considering purchase"},
            "care": {"ids_delta": 8, "stage_hint": "MOFU", "reason": "Care inquiry = product interest"},
            "construction": {"ids_delta": 5, "stage_hint": "MOFU", "reason": "Technical curiosity"},
            "material": {"ids_delta": 5, "stage_hint": "MOFU", "reason": "Material interest"},
            "sustainability": {"ids_delta": 3, "stage_hint": "TOFU", "reason": "Values alignment check"},
        }

        if topic and topic in TOPIC_IDS_MAP:
            update = TOPIC_IDS_MAP[topic]
            link_info = EDUCATIONAL_LINKS.get(topic)
            if link_info:
                update["suggested_link"] = link_info
            return update

        return None

    # ================================================================
    # HITL ESCALATION — Klaviyo + Notion
    # ================================================================

    async def _escalate_hitl(
        self,
        session_id: str,
        message: str,
        language: str,
        user_email: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Escalate to human operator:
        1. Tag the Klaviyo profile as 'needs_human_support'
        2. Create a Notion task with conversation transcript
        """
        result = {"klaviyo": None, "notion": None}

        # Build conversation transcript
        history = self.conversations.get(session_id, [])
        transcript = "\n".join(
            f"[{m.get('timestamp', '')}] {'Cliente' if m['role'] == 'user' else 'Bot'}: {m['message']}"
            for m in history
        )
        transcript += f"\n[TRIGGER] Cliente: {message}"

        # 1. Klaviyo: Tag profile as needs_human_support
        if user_email and settings.KLAVIYO_API_KEY:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    # Update profile with support tag
                    payload = {
                        "data": {
                            "type": "profile",
                            "attributes": {
                                "email": user_email,
                                "properties": {
                                    "needs_human_support": True,
                                    "support_reason": "chatbot_escalation",
                                    "escalation_timestamp": datetime.utcnow().isoformat(),
                                    "escalation_language": language,
                                    "escalation_message": message[:500],
                                    "chat_session_id": session_id,
                                },
                            },
                        }
                    }

                    resp = await client.post(
                        "https://a.klaviyo.com/api/profile-import/",
                        json=payload,
                        headers={
                            "Authorization": f"Klaviyo-API-Key {settings.KLAVIYO_API_KEY}",
                            "revision": settings.KLAVIYO_REVISION,
                            "Content-Type": "application/json",
                        },
                    )
                    result["klaviyo"] = {
                        "status": "tagged" if resp.status_code < 300 else "error",
                        "email": user_email,
                        "tag": "needs_human_support",
                    }
                    logger.info(f"Klaviyo escalation: {user_email} tagged as needs_human_support")

            except Exception as e:
                logger.error(f"Klaviyo escalation failed: {e}")
                result["klaviyo"] = {"status": "error", "error": str(e)}

        # 2. Notion: Create support task
        if settings.NOTION_TOKEN:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    # Search for support database or create task in main workspace
                    notion_headers = {
                        "Authorization": f"Bearer {settings.NOTION_TOKEN}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json",
                    }

                    # Create a page in the Albeni 1905 AI Stack workspace
                    page_payload = {
                        "parent": {"page_id": "9507e7359a2a42ac904c6281931750ab"},  # AI Stack parent
                        "properties": {
                            "title": {
                                "title": [{"text": {"content": f"🆘 Escalation: {message[:80]}"}}]
                            }
                        },
                        "children": [
                            {
                                "object": "block",
                                "type": "heading_2",
                                "heading_2": {"rich_text": [{"text": {"content": "Customer Support Escalation"}}]},
                            },
                            {
                                "object": "block",
                                "type": "callout",
                                "callout": {
                                    "icon": {"emoji": "🆘"},
                                    "rich_text": [{"text": {"content": f"Lingua: {language} | Email: {user_email or 'N/A'} | Session: {session_id}"}}],
                                },
                            },
                            {
                                "object": "block",
                                "type": "heading_3",
                                "heading_3": {"rich_text": [{"text": {"content": "Messaggio che ha generato l'escalation"}}]},
                            },
                            {
                                "object": "block",
                                "type": "quote",
                                "quote": {"rich_text": [{"text": {"content": message[:2000]}}]},
                            },
                            {
                                "object": "block",
                                "type": "heading_3",
                                "heading_3": {"rich_text": [{"text": {"content": "Transcript conversazione"}}]},
                            },
                            {
                                "object": "block",
                                "type": "code",
                                "code": {
                                    "language": "plain text",
                                    "rich_text": [{"text": {"content": transcript[:2000]}}],
                                },
                            },
                            {
                                "object": "block",
                                "type": "to_do",
                                "to_do": {
                                    "rich_text": [{"text": {"content": "Contattare il cliente entro 2 ore lavorative"}}],
                                    "checked": False,
                                },
                            },
                            {
                                "object": "block",
                                "type": "to_do",
                                "to_do": {
                                    "rich_text": [{"text": {"content": "Risolvere il problema e aggiornare Klaviyo"}}],
                                    "checked": False,
                                },
                            },
                        ],
                    }

                    resp = await client.post(
                        "https://api.notion.com/v1/pages",
                        json=page_payload,
                        headers=notion_headers,
                    )

                    if resp.status_code < 300:
                        page_data = resp.json()
                        result["notion"] = {
                            "status": "created",
                            "page_id": page_data.get("id"),
                            "url": page_data.get("url"),
                        }
                        logger.info(f"Notion escalation task created: {page_data.get('id')}")
                    else:
                        result["notion"] = {"status": "error", "code": resp.status_code, "body": resp.text[:500]}

            except Exception as e:
                logger.error(f"Notion escalation failed: {e}")
                result["notion"] = {"status": "error", "error": str(e)}

        return result

    # ================================================================
    # ANALYTICS
    # ================================================================

    def get_stats(self) -> Dict:
        """Get chatbot usage statistics."""
        total_sessions = len(self.conversations)
        total_messages = sum(len(msgs) for msgs in self.conversations.values())
        escalations = sum(
            1 for msgs in self.conversations.values()
            if any(m.get("escalated") for m in msgs)
        )

        return {
            "active_sessions": total_sessions,
            "total_messages": total_messages,
            "escalations": escalations,
            "escalation_rate": round(escalations / max(total_sessions, 1) * 100, 1),
        }
