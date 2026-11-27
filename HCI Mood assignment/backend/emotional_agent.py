"""Hybrid Emotional AI Agent: conditions Visual Type, Nav Type, and agent reasoning on live affect."""

from __future__ import annotations

import json
import re
from typing import Any
import urllib.error
import urllib.request

PRODUCT_CATALOG: list[dict[str, Any]] = [
    {
        "id": "p-phone-1",
        "name": "Redmi Note 13 Endurance",
        "brand": "Xiaomi",
        "category": "smartphone",
        "pricePkr": 52999,
        "priceUsd": 190,
        "rating": 4.7,
        "batteryHours": 42,
        "deliveryDays": 2,
        "warranty": "1 Year Official PTA",
        "vendor": "PriceOye",
        "specs": {"display": "6.67\" AMOLED 120Hz", "battery": "5000 mAh (33W)", "ramStorage": "8GB / 256GB", "camera": "108MP Main"},
        "pros": ["All-day 42h battery", "Bright crisp AMOLED for reading", "Best value under 55k PKR"],
        "cons": ["Average low-light video"],
        "bestFor": "Long campus days, note reading, budget value",
        "isBudgetPick": True,
    },
    {
        "id": "p-phone-2",
        "name": "Galaxy A25 Study Edition",
        "brand": "Samsung",
        "category": "smartphone",
        "pricePkr": 58500,
        "priceUsd": 210,
        "rating": 4.6,
        "batteryHours": 38,
        "deliveryDays": 1,
        "warranty": "1 Year Samsung Care",
        "vendor": "Daraz",
        "specs": {"display": "6.5\" Super AMOLED", "battery": "5000 mAh (25W)", "ramStorage": "6GB / 128GB", "camera": "50MP OIS"},
        "pros": ["4 years OS updates", "OIS camera for scanning slides", "Next-day delivery"],
        "cons": ["Charger not included in box"],
        "bestFor": "Long-term software reliability & clean UI",
        "isBudgetPick": False,
    },
    {
        "id": "p-phone-3",
        "name": "Tecno Spark 20 Pro+",
        "brand": "Tecno",
        "category": "smartphone",
        "pricePkr": 47999,
        "priceUsd": 172,
        "rating": 4.4,
        "batteryHours": 36,
        "deliveryDays": 2,
        "warranty": "1 Year Brand Warranty",
        "vendor": "PriceOye",
        "specs": {"display": "6.78\" Curved AMOLED", "battery": "5000 mAh (33W)", "ramStorage": "8GB / 256GB", "camera": "108MP"},
        "pros": ["Lowest price with 256GB", "Lightweight curved ergonomics"],
        "cons": ["Fewer OS updates"],
        "bestFor": "Tight student budget & high storage",
        "isBudgetPick": True,
    },
    {
        "id": "p-phone-4",
        "name": "Pixel 7a Refurb Certified",
        "brand": "Google",
        "category": "smartphone",
        "pricePkr": 74000,
        "priceUsd": 265,
        "rating": 4.8,
        "batteryHours": 29,
        "deliveryDays": 3,
        "warranty": "6 Months Seller",
        "vendor": "Daraz",
        "specs": {"display": "6.1\" OLED 90Hz", "battery": "4385 mAh", "ramStorage": "8GB / 128GB", "camera": "64MP Computational"},
        "pros": ["Best camera accuracy", "Zero bloatware stock Android"],
        "cons": ["Above 60k PKR budget", "Shorter battery than 5000mAh rivals"],
        "bestFor": "Mobile photography & clean Android purists",
        "isBudgetPick": False,
    },
    {
        "id": "p-hp-1",
        "name": "Soundcore Space Q45 ANC",
        "brand": "Anker",
        "category": "headphones",
        "pricePkr": 29500,
        "priceUsd": 105,
        "rating": 4.8,
        "batteryHours": 50,
        "deliveryDays": 1,
        "warranty": "18 Months Official",
        "vendor": "PriceOye",
        "specs": {"anc": "Adaptive -42dB ANC", "battery": "50h ANC On / 65h Off", "weight": "292g", "multipoint": "Dual Bluetooth 5.3"},
        "pros": ["50-hour marathon study battery", "Strong adaptive ANC for noisy cafes", "Plush low-clamp pads"],
        "cons": ["Slightly bulky carrying case"],
        "bestFor": "Quiet deep study, library & lecture focus",
        "isBudgetPick": True,
    },
    {
        "id": "p-hp-2",
        "name": "Sony WH-1000XM4 Studio",
        "brand": "Sony",
        "category": "headphones",
        "pricePkr": 68000,
        "priceUsd": 245,
        "rating": 4.9,
        "batteryHours": 30,
        "deliveryDays": 2,
        "warranty": "1 Year Official",
        "vendor": "Daraz",
        "specs": {"anc": "Dual-Sensor QN1 ANC", "battery": "30h", "weight": "254g", "multipoint": "Dual Bluetooth"},
        "pros": ["Class-leading voice/chatter isolation", "Featherlight 254g comfort"],
        "cons": ["Premium price tier"],
        "bestFor": "Maximum silence & multi-hour comfort",
        "isBudgetPick": False,
    },
    {
        "id": "p-hp-3",
        "name": "JBL Tune 770NC",
        "brand": "JBL",
        "category": "headphones",
        "pricePkr": 21999,
        "priceUsd": 79,
        "rating": 4.5,
        "batteryHours": 44,
        "deliveryDays": 2,
        "warranty": "1 Year Official",
        "vendor": "PriceOye",
        "specs": {"anc": "Adaptive ANC", "battery": "44h ANC On", "weight": "232g", "multipoint": "Yes"},
        "pros": ["Lightest on-head feel (232g)", "Affordable student pricing"],
        "cons": ["Smaller earcups for large ears"],
        "bestFor": "Budget quiet commuting & light study",
        "isBudgetPick": True,
    },
    {
        "id": "p-lap-1",
        "name": "ThinkPad X1 Carbon Gen 11 (Refurb)",
        "brand": "Lenovo",
        "category": "laptop",
        "pricePkr": 185000,
        "priceUsd": 665,
        "rating": 4.9,
        "batteryHours": 14,
        "deliveryDays": 2,
        "warranty": "1 Year Local",
        "vendor": "Daraz",
        "specs": {"cpu": "Core i7-1355U", "ram": "16GB LPDDR5", "weight": "1.12 kg", "display": "14\" Matte IPS 400-nit"},
        "pros": ["1.12 kg ultraportable", "Best-in-class coding keyboard", "Anti-glare matte screen"],
        "cons": ["No dedicated GPU for 3D gaming"],
        "bestFor": "HCI research, coding & all-day campus mobility",
        "isBudgetPick": False,
    },
    {
        "id": "p-lap-2",
        "name": "Zenbook 14 OLED Study Pro",
        "brand": "ASUS",
        "category": "laptop",
        "pricePkr": 168000,
        "priceUsd": 605,
        "rating": 4.7,
        "batteryHours": 12,
        "deliveryDays": 2,
        "warranty": "1 Year ASUS",
        "vendor": "PriceOye",
        "specs": {"cpu": "Ryzen 7 7730U", "ram": "16GB / 512GB", "weight": "1.35 kg", "display": "14\" 2.8K OLED"},
        "pros": ["Sharp 2.8K OLED for UI design", "Quiet thermal profile"],
        "cons": ["Glossy screen under direct sun"],
        "bestFor": "UI prototyping, coding & visual design",
        "isBudgetPick": False,
    },
    {
        "id": "p-lap-3",
        "name": "IdeaPad Slim 3 Student",
        "brand": "Lenovo",
        "category": "laptop",
        "pricePkr": 112000,
        "priceUsd": 402,
        "rating": 4.5,
        "batteryHours": 10,
        "deliveryDays": 1,
        "warranty": "1 Year Official",
        "vendor": "PriceOye",
        "specs": {"cpu": "Core i5-1235U", "ram": "16GB / 512GB", "weight": "1.62 kg", "display": "15.6\" FHD Anti-Glare"},
        "pros": ["16GB RAM at budget price", "Next-day delivery"],
        "cons": ["Slightly heavier 1.62 kg"],
        "bestFor": "Budget coding, essays & Python ML",
        "isBudgetPick": True,
    },
    {
        "id": "p-mon-1",
        "name": "Dell P2422H Ergonomic IPS",
        "brand": "Dell",
        "category": "monitor",
        "pricePkr": 54000,
        "priceUsd": 195,
        "rating": 4.8,
        "batteryHours": 0,
        "deliveryDays": 2,
        "warranty": "3 Years Dell",
        "vendor": "Daraz",
        "specs": {"panel": "24\" FHD IPS ComfortView+", "stand": "Height/Pivot/Swivel", "ports": "HDMI + DP + USB Hub"},
        "pros": ["Hardware low-blue-light ComfortView+", "Full ergonomic height adjust"],
        "cons": ["60Hz refresh rate"],
        "bestFor": "Eye-fatigue reduction & long writing sessions",
        "isBudgetPick": True,
    },
    {
        "id": "p-mon-2",
        "name": "LG UltraFine 27UP650 4K",
        "brand": "LG",
        "category": "monitor",
        "pricePkr": 98000,
        "priceUsd": 352,
        "rating": 4.7,
        "batteryHours": 0,
        "deliveryDays": 3,
        "warranty": "2 Years Official",
        "vendor": "Daraz",
        "specs": {"panel": "27\" 4K UHD IPS", "stand": "Height/Tilt", "ports": "2x HDMI + DP"},
        "pros": ["Crisp 4K typography reduces eye strain", "Large split-screen canvas"],
        "cons": ["Higher price"],
        "bestFor": "Multi-pane coding & research comparison",
        "isBudgetPick": False,
    },
]

# Explicit alignment with the class whiteboard taxonomy: Emotion -> Visual Type + Nav Type
VISUAL_NAV_TAXONOMY: dict[str, dict[str, Any]] = {
    "prompt_only_control": {
        "visualType": "Standard Z-Pattern Grid (Control)",
        "navType": "Horizontal Top-Down (Control)",
        "agentTone": "Standard Neutral (Unadapted)",
        "maxCards": 12,
        "showSpecMatrix": True,
        "showPromos": True,
        "voiceRecommended": False,
        "targetScale": 1.0,
        "typographyScale": 1.0,
        "lineHeight": 1.55,
    },
    "focused": {
        "visualType": "Focused & Spotlight",
        "navType": "Bento Box",
        "agentTone": "Analytical & Concise",
        "maxCards": 6,
        "showSpecMatrix": True,
        "showPromos": False,
        "voiceRecommended": False,
        "targetScale": 1.0,
        "typographyScale": 1.0,
        "lineHeight": 1.55,
    },
    "overwhelmed": {
        "visualType": "Focused & Spotlight",
        "navType": "Single-Path Guided Stepper",
        "agentTone": "Calm De-Escalating (1 Clear Choice)",
        "maxCards": 1,
        "showSpecMatrix": False,
        "showPromos": False,
        "voiceRecommended": False,
        "targetScale": 1.26,
        "typographyScale": 1.1,
        "lineHeight": 1.72,
    },
    "fatigued": {
        "visualType": "Minimalist Calm List",
        "navType": "Low-Friction Linear Stack",
        "agentTone": "Warm Low-Effort + Voice Assist",
        "maxCards": 3,
        "showSpecMatrix": False,
        "showPromos": False,
        "voiceRecommended": True,
        "targetScale": 1.16,
        "typographyScale": 1.14,
        "lineHeight": 1.82,
    },
    "energized": {
        "visualType": "Visual Bento & Card Grid",
        "navType": "Bento Box + Visual Facets",
        "agentTone": "Exploratory & Comparative",
        "maxCards": 8,
        "showSpecMatrix": True,
        "showPromos": False,
        "voiceRecommended": False,
        "targetScale": 1.04,
        "typographyScale": 1.02,
        "lineHeight": 1.6,
    },
    "disoriented": {
        "visualType": "Guided Z-Pattern & Anchor",
        "navType": "Horizontal Top-Down + Breadcrumbs",
        "agentTone": "Structured Step-by-Step Guide",
        "maxCards": 3,
        "showSpecMatrix": False,
        "showPromos": False,
        "voiceRecommended": False,
        "targetScale": 1.1,
        "typographyScale": 1.06,
        "lineHeight": 1.66,
    },
}


def _extract_prompt_intent(prompt: str) -> dict[str, Any]:
    lower = prompt.lower()
    category = None
    if any(w in lower for w in ("phone", "smartphone", "mobile", "android")):
        category = "smartphone"
    elif any(w in lower for w in ("headphone", "earphone", "anc", "audio", "quiet")):
        category = "headphones"
    elif any(w in lower for w in ("laptop", "notebook", "thinkpad", "coding", "programming")):
        category = "laptop"
    elif any(w in lower for w in ("monitor", "screen", "display", "eye")):
        category = "monitor"

    # Extract PKR budget if mentioned (e.g. "60,000" or "60k")
    budget_pkr = None
    m_k = re.search(r"(\d+)\s*k\b", lower)
    m_num = re.search(r"(\d{2,3}[,\d]*)\s*(pkr|rs)?", lower)
    if m_k:
        budget_pkr = int(m_k.group(1)) * 1000
    elif m_num:
        digits = int(m_num.group(1).replace(",", ""))
        if digits >= 10000:
            budget_pkr = digits

    priorities: list[str] = []
    if any(w in lower for w in ("battery", "long", "endurance", "all-day")):
        priorities.append("battery")
    if any(w in lower for w in ("cheap", "budget", "under", "value", "student")):
        priorities.append("budget")
    if any(w in lower for w in ("quiet", "study", "focus", "anc", "noise")):
        priorities.append("study")
    if any(w in lower for w in ("light", "portable", "weight", "campus")):
        priorities.append("portable")
    if any(w in lower for w in ("camera", "photo")):
        priorities.append("camera")

    return {"category": category, "budget_pkr": budget_pkr, "priorities": priorities}


def _score_products(prompt: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    intent = _extract_prompt_intent(prompt)
    cat = intent["category"]
    budget = intent["budget_pkr"]
    prios = intent["priorities"]

    scored: list[tuple[float, dict[str, Any]]] = []
    for item in PRODUCT_CATALOG:
        score = float(item["rating"]) * 10.0
        if cat and item["category"] == cat:
            score += 45.0
        elif cat and item["category"] != cat:
            score -= 25.0

        if budget is not None:
            if item["pricePkr"] <= budget:
                score += 22.0
            else:
                score -= 20.0

        if "battery" in prios:
            score += item["batteryHours"] * 0.45
        if "budget" in prios and item["isBudgetPick"]:
            score += 12.0
        if "study" in prios and ("study" in item["bestFor"].lower() or "anc" in json.dumps(item["specs"]).lower()):
            score += 16.0
        if "portable" in prios and ("1.12" in json.dumps(item["specs"]) or "light" in json.dumps(item["pros"]).lower()):
            score += 14.0
        if "camera" in prios and "camera" in json.dumps(item["specs"]).lower():
            score += 12.0

        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored], intent


def _call_external_llm(
    prompt: str,
    scenario: str,
    condition: str,
    emotion_state: str,
    affective: dict[str, Any],
    top_names: list[str],
    llm_config: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    provider = str(llm_config.get("provider", "gemini")).lower()
    api_key = str(llm_config.get("api_key", "")).strip()
    if not api_key:
        return None, None

    system_msg = (
        "You are an Emotional AI Agent powering an adaptive Generative UI. "
        "Given the user's prompt, scenario, condition, and live emotion state, "
        "respond ONLY with valid JSON containing keys: "
        '"headline" (short string), "message" (2 concise sentences tailored to their emotional state), '
        '"rationaleBullets" (array of 3 short strings), "scaffoldingCue" (1 short actionable next step).'
    )
    user_msg = json.dumps(
        {
            "prompt": prompt,
            "scenario": scenario,
            "condition": condition,
            "emotionState": emotion_state,
            "valence": affective.get("valence", 0.0),
            "arousal": affective.get("arousal", 0.0),
            "cognitiveLoad": affective.get("cognitive_load", 0.0),
            "topMatchedItems": top_names[:3],
        }
    )

    try:
        if provider == "openai":
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(
                    {
                        "model": "gpt-4o-mini",
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_msg},
                            {"role": "user", "content": user_msg},
                        ],
                        "temperature": 0.4,
                    }
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            raw_text = body["choices"][0]["message"]["content"]
            return json.loads(raw_text), None

        # Default: Gemini REST API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(
                {
                    "contents": [{"parts": [{"text": f"{system_msg}\n\nInput:\n{user_msg}"}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        raw_text = body["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text), None
    except Exception as exc:
        return None, str(exc)


def run_emotional_agent(
    prompt: str,
    scenario: str,
    condition: str,
    affective: dict[str, Any],
    workspace: dict[str, Any],
    llm_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate emotion-conditioned Visual Type, Nav Type, and agent guidance for a prompt."""
    clean_prompt = prompt.strip() or "Help me make the best decision right now"
    state = str(affective.get("active_state", "focused"))
    dom_emotion = str(affective.get("dominant_emotion", "neutral"))
    val = float(affective.get("valence", 0.0))
    aro = float(affective.get("arousal", 0.0))
    load = float(affective.get("cognitive_load", 0.2))

    tax_key = "prompt_only_control" if condition == "prompt_only_control" else state
    spec = VISUAL_NAV_TAXONOMY.get(tax_key, VISUAL_NAV_TAXONOMY["focused"])

    if scenario == "commerce":
        ranked, intent = _score_products(clean_prompt)
        visible_items = ranked[: spec["maxCards"]]
        spotlight = ranked[0] if ranked else None
        top_names = [p["name"] for p in ranked[:3]]
        criteria_tags = [
            t for t in [
                intent["category"],
                f"<= {intent['budget_pkr']:,} PKR" if intent["budget_pkr"] else None,
                *[p.title() for p in intent["priorities"]],
            ] if t
        ] or ["All Categories", "Top Rated"]
    else:
        tasks = [t for t in workspace.get("tasks", []) if not t.get("completed")]
        visible_items = tasks[: spec["maxCards"]]
        spotlight = visible_items[0] if visible_items else None
        top_names = [t["title"] for t in visible_items[:3]]
        criteria_tags = ["Workspace", state.title()]

    # Condition- & emotion-specific synthesized responses
    if condition == "prompt_only_control":
        headline = f"Standard Results for: \"{clean_prompt[:52]}\""
        message = (
            "Prompt-Only Control active: showing the full standard Z-Pattern catalog and horizontal navigation. "
            "Your live emotional state is logged silently without adapting layout or decision density."
        )
        bullets = [
            f"Top match: {top_names[0]}" if top_names else "Showing all available items.",
            "All 12 catalog options & promotional badges remain visible.",
            "Use the top horizontal category bar to manually filter specs.",
        ]
        scaffolding = "Compare items manually in the standard grid below."
        hci_explanation = (
            "Control Baseline: Identical Z-Pattern + Horizontal Top-Down UI regardless of Valence/Arousal."
        )
    elif state == "overwhelmed":
        top_label = spotlight["name"] if (scenario == "commerce" and spotlight) else (spotlight["title"] if spotlight else "Top Priority")
        headline = f"1 Clear Recommendation — {top_label}"
        message = (
            f"I sensed elevated strain (Load {int(load*100)}%, Valence {val:+.2f}), so I collapsed {len(PRODUCT_CATALOG) if scenario=='commerce' else 'the'} options "
            f"into a single Focused Spotlight and a 3-step Guided Stepper to eliminate choice overload."
        )
        bullets = (
            [
                f"Why {spotlight['name']}: {spotlight['bestFor']}",
                f"Price: {spotlight['pricePkr']:,} PKR ({spotlight['vendor']}) • Rating {spotlight['rating']}/5",
                spotlight["pros"][0],
            ]
            if (scenario == "commerce" and spotlight)
            else [
                f"Focus exclusively on: {top_label}",
                "Secondary backlog items are tucked away to protect working memory.",
                "Buttons enlarged 1.26x (Fitts's Law) for effortless selection.",
            ]
        )
        scaffolding = "Follow Step 1 -> Step 2 -> Step 3 in the Guided Stepper below."
        hci_explanation = "Hick's Law choice reduction (12 -> 1 card) + Single-Path Guided Stepper + 1.26x Fitts targets."
    elif state == "fatigued":
        headline = "Low-Friction Shortlist (3 Calm Picks)"
        message = (
            f"Detected low arousal ({aro:+.2f}) and visual fatigue. I switched to a Minimalist Calm List "
            f"with larger readable typography (1.14x) and enabled Voice Read-Aloud so you don't have to scan dense tables."
        )
        bullets = [
            f"Best effortless pick: {top_names[0]}" if top_names else "Top 3 calm picks curated.",
            "Dense spec matrices and promotional banners hidden.",
            "Tap 'Read Summary Aloud' to listen instead of reading.",
        ]
        scaffolding = "Pick from these 3 pre-vetted options or listen to the audio summary."
        hci_explanation = "Minimalist Calm List + Low-Friction Linear Stack + 1.14x Typography + Voice Read-Aloud."
    elif state == "energized":
        headline = "Exploratory Bento Studio & Side-by-Side Comparison"
        message = (
            f"High positive engagement detected (Valence {val:+.2f}, Arousal {aro:+.2f}). "
            f"I expanded the Visual Bento & Card Grid with interactive facet chips and live spec comparison."
        )
        bullets = [
            f"Explore {len(visible_items)} ranked matches across interactive visual facets.",
            "Pin up to 3 items into the live side-by-side comparison tray.",
            "Bento Box navigation surfaces specs, ratings, and vendors simultaneously.",
        ]
        scaffolding = "Use visual facets and compare candidates side-by-side in the Bento Grid."
        hci_explanation = "Broaden-and-Build exploratory coupling: Visual Bento & Card Grid + Bento Box Facets."
    elif state == "disoriented":
        headline = "Guided Criteria Anchor & Top 3 Matches"
        message = (
            "Attention fragmentation detected. I anchored your search criteria as clickable breadcrumbs "
            "and structured the top 3 matches in a clean Guided Z-Pattern with plain-English spec badges."
        )
        bullets = [
            f"Active criteria locked: {', '.join(criteria_tags)}",
            "Reduced to top 3 clear matches with plain-English 'Best For' tags.",
            "Breadcrumb bar keeps your goal visible at all times.",
        ]
        scaffolding = "Review the locked criteria bar above before comparing the 3 anchored picks."
        hci_explanation = "Nielsen #6 Recognition over Recall: Guided Z-Pattern + Horizontal Top-Down Breadcrumbs."
    else:  # focused
        headline = f"Focused Spotlight + Bento Spec Matrix ({len(visible_items)} matches)"
        message = (
            "Steady baseline attention detected. Highlighting the strongest match in a Focused Spotlight "
            "alongside a structured Bento Box comparison matrix for fast analytical verification."
        )
        bullets = [
            f"#1 Analytical Match: {top_names[0]}" if top_names else "Ranked workspace items ready.",
            "Balanced Bento Box navigation preserves high information density without promo clutter.",
            "Full spec comparison available immediately below Spotlight.",
        ]
        scaffolding = "Verify the #1 Spotlight against the Bento comparison cards."
        hci_explanation = "Flow-preserving Focused & Spotlight layout with Bento Box navigation."

    used_llm = False
    llm_error = None
    if llm_config and llm_config.get("enabled") and str(llm_config.get("api_key", "")).strip():
        llm_out, llm_error = _call_external_llm(
            clean_prompt, scenario, condition, state, affective, top_names, llm_config
        )
        if llm_out:
            used_llm = True
            headline = str(llm_out.get("headline") or headline)
            message = str(llm_out.get("message") or message)
            if isinstance(llm_out.get("rationaleBullets"), list) and llm_out["rationaleBullets"]:
                bullets = [str(b) for b in llm_out["rationaleBullets"][:4]]
            scaffolding = str(llm_out.get("scaffoldingCue") or scaffolding)

    return {
        "prompt": clean_prompt,
        "scenario": scenario,
        "condition": condition,
        "emotionState": "control" if condition == "prompt_only_control" else state,
        "dominantEmotion": dom_emotion,
        "visualType": spec["visualType"],
        "navType": spec["navType"],
        "agentTone": spec["agentTone"],
        "headline": headline,
        "message": message,
        "rationaleBullets": bullets,
        "scaffoldingCue": scaffolding,
        "criteriaTags": criteria_tags,
        "spotlightItem": spotlight,
        "matchedItems": visible_items,
        "totalCatalogCount": len(PRODUCT_CATALOG) if scenario == "commerce" else len(workspace.get("tasks", [])),
        "hciExplanation": hci_explanation,
        "uiOverrides": {
            "maxCards": spec["maxCards"],
            "showSpecMatrix": spec["showSpecMatrix"],
            "showPromos": spec["showPromos"],
            "voiceRecommended": spec["voiceRecommended"],
            "targetScale": spec["targetScale"],
            "typographyScale": spec["typographyScale"],
            "lineHeight": spec["lineHeight"],
        },
        "usedLlm": used_llm,
        "llmError": llm_error,
    }


def compare_prompt_across_emotions(
    prompt: str,
    scenario: str,
    workspace: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run the EXACT SAME prompt across Control and all 5 emotional states to prove structural divergence."""
    scenarios_to_compare = [
        ("prompt_only_control", "focused", "neutral", 0.0, 0.0, 0.2),
        ("emotional_agent", "focused", "neutral", 0.05, -0.05, 0.2),
        ("emotional_agent", "overwhelmed", "fear", -0.58, 0.62, 0.78),
        ("emotional_agent", "fatigued", "sadness", -0.45, -0.42, 0.45),
        ("emotional_agent", "energized", "happiness", 0.62, 0.48, 0.16),
        ("emotional_agent", "disoriented", "surprise", 0.05, 0.55, 0.52),
    ]
    results = []
    for cond, st, dom, val, aro, load in scenarios_to_compare:
        res = run_emotional_agent(
            prompt=prompt,
            scenario=scenario,
            condition=cond,
            affective={
                "active_state": st,
                "dominant_emotion": dom,
                "valence": val,
                "arousal": aro,
                "cognitive_load": load,
            },
            workspace=workspace,
            llm_config=None,
        )
        results.append(
            {
                "label": "Control (Prompt-Only)" if cond == "prompt_only_control" else st.title(),
                "condition": cond,
                "emotionState": res["emotionState"],
                "visualType": res["visualType"],
                "navType": res["navType"],
                "agentTone": res["agentTone"],
                "visibleCount": len(res["matchedItems"]),
                "headline": res["headline"],
                "message": res["message"],
                "hciExplanation": res["hciExplanation"],
            }
        )
    return results
