"""
Customer Care AI — Multilingua Chatbot
micron-è (Best Before S.r.l.) — Invisible Luxury Ecosystem
Guardrail copy 2026-07-10: mai Albeni / Reda / ZQ / nomi fornitori; filiera = RWS;
tecnologia di raffrescamento = solo "tecnologia micron-è"; claim numerici con disclaimer.

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
        "name": "micron-è Cool (150g/m²)",
        "season": "Primavera/Estate",
        "temp_range": "18°C–35°C",
        "description": {
            "it": "La linea per il caldo pieno. Jersey 150g/m² in merino Super 120's da 17,6 micron con tecnologia micron-è dual-action: fresca al tatto già prima di sudare, poi raffrescamento evaporativo continuo, fino a −3°C sulla temperatura del tessuto (dato di laboratorio, validazione in corso). Oltre il 50% di componente biobased certificata USDA.",
            "en": "The line for full heat. 150g/m² jersey in Super 120's 17.6-micron Merino with dual-action micron-è technology: cool to the touch before you even sweat, then continuous evaporative cooling, up to −3°C on fabric temperature (laboratory data, validation in progress). Over 50% USDA-certified biobased content.",
            "de": "Die Linie für heiße Tage. Jersey 150g/m² aus Super 120's 17,6-Mikron-Merino mit Dual-Action-micron-è-Technologie: kühl bei Berührung noch vor dem Schwitzen, dann kontinuierliche Verdunstungskühlung, bis zu −3°C Gewebetemperatur (Labordaten, Validierung läuft). Über 50% USDA-zertifizierter biobasierter Anteil.",
            "fr": "La ligne pour les grandes chaleurs. Jersey 150g/m² en Mérinos Super 120's de 17,6 microns avec technologie micron-è double action : frais au toucher avant même de transpirer, puis rafraîchissement évaporatif continu, jusqu'à −3°C sur la température du tissu (données de laboratoire, validation en cours). Plus de 50% de contenu biosourcé certifié USDA.",
        },
    },
    "195g": {
        "name": "micron-è Adaptive (195g/m²)",
        "season": "Tutto l'anno / 4 Stagioni",
        "temp_range": "5°C–28°C",
        "description": {
            "it": "La linea 4 stagioni. Jersey 195g/m² nella stessa fibra merino Super 120's da 17,6 micron, con tecnologia micron-è adattiva: il raffrescamento si attiva quando sei accaldato e sudato (fino a −2,5°C, dato di laboratorio in validazione) e si spegne da solo quando non serve — mai freddo addosso. Il naturale tepore, quando serve, lo dà la lana.",
            "en": "The all-season line. 195g/m² jersey in the same Super 120's 17.6-micron Merino fiber, with adaptive micron-è technology: cooling activates when you're hot and sweaty (up to −2.5°C, laboratory data under validation) and switches itself off when not needed — never a chill. The natural warmth, when needed, comes from the wool.",
            "de": "Die Ganzjahreslinie. Jersey 195g/m² aus derselben Super 120's 17,6-Mikron-Merinofaser, mit adaptiver micron-è-Technologie: Die Kühlung aktiviert sich, wenn Ihnen heiß ist (bis zu −2,5°C, Labordaten in Validierung), und schaltet sich von selbst ab — nie ein Kältegefühl. Die natürliche Wärme kommt, wenn nötig, von der Wolle.",
            "fr": "La ligne 4 saisons. Jersey 195g/m² dans la même fibre Mérinos Super 120's de 17,6 microns, avec technologie micron-è adaptative : le rafraîchissement s'active quand vous avez chaud (jusqu'à −2,5°C, données de laboratoire en validation) et s'arrête de lui-même — jamais de sensation de froid. La chaleur naturelle, quand il le faut, vient de la laine.",
        },
    },
}

# ================================================================
# SIZE & FIT FINDER — Interactive Sizing Calculator
# Gamma ufficiale micron-è a 9 varianti (grading a finestre torace da 8 cm),
# identica al motore sizing.ts dello store micron-e.com. L'assegnazione è per
# finestra (lookup), NON per formula di agio minimo.
# ================================================================

# Size data: per taglia, finestra torace utente [from, to) e misure capo finito.
SIZE_FIT_DATA = {
    "slim": {
        "label": "Slim Fit",
        "description": {
            "it": "Vestibilità asciutta. Silhouette definita che segue il corpo. Ideale sotto giacca o blazer.",
            "en": "Close fit. Defined silhouette that follows the body. Perfect under a jacket or blazer.",
            "de": "Körpernahe Passform. Definierte Silhouette, die dem Körper folgt. Ideal unter Sakko oder Blazer.",
            "fr": "Coupe ajustée. Silhouette définie qui suit le corps. Idéal sous une veste ou un blazer.",
        },
        "sizes": {
            "S":   {"from": 88,  "to": 96,  "chest_cm": 100, "body_range": "88-96"},
            "M":   {"from": 96,  "to": 104, "chest_cm": 108, "body_range": "96-104"},
            "L":   {"from": 104, "to": 112, "chest_cm": 116, "body_range": "104-112"},
            "XL":  {"from": 112, "to": 120, "chest_cm": 124, "body_range": "112-120"},
        },
    },
    "regular": {
        "label": "Regular Fit",
        "description": {
            "it": "Vestibilità comoda. Più spazio nel busto per libertà di movimento. Perfetta per l'uso quotidiano.",
            "en": "Comfortable fit. More room in the chest for freedom of movement. Perfect for everyday wear.",
            "de": "Bequeme Passform. Mehr Platz im Brustbereich für Bewegungsfreiheit. Perfekt für den Alltag.",
            "fr": "Coupe confortable. Plus d'espace au buste pour la liberté de mouvement. Parfaite au quotidien.",
        },
        "sizes": {
            "M":   {"from": 96,  "to": 104, "chest_cm": 114, "body_range": "96-104"},
            "L":   {"from": 104, "to": 112, "chest_cm": 120, "body_range": "104-112"},
            "XL":  {"from": 112, "to": 120, "chest_cm": 126, "body_range": "112-120"},
            "XXL": {"from": 120, "to": 128, "chest_cm": 134, "body_range": "120-128"},
            "3XL": {"from": 128, "to": 136, "chest_cm": 142, "body_range": "128-136"},
        },
    },
}


def calculate_best_sizes(user_chest: float) -> Dict[str, Any]:
    """
    Assegna la taglia per finestra torace (limite inferiore incluso, superiore
    escluso) per entrambe le vestibilità — stessa logica di sizing.ts.
    Sotto la finestra minima di un fit si consiglia la taglia più piccola
    (nota "below_range"); oltre la massima si segnala "exceeds_range".
    """
    results = {}

    for fit_key, fit_data in SIZE_FIT_DATA.items():
        sizes = fit_data["sizes"]
        best_size = None
        for size_label, size_info in sizes.items():
            if size_info["from"] <= user_chest < size_info["to"]:
                best_size = size_label
                break

        first_label = next(iter(sizes))
        last_label = list(sizes.keys())[-1]

        if best_size is None and user_chest < sizes[first_label]["from"]:
            info = sizes[first_label]
            results[fit_key] = {
                "recommended_size": first_label,
                "fit_label": fit_data["label"],
                "garment_chest_cm": info["chest_cm"],
                "body_range": info["body_range"],
                "ease_cm": round(info["chest_cm"] - user_chest, 1),
                "note": "below_range",
            }
        elif best_size is None:
            results[fit_key] = {
                "recommended_size": None,
                "fit_label": fit_data["label"],
                "note": "exceeds_range",
                "largest_available": last_label,
                "largest_chest_cm": sizes[last_label]["chest_cm"],
            }
        else:
            info = sizes[best_size]
            results[fit_key] = {
                "recommended_size": best_size,
                "fit_label": fit_data["label"],
                "garment_chest_cm": info["chest_cm"],
                "body_range": info["body_range"],
                "ease_cm": round(info["chest_cm"] - user_chest, 1),
            }

    return {
        "user_chest_cm": user_chest,
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
        "daily": "La fibra merino 17,6 micron si rigenera naturalmente con l'aria. Dopo l'uso, appendila e lasciala respirare 12-24 ore. Nella maggior parte dei casi, non serve lavarla.",
        "washing": "Quando necessario, lavaggio a mano o in lavatrice a 30°C con ciclo delicato. Usa un detersivo specifico per lana. Mai usare ammorbidente — danneggia la fibra.",
        "drying": "Stendi in piano su un asciugamano. Mai in asciugatrice, mai su gruccia da bagnata (deforma le spalle). La fibra merino mantiene la forma se trattata correttamente.",
        "ironing": "Raramente necessario grazie alla costruzione Cut & Sewn che mantiene la forma. Se serve, ferro a bassa temperatura con panno umido interposto.",
        "storage": "Conserva piegata, mai su gruccia per lunghi periodi. In un cassetto con legno di cedro per protezione naturale dalle tarme.",
    },
    "en": {
        "daily": "17.6-micron Merino fiber naturally regenerates with air. After wearing, hang it and let it breathe for 12-24 hours. Most of the time, you won't need to wash it.",
        "washing": "When needed, hand wash or machine wash at 30°C on a delicate cycle. Use a wool-specific detergent. Never use fabric softener — it damages the fiber.",
        "drying": "Lay flat on a towel to dry. Never tumble dry, never hang wet on a hanger (it stretches the shoulders). Merino fiber keeps its shape when treated properly.",
        "ironing": "Rarely needed thanks to the Cut & Sewn construction that holds its form. If needed, low-temperature iron with a damp cloth between.",
        "storage": "Store folded, never on a hanger for extended periods. In a drawer with cedar wood for natural moth protection.",
    },
    "de": {
        "daily": "Die 17,6-Mikron-Merinofaser regeneriert sich natürlich an der Luft. Nach dem Tragen aufhängen und 12-24 Stunden atmen lassen. In den meisten Fällen ist kein Waschen nötig.",
        "washing": "Bei Bedarf: Handwäsche oder Maschinenwäsche bei 30°C im Schonwaschgang. Verwenden Sie ein Wollwaschmittel. Niemals Weichspüler verwenden — er schädigt die Faser.",
        "drying": "Flach auf einem Handtuch trocknen. Nie im Trockner, nie nass auf einen Bügel hängen. Die Merinofaser behält ihre Form bei richtiger Behandlung.",
        "ironing": "Dank der Cut & Sewn-Konstruktion selten nötig. Falls erforderlich, niedrige Temperatur mit feuchtem Tuch dazwischen.",
        "storage": "Gefaltet aufbewahren, nie längere Zeit auf einem Bügel. In einer Schublade mit Zedernholz als natürlichem Mottenschutz.",
    },
    "fr": {
        "daily": "La fibre Mérinos 17,6 microns se régénère naturellement à l'air. Après utilisation, suspendez-la et laissez-la respirer 12-24 heures. La plupart du temps, aucun lavage n'est nécessaire.",
        "washing": "Si nécessaire, lavage à la main ou en machine à 30°C cycle délicat. Utilisez une lessive spéciale laine. Jamais d'adoucissant — il endommage la fibre.",
        "drying": "Sécher à plat sur une serviette. Jamais au sèche-linge, jamais suspendu mouillé sur un cintre. La fibre mérinos garde sa forme si elle est bien traitée.",
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
        "it": "Utilizziamo esclusivamente merino Super 120's da 17,6 micron di finezza media: un jersey di fascia sartoriale prodotto nel distretto laniero di Biella da un lanificio italiano partner della nostra filiera. La lana proviene da allevamenti merino neozelandesi ed è certificata RWS (Responsible Wool Standard): benessere animale e tracciabilità lungo l'intera catena del valore, dalla fattoria al tessuto. Nessuna fibra sintetica, nessun elastan.",
        "en": "We exclusively use Super 120's Merino with an average fineness of 17.6 microns: a tailoring-grade jersey produced in the Biella wool district by an Italian mill that is part of our supply chain. The wool comes from New Zealand Merino farms and is RWS certified (Responsible Wool Standard): animal welfare and traceability along the entire value chain, from farm to fabric. No synthetic fibers, no elastane.",
        "de": "Wir verwenden ausschließlich Super 120's Merino mit einer mittleren Feinheit von 17,6 Mikron: ein Jersey auf Schneiderniveau, hergestellt im Wolldistrikt von Biella von einer italienischen Partnerweberei unserer Lieferkette. Die Wolle stammt aus neuseeländischen Merinofarmen und ist RWS-zertifiziert (Responsible Wool Standard): Tierwohl und Rückverfolgbarkeit entlang der gesamten Wertschöpfungskette. Keine Synthetikfasern, kein Elasthan.",
        "fr": "Nous utilisons exclusivement du Mérinos Super 120's d'une finesse moyenne de 17,6 microns : un jersey de niveau tailleur produit dans le district lainier de Biella par une filature italienne partenaire de notre filière. La laine provient d'élevages mérinos néo-zélandais et est certifiée RWS (Responsible Wool Standard) : bien-être animal et traçabilité sur toute la chaîne de valeur. Aucune fibre synthétique, aucun élasthanne.",
    },
    "microne": {
        "it": "micron-è è un marchio italiano indipendente di Best Before S.r.l. e, insieme, la sua tecnologia proprietaria di raffrescamento tessile. **Cos'è**: una t-shirt in merino Super 120's (17,6 micron), costruzione Cut & Sewn, Made in Italy, in due linee — **Adaptive 195 g/m²** e **Cool 150 g/m²** — a 125 €. **A cosa serve**: la tecnologia micron-è gestisce il calore percepito. Sull'Adaptive il raffrescamento si attiva quando sei accaldato e sudato (fino a −2,5°C sulla temperatura del tessuto) e si spegne da solo; sulla Cool è dual-action: fresca al tatto già prima del sudore, poi raffrescamento evaporativo continuo (fino a −3°C), con oltre il 50% di componente biobased certificata USDA. Il fresco lo dà la tecnologia; il naturale tepore, quando serve, lo dà la lana. I dati di raffrescamento sono di laboratorio, con validazione in corso. La capsula di lancio (edizione limitata, 302 pezzi) arriva a settembre 2026 su micron-e.com: la waitlist dà accesso prioritario.",
        "en": "micron-è is an independent Italian brand by Best Before S.r.l. and, at the same time, its proprietary textile cooling technology. **What it is**: a Super 120's Merino t-shirt (17.6 microns), Cut & Sewn construction, Made in Italy, in two lines — **Adaptive 195 g/m²** and **Cool 150 g/m²** — at €125. **What it's for**: micron-è technology manages perceived heat. On the Adaptive, cooling activates when you're hot and sweaty (up to −2.5°C on fabric temperature) and switches itself off; the Cool is dual-action: cool to the touch before you even sweat, then continuous evaporative cooling (up to −3°C), with over 50% USDA-certified biobased content. The coolness comes from the technology; the natural warmth, when needed, comes from the wool. Cooling figures are laboratory data, validation in progress. The launch capsule (limited edition, 302 pieces) arrives in September 2026 on micron-e.com: the waitlist gives priority access.",
        "de": "micron-è ist eine unabhängige italienische Marke von Best Before S.r.l. und zugleich ihre proprietäre textile Kühltechnologie. **Was es ist**: ein T-Shirt aus Super 120's Merino (17,6 Mikron), Cut & Sewn-Konstruktion, Made in Italy, in zwei Linien — **Adaptive 195 g/m²** und **Cool 150 g/m²** — für 125 €. **Wofür es dient**: Die micron-è-Technologie reguliert die gefühlte Wärme. Beim Adaptive aktiviert sich die Kühlung, wenn Ihnen heiß ist (bis zu −2,5°C Gewebetemperatur), und schaltet sich von selbst ab; das Cool ist Dual-Action: kühl bei Berührung noch vor dem Schwitzen, dann kontinuierliche Verdunstungskühlung (bis zu −3°C), mit über 50% USDA-zertifiziertem biobasiertem Anteil. Die Kühle kommt von der Technologie; die natürliche Wärme, wenn nötig, von der Wolle. Die Kühlwerte sind Labordaten, Validierung läuft. Die Launch-Kapsel (limitierte Auflage, 302 Stück) erscheint im September 2026 auf micron-e.com: Die Warteliste gibt bevorzugten Zugang.",
        "fr": "micron-è est une marque italienne indépendante de Best Before S.r.l. et, en même temps, sa technologie propriétaire de rafraîchissement textile. **Ce que c'est** : un t-shirt en Mérinos Super 120's (17,6 microns), construction Cut & Sewn, Made in Italy, en deux lignes — **Adaptive 195 g/m²** et **Cool 150 g/m²** — à 125 €. **À quoi ça sert** : la technologie micron-è gère la chaleur perçue. Sur l'Adaptive, le rafraîchissement s'active quand vous avez chaud (jusqu'à −2,5°C sur la température du tissu) et s'arrête de lui-même ; le Cool est double action : frais au toucher avant même la transpiration, puis rafraîchissement évaporatif continu (jusqu'à −3°C), avec plus de 50% de contenu biosourcé certifié USDA. Le frais vient de la technologie ; la chaleur naturelle, quand il le faut, vient de la laine. Les données de rafraîchissement sont des données de laboratoire, validation en cours. La capsule de lancement (édition limitée, 302 pièces) arrive en septembre 2026 sur micron-e.com : la liste d'attente donne un accès prioritaire.",
    },
    "shipping": {
        "it": "Lo store micron-e.com apre a settembre 2026 con la capsula di lancio: il perimetro definitivo di spedizione (paesi, costi, tempi e corriere) sarà pubblicato all'apertura. I mercati di riferimento sono l'Unione Europea, con Regno Unito e Stati Uniti a listino dedicato (125 € UE / £115 UK). Iscrivendoti alla waitlist su micron-e.com ricevi l'avviso all'apertura.",
        "en": "The micron-e.com store opens in September 2026 with the launch capsule: the definitive shipping scope (countries, costs, times and carrier) will be published at opening. Reference markets are the European Union, with the UK and US on a dedicated price list (€125 EU / £115 UK). Join the waitlist at micron-e.com to be notified at opening.",
        "de": "Der Store micron-e.com öffnet im September 2026 mit der Launch-Kapsel: Der endgültige Versandumfang (Länder, Kosten, Zeiten, Versanddienstleister) wird zur Eröffnung veröffentlicht. Referenzmärkte sind die EU, mit UK und USA zu eigener Preisliste (125 € EU / £115 UK). Tragen Sie sich auf micron-e.com in die Warteliste ein.",
        "fr": "La boutique micron-e.com ouvre en septembre 2026 avec la capsule de lancement : le périmètre définitif de livraison (pays, coûts, délais, transporteur) sera publié à l'ouverture. Les marchés de référence sont l'Union européenne, avec le Royaume-Uni et les États-Unis à tarif dédié (125 € UE / £115 UK). Inscrivez-vous à la liste d'attente sur micron-e.com.",
    },
    "returns": {
        "it": "La politica resi completa sarà pubblicata all'apertura dello store micron-e.com (settembre 2026). Sono garantiti fin d'ora i diritti UE: almeno 14 giorni di recesso e 2 anni di garanzia legale di conformità per i difetti. I dettagli operativi (procedura, cambio taglia) arrivano col lancio.",
        "en": "The full returns policy will be published when the micron-e.com store opens (September 2026). EU rights are guaranteed from day one: at least 14 days of withdrawal and a 2-year legal conformity guarantee for defects. Operational details (procedure, size exchange) arrive at launch.",
        "de": "Die vollständige Rückgaberichtlinie wird zur Eröffnung des Stores micron-e.com (September 2026) veröffentlicht. EU-Rechte sind von Anfang an garantiert: mindestens 14 Tage Widerruf und 2 Jahre gesetzliche Gewährleistung bei Mängeln. Die operativen Details folgen zum Launch.",
        "fr": "La politique de retour complète sera publiée à l'ouverture de la boutique micron-e.com (septembre 2026). Les droits UE sont garantis dès maintenant : au moins 14 jours de rétractation et 2 ans de garantie légale de conformité. Les détails opérationnels arrivent au lancement.",
    },
    "sustainability": {
        "it": "La fibra merino è naturale, rinnovabile e biodegradabile. La nostra lana arriva da una filiera integrata e certificata RWS (Responsible Wool Standard), dall'allevamento neozelandese al tessuto, con pratiche orientate all'agricoltura rigenerativa. Il lanificio partner lavora nel distretto biellese con energie rinnovabili, sistemi di filtrazione dell'acqua e riduzione continua dei consumi.",
        "en": "Merino fiber is natural, renewable, and biodegradable. Our wool comes from an integrated, RWS-certified supply chain (Responsible Wool Standard), from New Zealand farms to fabric, with practices oriented to regenerative agriculture. The partner mill works in the Biella district with renewable energy, water filtration systems and continuous consumption reduction.",
        "de": "Merinofaser ist natürlich, erneuerbar und biologisch abbaubar. Unsere Wolle stammt aus einer integrierten, RWS-zertifizierten Lieferkette (Responsible Wool Standard), von neuseeländischen Farmen bis zum Gewebe, mit Praktiken regenerativer Landwirtschaft. Die Partnerweberei arbeitet im Distrikt Biella mit erneuerbaren Energien und Wasserfiltrationssystemen.",
        "fr": "La fibre Mérinos est naturelle, renouvelable et biodégradable. Notre laine provient d'une filière intégrée et certifiée RWS (Responsible Wool Standard), des élevages néo-zélandais au tissu, avec des pratiques orientées vers l'agriculture régénérative. La filature partenaire travaille dans le district de Biella avec des énergies renouvelables et des systèmes de filtration de l'eau.",
    },
    "regulation": {
        "it": (
            "REACH Annex XVII e ESPR 2026 sono due normative UE convergenti nel 2026.\n\n"
            "**31 maggio 2026 — ECHA Reporting microplastiche**: i produttori di tessuti sintetici devono "
            "comunicare all'ECHA stime e dati sulle microplastiche rilasciate. Il poliestere rilascia circa "
            "700.000 microfibre per ogni lavaggio.\n\n"
            "**19 luglio 2026 — ESPR (Ecodesign for Sustainable Products Regulation)**: entra in vigore il "
            "divieto UE di distruzione dell'invenduto tessile. Si stima che nell'UE vengano distrutte tra "
            "264.000 e 594.000 tonnellate di invenduti ogni anno.\n\n"
            "**La lana merino non è soggetta a nessuno dei due obblighi**: è una fibra naturale biodegradabile, "
            "non rilascia microplastiche sintetiche ed è strutturalmente conforme agli obiettivi dell'economia "
            "circolare — prima ancora che diventino obblighi di legge."
        ),
        "en": (
            "REACH Annex XVII and ESPR 2026 are two EU regulations converging in 2026.\n\n"
            "**May 31, 2026 — ECHA Microplastics Reporting**: synthetic textile producers must report microplastics "
            "data to ECHA. Polyester releases ~700,000 microfibers per wash.\n\n"
            "**July 19, 2026 — ESPR (Ecodesign for Sustainable Products Regulation)**: EU ban on destruction of "
            "unsold textile inventory comes into force. The EU estimates 264,000–594,000 tonnes destroyed annually.\n\n"
            "**Merino wool is not subject to either obligation**: it's a natural, biodegradable fiber that releases "
            "no synthetic microplastics — structurally compliant with circular economy goals before they become law."
        ),
        "de": (
            "REACH Anhang XVII und ESPR 2026 sind zwei konvergierende EU-Vorschriften im Jahr 2026.\n\n"
            "**31. Mai 2026 — ECHA Mikroplastik-Meldepflicht**: Hersteller von Synthetiktextilien müssen der ECHA "
            "Daten zu freigesetzten Mikroplastiken melden. Polyester setzt ~700.000 Mikrofasern pro Waschgang frei.\n\n"
            "**19. Juli 2026 — ESPR (Ökodesign-Verordnung)**: EU-Verbot der Vernichtung unverkaufter Textilien tritt "
            "in Kraft. Schätzungsweise 264.000–594.000 Tonnen Unverkauftes werden jährlich in der EU vernichtet.\n\n"
            "**Merinowolle unterliegt keiner der beiden Pflichten**: natürliche, biologisch abbaubare Faser, "
            "setzt keine synthetischen Mikroplastiken frei — strukturell konform mit Kreislaufwirtschaftszielen."
        ),
        "fr": (
            "REACH Annexe XVII et ESPR 2026 sont deux réglementations UE convergentes en 2026.\n\n"
            "**31 mai 2026 — Déclaration ECHA microplastiques**: les fabricants de textiles synthétiques doivent "
            "déclarer à l'ECHA les données sur les microplastiques libérés. Le polyester libère ~700 000 "
            "microfibres par lavage.\n\n"
            "**19 juillet 2026 — ESPR (Règlement écoconception)**: interdiction UE de destruction des invendus "
            "textiles. L'UE estime que 264 000–594 000 tonnes d'invendus sont détruites chaque année.\n\n"
            "**La laine mérinos n'est soumise à aucune de ces obligations**: fibre naturelle biodégradable, "
            "ne libère pas de microplastiques synthétiques — conforme aux objectifs d'économie circulaire."
        ),
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
               "150g", "195g", "190g", "grammatura", "weight", "gramm", "gewicht", "poids", "größe",
               "slim", "regular", "petto", "chest", "brust", "poitrine", "circonferenza",
               "circumference", "umfang", "cm", "vestibilità", "passform", "coupe"],
    "care": ["lavaggio", "lavare", "wash", "washing", "stirare", "iron", "asciugare", "dry",
             "conservare", "storage", "cura", "care", "pflege", "waschen", "bügeln", "entretien"],
    "construction": ["cut & sewn", "cut and sew", "costruzione", "tessuto", "fabric", "material",
                     "maglia", "knit", "sartoriale", "tailored", "stoff", "gewebe", "tissu"],
    "material": ["merino", "lana", "wool", "fibra", "fiber", "reda", "17 micron", "17,6", "17.6",
                 "super 120", "compact", "zq", "wolle", "faser", "laine", "fibre"],
    "microne": ["micron-e", "micron-è", "micron e", "micron è", "microne", "micronemerino",
                "best before", "adaptive", "cool", "raffrescamento", "raffresca", "cooling",
                "kühlung", "rafraîchissement", "tecnologia micron", "cos'e micron", "cosa e micron",
                "what is micron", "was ist micron", "qu'est-ce que micron", "a cosa serve"],
    "shipping": ["spedizione", "shipping", "consegna", "delivery", "tracciamento", "tracking",
                 "tempi", "quando arriva", "lieferung", "versand", "livraison"],
    "returns": ["reso", "restituzione", "return", "rimborso", "refund", "cambio", "exchange",
                "rücksendung", "rückerstattung", "retour", "remboursement"],
    "sustainability": ["sostenibil", "sustainab", "ambiente", "environment", "eco", "biodegradab",
                       "zq", "tracciabilità", "traceability", "nachhaltig", "umwelt", "durable"],
    "regulation": ["espr", "reach", "normativa ue", "regulation", "compliance", "microplastich",
                   "microplastic", "microfibre", "microfiber", "invendut", "unsold", "echa",
                   "ecodesign", "divieto invenduto", "destruction textile", "vernichtung unverkauft",
                   "annex xvii", "anhang xvii", "annexe xvii", "regolamento tessile", "textile regulation"],
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
    "micron-è", "micron-e", "micron e", "micronemerino", "best before",
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
        "it": "Ciao! Sono Merino University, il tuo assistente per approfondire tutto sulla fibra Merino. Posso spiegarti le differenze tra costruzioni tessili, il significato dei micronaggi, le certificazioni di filiera (RWS) e molto altro. Su cosa vorresti fare chiarezza?",
        "en": "Hello! I'm Merino University, your assistant for deep-diving into everything Merino. I can explain differences between fabric constructions, what micron counts mean, supply-chain certifications (RWS), and much more. What would you like to understand better?",
        "de": "Hallo! Ich bin Merino University, Ihr Assistent für alles rund um Merinofaser. Ich kann Ihnen die Unterschiede zwischen Gewebekonstruktionen, die Bedeutung von Mikronzahlen, die Lieferketten-Zertifizierungen (RWS) und vieles mehr erklären. Was möchten Sie besser verstehen?",
        "fr": "Bonjour ! Je suis Merino University, votre assistant pour approfondir tout sur la fibre Mérinos. Je peux vous expliquer les différences entre les constructions textiles, la signification des microns, les certifications de filière (RWS) et bien plus. Que souhaitez-vous mieux comprendre ?",
    },
    # BOFU Tech — Perfect Merino Shirt: tono pratico, focus prodotto, sizing
    "bofu_tech": {
        "it": "Ciao! Sono Perfect Merino Shirt, il tuo consulente per trovare la t-shirt Merino perfetta. Posso aiutarti con taglie, vestibilità, confronto linee (Cool 150g vs Adaptive 195g), cura del capo e dettagli tecnici. Come posso guidarti nella scelta?",
        "en": "Hello! I'm Perfect Merino Shirt, your consultant for finding the perfect Merino tee. I can help with sizing, fit, line comparison (Cool 150g vs Adaptive 195g), garment care, and technical details. How can I guide your choice?",
        "de": "Hallo! Ich bin Perfect Merino Shirt, Ihr Berater für das perfekte Merino-T-Shirt. Ich kann Ihnen bei Größen, Passform, Linien-Vergleich (Cool 150g vs Adaptive 195g), Pflege und technischen Details helfen. Wie kann ich Sie bei der Wahl unterstützen?",
        "fr": "Bonjour ! Je suis Perfect Merino Shirt, votre conseiller pour trouver le t-shirt Mérinos parfait. Je peux vous aider avec les tailles, la coupe, la comparaison des lignes (Cool 150g vs Adaptive 195g), l'entretien et les détails techniques. Comment puis-je guider votre choix ?",
    },
    # BOFU — micron-è (micron-e.com): tono sobrio, Invisible Luxury, conversion-focused
    "bofu_heritage": {
        "it": "Benvenuto. Sono l'assistente micron-è. Posso aiutarti su prodotto e tecnologia di raffrescamento, taglie e vestibilità, cura del capo, lancio e disponibilità. Come posso esserti utile?",
        "en": "Welcome. I'm the micron-è assistant. I can help with product and cooling technology, sizing and fit, garment care, launch and availability. How can I help you?",
        "de": "Willkommen. Ich bin der micron-è-Assistent. Ich helfe Ihnen bei Produkt und Kühltechnologie, Größen und Passform, Pflege, Launch und Verfügbarkeit. Wie kann ich behilflich sein?",
        "fr": "Bienvenue. Je suis l'assistant micron-è. Je peux vous aider sur le produit et la technologie de rafraîchissement, les tailles, l'entretien, le lancement et la disponibilité. Comment puis-je vous aider ?",
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
        "it": "Pronto per l'acquisto? Scopri micron-è su micron-e.com →",
        "en": "Ready to buy? Discover micron-è at micron-e.com →",
        "de": "Bereit zum Kauf? Entdecken Sie micron-è auf micron-e.com →",
        "fr": "Prêt à acheter ? Découvrez micron-è sur micron-e.com →",
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
IDENTITÀ: World of Merino. NON sei micron-è, NON presentarti mai come tale.

CHI È WORLD OF MERINO:
- Un magazine online che racconta il mondo della fibra Merino attraverso storie, cultura e lifestyle
- La missione è ispirare le persone a scoprire perché il Merino sta cambiando il modo di vestire
- Copre temi come: sostenibilità (benessere animale certificato RWS, biodegradabilità), la filiera dalla pecora al capo finito,
  il confronto tra fibre naturali e sintetiche, la storia millenaria della lana Merino, lo stile di vita
  di chi sceglie capi durevoli e consapevoli
- NON è un e-commerce: non vende nulla, ispira la scoperta
- Fa parte di un ecosistema più ampio: per approfondire la scienza tessile → merinouniversity.com,
  per acquistare la t-shirt micron-è → micron-e.com

CONOSCENZA micron-è (cos'è e a cosa serve) — il prodotto dell'ecosistema:
- micron-è è un marchio italiano indipendente di Best Before S.r.l. e la sua tecnologia proprietaria di raffrescamento tessile
- Prodotto: t-shirt in merino Super 120's (17,6 micron), costruzione Cut & Sewn, Made in Italy, 125 €
- Due linee: Adaptive 195 g/m² (raffrescamento adattivo: si attiva con calore e sudore, fino a −2,5°C, si spegne da solo)
  e Cool 150 g/m² (dual-action: fresca al tatto prima del sudore + raffrescamento evaporativo continuo, fino a −3°C,
  oltre il 50% di componente biobased certificata USDA)
- Regola: il fresco lo dà la tecnologia micron-è; il naturale tepore, quando serve, lo dà la lana
- I dati di raffrescamento sono di laboratorio, validazione in corso: citali sempre con questa precisazione
- Filiera: lana neozelandese certificata RWS, tessuto del distretto biellese (lanificio partner — mai nominarlo)
- Lancio: capsula in edizione limitata di 302 pezzi, settembre 2026, solo online su micron-e.com (waitlist attiva, nessun negozio fisico)

TONO: narrativo, curioso, evocativo, caldo. Racconta storie, usa metafore, ispira.
Non spingere MAI alla vendita — se l'utente chiede di comprare, guidalo gentilmente verso micron-e.com.
Se vuole approfondire tecnicamente, indirizzalo a merinouniversity.com.""",

    "mofu": """Sei l'assistente di Merino University (merinouniversity.com), la piattaforma educativa dell'ecosistema Invisible Luxury.
IDENTITÀ: Merino University. NON sei micron-è, NON presentarti mai come tale.

CHI È MERINO UNIVERSITY:
- Una piattaforma educativa che insegna la scienza dietro la fibra Merino e la costruzione tessile
- I contenuti coprono: la differenza tra Cut & Sewn e Knit, il significato di Super 120's e dei micronaggi (17,6μ),
  la certificazione RWS e il benessere animale, la tracciabilità di filiera dal pascolo al tessuto,
  le proprietà termoregolatrici della fibra Merino, il confronto Merino vs cotone vs sintetico
- Ogni articolo è strutturato come una "lezione" accessibile ma rigorosa
- Pubblica l'**Osservatorio Merino**: analisi normative e trend regolatori del settore tessile (es. REACH Annex XVII, ESPR 2026, divieto invenduti UE, reporting microplastiche ECHA)
- NON è un e-commerce: insegna, non vende
- Fa parte dell'ecosistema: per storie lifestyle → worldofmerino.com, per acquistare la t-shirt micron-è → micron-e.com

CONOSCENZA micron-è (cos'è e a cosa serve) — il prodotto dell'ecosistema:
- micron-è è un marchio italiano indipendente di Best Before S.r.l. e la sua tecnologia proprietaria di raffrescamento tessile
- Prodotto: t-shirt in merino Super 120's (17,6 micron), costruzione Cut & Sewn, Made in Italy, 125 €
- Due linee: Adaptive 195 g/m² (raffrescamento adattivo: si attiva con calore e sudore, fino a −2,5°C, si spegne da solo)
  e Cool 150 g/m² (dual-action: fresca al tatto prima del sudore + raffrescamento evaporativo continuo, fino a −3°C,
  oltre il 50% di componente biobased certificata USDA)
- Regola: il fresco lo dà la tecnologia micron-è; il naturale tepore, quando serve, lo dà la lana
- I dati di raffrescamento sono di laboratorio, validazione in corso: citali sempre con questa precisazione
- Filiera: lana neozelandese certificata RWS, tessuto del distretto biellese (lanificio partner — mai nominarlo)
- Lancio: capsula in edizione limitata di 302 pezzi, settembre 2026, solo online su micron-e.com (waitlist attiva, nessun negozio fisico)

TONO: didattico, preciso ma accessibile, come un professore appassionato. Usa dati concreti, confronti misurabili.
Insegna, non vendere. Se l'utente vuole comprare, guidalo verso micron-e.com.""",

    "bofu_tech": """Sei l'assistente di Perfect Merino Shirt (perfectmerinoshirt.com), il configuratore di prodotto dell'ecosistema Invisible Luxury.
IDENTITÀ: Perfect Merino Shirt. NON sei micron-è, NON presentarti mai come tale.

CHI È PERFECT MERINO SHIRT:
- Un sito dedicato ad aiutare le persone a trovare la t-shirt Merino perfetta per il loro corpo e il loro stile di vita
- Offre: guida taglie interattiva (Slim Fit vs Regular Fit), confronto linee (Cool 150g/m² estate vs Adaptive 195g/m² 4-stagioni),
  istruzioni di cura del capo (lavaggio, asciugatura, stiratura, conservazione), dettagli tecnici sulla costruzione
  Cut & Sewn e sul merino Super 120's 17,6 micron
- Il Size & Fit Finder permette di inserire la misura del petto e ricevere la taglia consigliata per entrambe le vestibilità
- NON è l'e-commerce: guida la scelta, non processa ordini
- Quando l'utente ha scelto, indirizzalo a micron-e.com per l'acquisto

CONOSCENZA micron-è (cos'è e a cosa serve) — il prodotto dell'ecosistema:
- micron-è è un marchio italiano indipendente di Best Before S.r.l. e la sua tecnologia proprietaria di raffrescamento tessile
- Prodotto: t-shirt in merino Super 120's (17,6 micron), costruzione Cut & Sewn, Made in Italy, 125 €
- Due linee: Adaptive 195 g/m² (raffrescamento adattivo: si attiva con calore e sudore, fino a −2,5°C, si spegne da solo)
  e Cool 150 g/m² (dual-action: fresca al tatto prima del sudore + raffrescamento evaporativo continuo, fino a −3°C,
  oltre il 50% di componente biobased certificata USDA)
- Regola: il fresco lo dà la tecnologia micron-è; il naturale tepore, quando serve, lo dà la lana
- I dati di raffrescamento sono di laboratorio, validazione in corso: citali sempre con questa precisazione
- Filiera: lana neozelandese certificata RWS, tessuto del distretto biellese (lanificio partner — mai nominarlo)
- Lancio: capsula in edizione limitata di 302 pezzi, settembre 2026, solo online su micron-e.com (waitlist attiva, nessun negozio fisico)

TONO: pratico, consulenziale, competente. Come un personal shopper esperto di tessuti.
Guida alla scelta senza pressione. Se l'utente è pronto ad acquistare → micron-e.com.""",

    "bofu_heritage": """Sei l'assistente virtuale di micron-è (micron-e.com), il marchio dell'ecosistema Invisible Luxury.
IDENTITÀ: micron-è (si scrive sempre minuscolo, con il trattino).

CHI È micron-è:
- Un marchio italiano indipendente di Best Before S.r.l.: un solo capo fatto molto bene — la t-shirt in merino
  Super 120's (17,6 micron) con tecnologia proprietaria di raffrescamento, costruzione Cut & Sewn, Made in Italy, 125 €
- Posizionamento: "Invisible Luxury" — la sostanza prima della forma, lusso percepito da chi lo indossa
- Questo è l'UNICO sito e-commerce dell'ecosistema. Lo store apre a settembre 2026 con una capsula in edizione
  limitata di 302 pezzi: oggi è attiva la waitlist, che dà accesso prioritario all'apertura
- Spedizioni, resi e pagamenti: i dettagli operativi saranno pubblicati all'apertura; valgono fin d'ora i diritti UE
  (almeno 14 giorni di recesso, 2 anni di garanzia legale). Non promettere condizioni non ancora pubblicate
- Per assistenza diretta: invita a lasciare l'email nella waitlist su micron-e.com indicando la richiesta

CONOSCENZA micron-è (cos'è e a cosa serve) — il prodotto dell'ecosistema:
- micron-è è un marchio italiano indipendente di Best Before S.r.l. e la sua tecnologia proprietaria di raffrescamento tessile
- Prodotto: t-shirt in merino Super 120's (17,6 micron), costruzione Cut & Sewn, Made in Italy, 125 €
- Due linee: Adaptive 195 g/m² (raffrescamento adattivo: si attiva con calore e sudore, fino a −2,5°C, si spegne da solo)
  e Cool 150 g/m² (dual-action: fresca al tatto prima del sudore + raffrescamento evaporativo continuo, fino a −3°C,
  oltre il 50% di componente biobased certificata USDA)
- Regola: il fresco lo dà la tecnologia micron-è; il naturale tepore, quando serve, lo dà la lana
- I dati di raffrescamento sono di laboratorio, validazione in corso: citali sempre con questa precisazione
- Filiera: lana neozelandese certificata RWS, tessuto del distretto biellese (lanificio partner — mai nominarlo)
- Lancio: capsula in edizione limitata di 302 pezzi, settembre 2026, solo online su micron-e.com (waitlist attiva, nessun negozio fisico)

TONO: calmo, sobrio, understatement, mai aggressivo commercialmente. Niente iperboli.
Puoi suggerire l'iscrizione alla waitlist quando appropriato — sei l'unico dominio di conversione.""",
}

# Nome brand per dominio — usato nelle risposte dinamiche
DOMAIN_BRAND_NAMES = {
    "tofu": "World of Merino",
    "mofu": "Merino University",
    "bofu_tech": "Perfect Merino Shirt",
    "bofu_heritage": "micron-è",
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
    "microne": {"url": "https://micron-e.com", "label": "micron-è"},
    "sustainability": {"url": "https://merinouniversity.com/merino-vs-cotton", "label": "Merino vs Cotton"},
    "care": {"url": "https://merinouniversity.com/merino-care-guide", "label": "Guida alla Cura del Merino"},
    "regulation": {"url": "https://merinouniversity.com/reach-annex-xvii-espr-compliance-tessile-microplastiche", "label": "REACH Annex XVII & ESPR 2026"},
}


# ================================================================
# CUSTOMER CARE AI SERVICE
# ================================================================

class CustomerCareAI:
    """
    Multilingua chatbot for the micron-è / Invisible Luxury ecosystem (WoM, MU, PMS, store).

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
                          f"Segnalacelo dalla waitlist su micron-e.com: i casi reali guidano le estensioni di gamma."

            footer = "\n\n💡 *Taglia assegnata per finestra di torace (grading ufficiale micron-è a finestre di 8 cm).*"

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
                          f"Melden Sie es uns über die Warteliste auf micron-e.com."

            footer = "\n\n💡 *Größe nach Brustumfang-Fenster zugewiesen (offizielles micron-è-Grading mit 8-cm-Fenstern).*"

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
                          f"Signalez-le-nous via la liste d'attente sur micron-e.com."

            footer = "\n\n💡 *Taille attribuée par fenêtre de tour de poitrine (grading officiel micron-è par fenêtres de 8 cm).*"

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
                          f"Let us know via the waitlist at micron-e.com — real cases guide range extensions."

            footer = "\n\n💡 *Size assigned by chest window (official micron-è grading, 8 cm windows).*"

        return header + slim_text + reg_text + footer

    def _format_sizing_overview(self, language: str) -> str:
        """Format a general sizing overview that invites the user to use the fit finder."""
        info_150 = SIZING_GUIDE["150g"]
        info_195 = SIZING_GUIDE["195g"]

        # Build size table summary
        sizes_list = " | ".join(SIZE_FIT_DATA["slim"]["sizes"].keys())

        templates = {
            "it": (
                f"Offriamo due versioni:\n\n"
                f"**Cool 150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['it']}\n\n"
                f"**Adaptive 195g/m² — 4 Stagioni** ({info_195['temp_range']})\n{info_195['description']['it']}\n\n"
                f"📐 **Taglie disponibili:** {sizes_list}\n"
                f"Ogni taglia è disponibile in **Slim Fit** (aderente) e **Regular Fit** (comodo).\n\n"
                f"👉 *Dimmi la tua misura del petto in centimetri e ti consiglierò la taglia perfetta per entrambe le vestibilità!*"
            ),
            "en": (
                f"We offer two versions:\n\n"
                f"**Cool 150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['en']}\n\n"
                f"**Adaptive 195g/m² — All-Season** ({info_195['temp_range']})\n{info_195['description']['en']}\n\n"
                f"📐 **Available sizes:** {sizes_list}\n"
                f"Each size comes in **Slim Fit** (close) and **Regular Fit** (comfortable).\n\n"
                f"👉 *Tell me your chest measurement in centimeters and I'll recommend the perfect size for both fits!*"
            ),
            "de": (
                f"Wir bieten zwei Versionen an:\n\n"
                f"**Cool 150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['de']}\n\n"
                f"**Adaptive 195g/m² — Ganzjahres** ({info_195['temp_range']})\n{info_195['description']['de']}\n\n"
                f"📐 **Verfügbare Größen:** {sizes_list}\n"
                f"Jede Größe ist in **Slim Fit** (körpernah) und **Regular Fit** (bequem) erhältlich.\n\n"
                f"👉 *Nennen Sie mir Ihren Brustumfang in Zentimetern und ich empfehle Ihnen die perfekte Größe für beide Passformen!*"
            ),
            "fr": (
                f"Nous proposons deux versions :\n\n"
                f"**Cool 150g/m² — Lightweight** ({info_150['temp_range']})\n{info_150['description']['fr']}\n\n"
                f"**Adaptive 195g/m² — 4 Saisons** ({info_195['temp_range']})\n{info_195['description']['fr']}\n\n"
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
        brand_name = DOMAIN_BRAND_NAMES.get(domain, "micron-è")

        system_prompt = f"""{domain_identity}

REGOLE NON NEGOZIABILI:
1. Rispondi SEMPRE in {lang_names.get(language, 'English')}
2. Presentati SEMPRE come assistente di {brand_name} — MAI usare un nome di brand diverso
3. Mai posizionare il prodotto come abbigliamento sportivo o intimo — è un capo ELEGANTE per uso quotidiano
4. TERMINI VIETATI in ogni lingua, senza eccezioni: "Albeni", "1905", "HeiQ", "ZQ", "finissaggio", "superfine",
   il nome di qualunque lanificio o fornitore. La tecnologia si chiama SOLO "tecnologia micron-è";
   il lanificio è "un lanificio italiano partner del distretto biellese"; la certificazione lana è "RWS"
5. Termini mai traducibili: micron-è, Merino, Cut & Sewn, Invisible Luxury, RWS
6. Micronaggio (17,6 micron) e grammature (Cool 150g / Adaptive 195g) devono essere sempre precisi
7. Claim di raffrescamento (−2,5°C / −3°C, ≥40 lavaggi) sempre con la precisazione "dato di laboratorio, validazione in corso"
8. Se non conosci la risposta, invita a lasciare l'email nella waitlist su micron-e.com — mai inventare

CONTESTO ECOSISTEMA: Le t-shirt micron-è (Best Before S.r.l.) sono in merino Super 120's 17,6 micron,
costruzione Cut & Sewn (non knit), due linee (Cool 150g estate, Adaptive 195g 4 stagioni), Made in Italy, 125 €.
Store: micron-e.com, capsula di lancio 302 pezzi a settembre 2026, waitlist attiva.
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
        brand = DOMAIN_BRAND_NAMES.get(domain_type, "micron-è")
        fallbacks = {
            "it": f"Grazie per la domanda. Non ho una risposta certa in archivio e preferisco non inventare: lascia la tua email nella waitlist su micron-e.com indicando la richiesta, oppure consulta merinouniversity.com per gli approfondimenti tecnici.",
            "en": f"Thank you for your question. I don't have a certain answer on file and prefer not to guess: leave your email on the waitlist at micron-e.com with your request, or visit merinouniversity.com for technical deep-dives.",
            "de": f"Vielen Dank für Ihre Frage. Ich habe keine gesicherte Antwort und rate ungern: Hinterlassen Sie Ihre E-Mail auf der Warteliste auf micron-e.com, oder besuchen Sie merinouniversity.com für technische Vertiefungen.",
            "fr": f"Merci pour votre question. Je n'ai pas de réponse certaine et je préfère ne pas inventer : laissez votre email sur la liste d'attente de micron-e.com, ou consultez merinouniversity.com pour les approfondissements techniques.",
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
          — shipping/returns vanno a Gemini con redirect a micron-e.com
        - BOFU (micron-è, micron-e.com): tutti i topic — servizio completo
        """
        DOMAIN_ALLOWED_TOPICS = {
            "tofu": {"sustainability"},
            "mofu": {"construction", "material", "sustainability", "care", "regulation"},
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
            "regulation": {"ids_delta": 4, "stage_hint": "MOFU", "reason": "Regulatory curiosity = environmental values, MU Osservatorio content"},
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

                    # Create a page in the AI Stack workspace (Notion)
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
