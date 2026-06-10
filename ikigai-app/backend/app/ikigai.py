import os
import json
import logging
from typing import List

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = ["en", "zh", "hi", "es", "fr"]

LANG_NAMES = {
    "en": "English",
    "zh": "Chinese (Simplified)",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
}

DOMAIN_LABELS = {
    "en": {
        "love": "What You Love",
        "good_at": "What You're Good At",
        "world_needs": "What the World Needs",
        "paid_for": "What You Can Offer",
    },
    "zh": {
        "love": "你热爱的",
        "good_at": "你擅长的",
        "world_needs": "世界需要的",
        "paid_for": "你能提供的",
    },
    "hi": {
        "love": "जो आप प्यार करते हैं",
        "good_at": "जिसमें आप अच्छे हैं",
        "world_needs": "दुनिया को जो चाहिए",
        "paid_for": "जो आप दे सकते हैं",
    },
    "es": {
        "love": "Lo que Amas",
        "good_at": "En lo que Eres Bueno",
        "world_needs": "Lo que el Mundo Necesita",
        "paid_for": "Lo que Puedes Ofrecer",
    },
    "fr": {
        "love": "Ce que Vous Aimez",
        "good_at": "Ce en quoi Vous Excellez",
        "world_needs": "Ce dont le Monde a Besoin",
        "paid_for": "Ce que Vous Pouvez Offrir",
    },
}

FALLBACK = {
    "en": {
        "eyebrow": "Where your world begins",
        "centre_intro": "A reflection drawn from your own words.",
        "centre": (
            "You are drawn to {love}, and you bring a rare quality to it — the kind that shows up in {talent}. "
            "Where you feel most called is toward {world}, and the world around you is already beginning to notice "
            "what you offer through {offer}."
        ),
        "love": (
            "When you speak of {q1}, something in you comes alive. Your energy shifts when you are {q2} — "
            "this is not coincidence."
        ),
        "good_at": (
            "You have a gift for {q3}, though you may not always see it that way. The ease with which you {q4} "
            "is something others quietly admire."
        ),
        "world_needs": (
            "The world you want to live in is shaped by your response to {q5}. "
            "The change you seek — {q6} — has your fingerprints on it already."
        ),
        "paid_for": (
            "There is real value in what you offer through {q7}. "
            "A life shaped by {q8} is not only possible — it may already be forming."
        ),
        "closing": "Ikigai is not a destination but a direction. You are already on the path.",
    },
    "zh": {
        "eyebrow": "你的世界从这里开始",
        "centre_intro": "这是一段源自你自己话语的省思。",
        "centre": (
            "你被{love}深深吸引，并为之带来一种罕见的品质——那种在{talent}中显现出来的特质。"
            "你内心最深处的召唤指向{world}，而你通过{offer}所提供的价值，世界已经开始悄然感受到。"
        ),
        "love": (
            "当你谈起{q1}，你内心的某种东西便活了起来。当你沉浸于{q2}时，你的整个状态都会改变——这绝非偶然。"
        ),
        "good_at": (
            "你在{q3}上有着天赋，尽管你未必总是这样看待自己。你{q4}的那份自如与从容，是旁人默默欣赏的。"
        ),
        "world_needs": (
            "你对{q5}的回应，塑造了你想要生活其中的那个世界。你所渴望的改变——{q6}——已经留下了你的印记。"
        ),
        "paid_for": (
            "你通过{q7}所能提供的，有着真实而深刻的价值。以{q8}为核心的生活，不仅可能实现——也许已经在悄悄成形。"
        ),
        "closing": "生命的意义不是一个终点，而是一个方向。你已经走在路上了。",
    },
    "hi": {
        "eyebrow": "जहाँ आपकी दुनिया शुरू होती है",
        "centre_intro": "यह चिंतन आपके अपने शब्दों से उभरा है।",
        "centre": (
            "आप {love} की ओर खिंचते हैं, और इसमें आप एक विशेष गुण लाते हैं — वह गुण जो {talent} में झलकता है। "
            "जहाँ आप सबसे अधिक बुलाया महसूस करते हैं, वह है {world}, "
            "और आपके आस-पास की दुनिया पहले से ही उस मूल्य को महसूस करने लगी है जो आप {offer} के माध्यम से देते हैं।"
        ),
        "love": (
            "जब आप {q1} की बात करते हैं, तो आपके भीतर कुछ जीवंत हो उठता है। "
            "जब आप {q2} में होते हैं तो आपकी ऊर्जा बदल जाती है — यह संयोग नहीं है।"
        ),
        "good_at": (
            "आपमें {q3} की एक विशेष प्रतिभा है, भले ही आप हमेशा इसे इस तरह न देखते हों। "
            "जिस सहजता से आप {q4} करते हैं, उसे दूसरे लोग चुपचाप सराहते हैं।"
        ),
        "world_needs": (
            "जो दुनिया आप जीना चाहते हैं, वह {q5} के प्रति आपकी प्रतिक्रिया से आकार लेती है। "
            "जो बदलाव आप चाहते हैं — {q6} — उस पर पहले से आपकी छाप है।"
        ),
        "paid_for": (
            "{q7} के माध्यम से आप जो प्रदान करते हैं, उसमें वास्तविक मूल्य है। "
            "{q8} पर आधारित जीवन न केवल संभव है — शायद वह पहले से बन भी रहा है।"
        ),
        "closing": "इकिगाई कोई मंज़िल नहीं, बल्कि एक दिशा है। आप पहले से ही इस राह पर हैं।",
    },
    "es": {
        "eyebrow": "Donde comienza tu mundo",
        "centre_intro": "Una reflexión construida desde tus propias palabras.",
        "centre": (
            "Te sientes atraído hacia {love}, y traes a ello una cualidad singular — la que se manifiesta en {talent}. "
            "Donde más te sientes llamado es hacia {world}, y el mundo a tu alrededor ya comienza a notar "
            "lo que ofreces a través de {offer}."
        ),
        "love": (
            "Cuando hablas de {q1}, algo en ti cobra vida. Tu energía cambia cuando estás {q2} — "
            "esto no es casualidad."
        ),
        "good_at": (
            "Tienes un don para {q3}, aunque quizás no siempre lo veas así. "
            "La facilidad con la que {q4} es algo que otros admiran en silencio."
        ),
        "world_needs": (
            "El mundo en el que quieres vivir está moldeado por tu respuesta a {q5}. "
            "El cambio que buscas — {q6} — ya lleva tus huellas."
        ),
        "paid_for": (
            "Hay un valor real en lo que ofreces a través de {q7}. "
            "Una vida moldeada por {q8} no solo es posible — quizás ya se está formando."
        ),
        "closing": "El ikigai no es un destino, sino una dirección. Ya estás en el camino.",
    },
    "fr": {
        "eyebrow": "Là où votre monde commence",
        "centre_intro": "Une réflexion tirée de vos propres mots.",
        "centre": (
            "Vous êtes attiré par {love}, et vous y apportez une qualité rare — celle qui transparaît dans {talent}. "
            "Là où vous vous sentez le plus appelé, c'est vers {world}, "
            "et le monde autour de vous commence déjà à percevoir ce que vous offrez à travers {offer}."
        ),
        "love": (
            "Lorsque vous parlez de {q1}, quelque chose en vous s'éveille. "
            "Votre énergie change quand vous êtes {q2} — ce n'est pas un hasard."
        ),
        "good_at": (
            "Vous avez un don pour {q3}, même si vous ne le voyez pas toujours ainsi. "
            "La facilité avec laquelle vous {q4} est quelque chose que les autres admirent discrètement."
        ),
        "world_needs": (
            "Le monde dans lequel vous voulez vivre est façonné par votre réponse à {q5}. "
            "Le changement que vous cherchez — {q6} — porte déjà votre empreinte."
        ),
        "paid_for": (
            "Il y a une vraie valeur dans ce que vous offrez à travers {q7}. "
            "Une vie façonnée par {q8} n'est pas seulement possible — elle est peut-être déjà en train de prendre forme."
        ),
        "closing": "L'ikigai n'est pas une destination, mais une direction. Vous êtes déjà sur le chemin.",
    },
}


def _fallback(answers: List[str], lang: str) -> dict:
    safe_lang = lang if lang in SUPPORTED_LANGS else "en"
    tmpl = FALLBACK[safe_lang]
    labels = DOMAIN_LABELS[safe_lang]

    q1, q2, q3, q4, q5, q6, q7, q8 = answers

    fmt_kwargs = {
        "love": q1,
        "talent": q3,
        "world": q5,
        "offer": q7,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4,
        "q5": q5,
        "q6": q6,
        "q7": q7,
        "q8": q8,
    }

    return {
        "eyebrow": tmpl["eyebrow"],
        "centre_intro": tmpl["centre_intro"],
        "centre": tmpl["centre"].format(**fmt_kwargs),
        "sections": [
            {
                "title": labels["love"],
                "body": tmpl["love"].format(**fmt_kwargs),
                "domain": "love",
            },
            {
                "title": labels["good_at"],
                "body": tmpl["good_at"].format(**fmt_kwargs),
                "domain": "good_at",
            },
            {
                "title": labels["world_needs"],
                "body": tmpl["world_needs"].format(**fmt_kwargs),
                "domain": "world_needs",
            },
            {
                "title": labels["paid_for"],
                "body": tmpl["paid_for"].format(**fmt_kwargs),
                "domain": "paid_for",
            },
        ],
        "closing": tmpl["closing"],
    }


async def build_reflection(answers: List[str], lang: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _fallback(answers, lang)

    safe_lang = lang if lang in SUPPORTED_LANGS else "en"
    lang_name = LANG_NAMES[safe_lang]
    labels = DOMAIN_LABELS[safe_lang]

    q1, q2, q3, q4, q5, q6, q7, q8 = answers

    system_prompt = (
        f"You are a warm, perceptive guide helping someone discover their ikigai — their reason for being. "
        f"You write with depth, care, and specificity, always referencing the person's own words. "
        f"Respond in {lang_name}. Return valid JSON only — no preamble, no markdown fences."
    )

    user_prompt = f"""A person has answered eight questions to explore their ikigai. Using their exact words as the foundation, write a personalised reflection in {lang_name}.

Their answers:

WHAT THEY LOVE:
  Q1 (What do you love doing?): {q1}
  Q2 (What makes you feel alive?): {q2}

WHAT THEY'RE GOOD AT:
  Q3 (What are you talented at?): {q3}
  Q4 (What do you do effortlessly?): {q4}

WHAT THE WORLD NEEDS:
  Q5 (What problems move you?): {q5}
  Q6 (What change do you want to see?): {q6}

WHAT THEY CAN OFFER:
  Q7 (What would others pay you for?): {q7}
  Q8 (What is your ideal livelihood?): {q8}

Return a JSON object with exactly this structure (all text in {lang_name}):
{{
  "eyebrow": "<short poetic label, 3-6 words, capturing the essence of this person's ikigai>",
  "centre_intro": "<one warm sentence introducing the reflection>",
  "centre": "<2-3 sentence core reflection weaving together all four domains, referencing their actual words>",
  "sections": [
    {{
      "title": "{labels['love']}",
      "body": "<2-3 sentences reflecting on what they love, referencing Q1 and Q2 specifically>",
      "domain": "love"
    }},
    {{
      "title": "{labels['good_at']}",
      "body": "<2-3 sentences reflecting on their strengths, referencing Q3 and Q4 specifically>",
      "domain": "good_at"
    }},
    {{
      "title": "{labels['world_needs']}",
      "body": "<2-3 sentences reflecting on their contribution to the world, referencing Q5 and Q6 specifically>",
      "domain": "world_needs"
    }},
    {{
      "title": "{labels['paid_for']}",
      "body": "<2-3 sentences reflecting on their livelihood potential, referencing Q7 and Q8 specifically>",
      "domain": "paid_for"
    }}
  ],
  "closing": "<one warm, encouraging closing sentence>"
}}"""

    try:
        import anthropic

        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        client = anthropic.AsyncAnthropic(api_key=api_key)

        message = await client.messages.create(
            model=model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        required_keys = {"eyebrow", "centre_intro", "centre", "sections", "closing"}
        if not required_keys.issubset(data.keys()):
            raise ValueError(f"Missing keys in Claude response: {required_keys - data.keys()}")

        if not isinstance(data["sections"], list) or len(data["sections"]) != 4:
            raise ValueError("sections must be a list of exactly 4 items")

        for section in data["sections"]:
            if not {"title", "body", "domain"}.issubset(section.keys()):
                raise ValueError(f"Section missing required keys: {section}")

        return data

    except Exception as exc:
        logger.warning("Claude API call failed (%s: %s); using fallback.", type(exc).__name__, exc)
        return _fallback(answers, lang)
