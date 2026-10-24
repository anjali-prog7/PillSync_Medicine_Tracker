import os
import random
import re

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reminders.models import Reminder


# ──────────────────────────────────────────────
#  1.  MEDICINE DATABASE
# ──────────────────────────────────────────────
MEDICINE_INFO = {
    "paracetamol": {
        "aliases": ["acetaminophen", "tylenol", "crocin", "calpol", "pcm"],
        "uses": [
            "Relieves mild to moderate pain (headache, toothache, menstrual cramps)",
            "Reduces fever (antipyretic)",
            "Commonly used for cold and flu symptoms",
        ],
        "dosage": [
            "Adults: 500 mg to 1000 mg every 4–6 hours as needed",
            "Maximum: 4000 mg (4 g) per day for adults",
            "Children: Dosage is weight-based — consult packaging or doctor",
            "Do not exceed 10 days of use for pain or 3 days for fever unless directed by a doctor",
        ],
        "warnings": [
            "Do NOT take more than the recommended dose — overdose can cause severe liver damage",
            "Avoid alcohol while taking paracetamol",
            "Consult a doctor if you have pre-existing liver disease",
            "Check other medications — many cold/flu products also contain paracetamol",
        ],
        "side_effects": [
            "Generally well-tolerated with few side effects at recommended doses",
            "Rare: allergic reactions — rash, swelling, difficulty breathing",
            "Very rare: blood disorders (thrombocytopenia, leukopenia)",
            "Seek immediate medical help if you experience yellowing of skin/eyes (jaundice)",
        ],
        "storage": [
            "Store at room temperature (below 30°C / 86°F)",
            "Keep away from moisture and direct sunlight",
            "Keep out of reach of children",
        ],
        "precautions": [
            "Do not take on an empty stomach if you experience nausea",
            "Inform your doctor about all medications you are taking",
            "Pregnant / breastfeeding women should consult a doctor before use",
        ],
    },
    "dolo": {
        "aliases": ["dolo 650", "dolo 500", "paracetamol"],
        "uses": [
            "Effective for fever reduction (commonly used in India)",
            "Relieves mild to moderate body pain and headaches",
            "Helps manage pain associated with cold, flu, and viral infections",
            "Dolo 650 is a 650 mg paracetamol tablet for stronger fever/pain relief",
        ],
        "dosage": [
            "Dolo 650: 1 tablet (650 mg) every 6 hours as needed",
            "Maximum: 3 tablets (1950 mg) in 24 hours for Dolo 650",
            "Do not use for more than 3 days for fever or 5 days for pain without medical advice",
            "Swallow whole with water — do not crush or chew",
        ],
        "warnings": [
            "Overdose can cause liver failure — strictly adhere to dosing",
            "Do not combine with other paracetamol-containing medicines",
            "Avoid alcohol during use",
            "Reduce dose if you have liver or kidney impairment",
        ],
        "side_effects": [
            "Generally very safe at recommended doses",
            "Rare: allergic skin reactions including Stevens-Johnson syndrome",
            "Chronic use may affect liver function",
        ],
        "storage": [
            "Store in a cool dry place below 30°C",
            "Protect from light and moisture",
            "Keep away from children",
        ],
        "precautions": [
            "Check expiry date before use",
            "Do not take on an empty stomach if you have gastric issues",
            "Consult a doctor before use during pregnancy or breastfeeding",
        ],
    },
    "crocin": {
        "aliases": ["crocin 500", "crocin 650", "paracetamol", "acetaminophen"],
        "uses": [
            "Relieves headaches, toothaches, and menstrual pain",
            "Reduces fever in adults and children",
            "Provides relief from body aches associated with cold and flu",
        ],
        "dosage": [
            "Crocin 500: 1–2 tablets (500–1000 mg) every 4–6 hours",
            "Crocin 650: 1 tablet (650 mg) every 6 hours",
            "Maximum daily: 4000 mg for adults",
            "For children, use Crocin Paediatric drops/syrup as per weight chart",
        ],
        "warnings": [
            "Do not exceed the maximum daily dose — risk of liver toxicity",
            "Not recommended if you have severe liver disease",
            "Avoid alcohol",
        ],
        "side_effects": [
            "Rare and mild when taken as directed",
            "Possible: nausea, vomiting, constipation",
            "Rare: allergic dermatitis, urticaria",
        ],
        "storage": [
            "Store below 30°C in a dry place",
            "Protect from light",
        ],
        "precautions": [
            "Keep a record of all paracetamol-containing products you take",
            "Consult a doctor if symptoms persist beyond the recommended duration",
        ],
    },
    "ibuprofen": {
        "aliases": ["advil", "motrin", "brufen", "nurofen"],
        "uses": [
            "Relieves moderate pain (headache, dental pain, menstrual cramps)",
            "Reduces inflammation and swelling (anti-inflammatory)",
            "Reduces fever (antipyretic)",
            "Used for arthritis, sprains, and muscle strains",
        ],
        "dosage": [
            "Adults: 200–400 mg every 6–8 hours as needed",
            "Maximum: 1200 mg per day (over-the-counter); up to 2400 mg with a doctor's prescription",
            "Take with food or milk to reduce stomach irritation",
            "Do not use for more than 10 days for pain or 3 days for fever without consulting a doctor",
        ],
        "warnings": [
            "Increases risk of heart attack or stroke (especially with long-term use)",
            "Can cause stomach bleeding — risk is higher in elderly, smokers, and alcohol users",
            "Do not take if you have a history of stomach ulcers or bleeding disorders",
            "Avoid in the last 3 months of pregnancy",
            "Can interact with blood thinners (warfarin), aspirin, and certain blood pressure medications",
        ],
        "side_effects": [
            "Common: heartburn, nausea, stomach pain, bloating",
            "Serious: signs of stomach bleeding — bloody vomit, black/tarry stools, abdominal pain",
            "Serious: signs of allergic reaction — hives, facial swelling, asthma-like symptoms",
            "Long-term use may cause kidney damage",
        ],
        "storage": [
            "Store at room temperature (20–25°C)",
            "Protect from moisture and heat",
            "Keep the bottle tightly closed",
        ],
        "precautions": [
            "Avoid using with other NSAIDs (naproxen, diclofenac, aspirin)",
            "Stay hydrated while taking ibuprofen to protect kidneys",
            "Elderly patients should use the lowest effective dose for the shortest duration",
            "Consult a doctor before use if you have high blood pressure, heart disease, or kidney disease",
        ],
    },
    "amoxicillin": {
        "aliases": ["amoxil", "mox", "antibiotic"],
        "uses": [
            "Treats bacterial infections — ear infections, sinusitis, bronchitis, pneumonia",
            "Treats urinary tract infections (UTIs)",
            "Treats strep throat and tonsillitis",
            "Used in combination for H. pylori (stomach ulcer treatment)",
        ],
        "dosage": [
            "Adults: 250–500 mg three times daily (every 8 hours) or 875 mg twice daily",
            "Children: Dosage is weight-based — typically 20–40 mg/kg/day in divided doses",
            "Complete the FULL course even if you feel better — do not stop early",
            "Take at evenly spaced intervals to maintain effective blood levels",
        ],
        "warnings": [
            "Only effective against bacterial infections — does NOT work for viral infections (colds, flu)",
            "Do not share antibiotics or use leftover medication",
            "May cause allergic reactions (especially if allergic to penicillin)",
            "Frequent use can lead to antibiotic resistance",
        ],
        "side_effects": [
            "Common: diarrhea, nausea, vomiting, skin rash",
            "Common: vaginal yeast infection (due to bacterial imbalance)",
            "Serious: severe allergic reaction — difficulty breathing, swelling, hives",
            "Serious: severe diarrhea (C. difficile infection) — may occur weeks after stopping",
        ],
        "storage": [
            "Store at room temperature below 30°C",
            "Keep capsules/tablets in a dry place",
            "Oral suspension (liquid) typically needs refrigeration — check label",
            "Discard unused liquid after the expiry period specified on the bottle",
        ],
        "precautions": [
            "Inform your doctor if you are allergic to penicillin or cephalosporins",
            "Inform your doctor about all other medications you are taking",
            "May reduce the effectiveness of oral contraceptives — use backup birth control",
            "Take probiotics or yogurt to reduce the risk of antibiotic-associated diarrhea",
        ],
    },
    "metformin": {
        "aliases": ["glucophage", "glyciphage", "diabetic medicine"],
        "uses": [
            "Controls high blood sugar in type 2 diabetes mellitus",
            "Helps improve insulin sensitivity",
            "Reduces glucose production by the liver",
            "May be used alone or in combination with other diabetic medications",
        ],
        "dosage": [
            "Starting dose: 500 mg once or twice daily with meals",
            "Maintenance dose: 1500–2000 mg per day in divided doses",
            "Maximum: 2550 mg per day",
            "Take with food to minimize stomach upset",
            "Tablets should be swallowed whole — do not crush or chew extended-release forms",
        ],
        "warnings": [
            "Rare but serious: Lactic acidosis — symptoms include weakness, muscle pain, difficulty breathing, drowsiness",
            "Discontinue temporarily before surgery or iodinated contrast imaging procedures",
            "Not for use in severe kidney or liver disease",
            "Avoid excessive alcohol consumption — increases risk of lactic acidosis",
        ],
        "side_effects": [
            "Very common: diarrhea, nausea, vomiting, bloating, gas (especially when starting)",
            "These often improve over time — take with food to reduce them",
            "May cause metallic taste in the mouth",
            "Long-term use may lead to vitamin B12 deficiency",
        ],
        "storage": [
            "Store at room temperature (20–25°C)",
            "Protect from light and moisture",
            "Keep away from children",
        ],
        "precautions": [
            "Monitor blood sugar regularly as directed by your doctor",
            "Get periodic vitamin B12 levels checked",
            "Do not skip meals while on this medication",
            "Carry a source of sugar (glucose tablets, candy) for hypoglycemia emergencies",
            "Consult your doctor before changing the dose",
        ],
    },
}


# ──────────────────────────────────────────────
#  2.  DRUG INTERACTION DATABASE
# ──────────────────────────────────────────────
DRUG_INTERACTIONS = {
    ("paracetamol", "ibuprofen"): {
        "verdict": "Use with caution",
        "detail": (
            "Paracetamol and ibuprofen work differently and can sometimes be "
            "taken together (staggered) for enhanced pain relief. However, they "
            "should NOT be taken at the exact same time regularly. Maintain a "
            "gap of at least 4–6 hours between them. Never exceed the maximum "
            "daily dose of either medication, and consult your doctor if you "
            "have liver or kidney concerns."
        ),
    },
    ("paracetamol", "dolo"): {
        "verdict": "Consult doctor",
        "detail": (
            "Dolo is a brand of paracetamol. Taking paracetamol with Dolo "
            "means you are doubling up on the same active ingredient, which "
            "increases the risk of liver damage. Do NOT take them together. "
            "Use only one paracetamol-containing product at a time."
        ),
    },
    ("crocin", "dolo"): {
        "verdict": "Consult doctor",
        "detail": (
            "Crocin and Dolo both contain paracetamol as the active ingredient. "
            "Taking them together will result in a double dose, significantly "
            "increasing the risk of liver toxicity. Choose ONE paracetamol "
            "product and stick to the recommended dosage."
        ),
    },
    ("ibuprofen", "aspirin"): {
        "verdict": "Consult doctor",
        "detail": (
            "Ibuprofen can reduce the cardioprotective effects of low-dose "
            "aspirin. Combining them also increases the risk of stomach ulcers "
            "and gastrointestinal bleeding. If you take aspirin regularly for "
            "heart protection, consult your doctor before taking ibuprofen."
        ),
    },
    ("vitamin c", "antibiotics"): {
        "verdict": "Safe",
        "detail": (
            "Vitamin C is generally safe to take with most antibiotics. In "
            "fact, vitamin C can support the immune system during an infection. "
            "However, take them at least 2 hours apart to avoid any potential "
            "interference with absorption. Always follow your doctor's specific "
            "instructions regarding antibiotics."
        ),
    },
    ("metformin", "alcohol"): {
        "verdict": "Use with caution",
        "detail": (
            "Alcohol can increase the risk of metformin-associated lactic "
            "acidosis, a rare but serious side effect. It also affects blood "
            "sugar levels. Limit alcohol intake, avoid binge drinking, and "
            "never drink on an empty stomach while taking metformin."
        ),
    },
    ("ibuprofen", "warfarin"): {
        "verdict": "Consult doctor",
        "detail": (
            "Ibuprofen can increase the anticoagulant (blood-thinning) effect "
            "of warfarin, raising the risk of serious bleeding. This combination "
            "should generally be avoided. If you take warfarin, consult your "
            "doctor for a safer pain relief alternative such as paracetamol."
        ),
    },
}


# ──────────────────────────────────────────────
#  3.  HEALTH TIPS DATABASE
# ──────────────────────────────────────────────
HEALTH_TIPS = [
    # General
    "🚰 Drink at least 8 glasses (2 liters) of water daily to stay hydrated and support all bodily functions.",
    "🥦 Eat a rainbow — include fruits and vegetables of different colors in your meals for a wide range of nutrients.",
    "😴 Aim for 7–9 hours of quality sleep every night. Good sleep improves memory, mood, and immune function.",
    "🚶 Walk for at least 30 minutes a day. Regular physical activity reduces the risk of heart disease, diabetes, and many cancers.",
    "🧘 Practice deep breathing or meditation for 10 minutes daily to reduce stress and improve mental clarity.",
    # Immunity
    "🛡️ Boost your immune system: eat citrus fruits (vitamin C), zinc-rich foods (nuts, seeds), and get enough sleep.",
    "🌞 Get 15–20 minutes of morning sunlight for natural vitamin D — essential for immune function and bone health.",
    "🫐 Include probiotic foods like yogurt, kimchi, or kefir in your diet to support gut health and immunity.",
    # Stress
    "🌿 To reduce stress: practice mindfulness, take short breaks during work, listen to calming music, or go for a nature walk.",
    "📝 Write down 3 things you are grateful for every day — it can reframe your mindset and lower stress.",
    # Sleep
    "📱 Avoid screens (phone, TV, laptop) 30–60 minutes before bedtime — blue light disrupts melatonin production.",
    "🛏️ Keep your bedroom cool, dark, and quiet for optimal sleep quality.",
    "☕ Avoid caffeine after 2 PM to prevent sleep disruption.",
    # Exercise
    "🏃 Start with small fitness goals: 10-minute walks, stretching, or bodyweight exercises. Consistency beats intensity.",
    "🧘 Stretch for 5–10 minutes after waking up to improve circulation and reduce morning stiffness.",
    "🤸 Try a mix of cardio (walking, jogging), strength (bodyweight exercises), and flexibility (yoga, stretching) training.",
    # Diet / Hydration
    "🍽️ Eat smaller, balanced meals throughout the day to maintain steady energy levels and blood sugar.",
    "🧂 Reduce salt intake to under 5 g (about 1 teaspoon) per day to maintain healthy blood pressure.",
    "🍬 Cut down on added sugars — check labels for hidden sugars in sauces, drinks, and packaged foods.",
    "🍵 Herbal teas (ginger, chamomile, green tea) offer antioxidants and can aid digestion and relaxation.",
]

# ──────────────────────────────────────────────
#  4.  REMINDER / DOSAGE GUIDANCE
# ──────────────────────────────────────────────
REMINDER_GUIDANCE = {
    "miss": {
        "keywords": ["miss", "forgot", "skip", "forget", "skipped"],
        "response": (
            "If you miss a dose:\n"
            "1️⃣ Take it as soon as you remember — IF it is not almost time for your next dose.\n"
            "2️⃣ If your next dose is due soon, skip the missed dose. Do NOT double up.\n"
            "3️⃣ Resume your normal schedule.\n\n"
            "If you frequently forget doses, try setting alarms or using the PillSync app's reminder feature. "
            "For critical medications (heart, diabetes, blood pressure), consult your doctor about what to do if you miss a dose."
        ),
    },
    "overdose": {
        "keywords": ["extra", "overdose", "too much", "double", "excess", "over"],
        "response": (
            "⚠️ If you have taken more than the recommended dose:\n\n"
            "1️⃣ Do NOT panic — but do not wait either.\n"
            "2️⃣ Contact your local poison control center or emergency services immediately.\n"
            "3️⃣ Have the medication container with you to provide details.\n"
            "4️⃣ If you feel unwell (drowsy, confused, vomiting, difficulty breathing), call an ambulance right away.\n\n"
            "💡 In the US, call Poison Control: 1-800-222-1222.\n"
            "💡 In India, call the National Poison Information Centre: 1800-11-6111."
        ),
    },
    "with_food": {
        "keywords": ["with food", "after food", "with meal", "full stomach"],
        "response": (
            "🕐 General rule: Take medications AFTER food unless otherwise instructed.\n\n"
            "Some medications that should be taken WITH food:\n"
            "• NSAIDs (ibuprofen, aspirin, diclofenac) — to reduce stomach irritation\n"
            "• Metformin — to reduce nausea\n"
            "• Prednisolone / corticosteroids\n"
            "• Fat-soluble vitamins (A, D, E, K)\n\n"
            "Always check your prescription label — some medications require an empty stomach for better absorption."
        ),
    },
    "before_food": {
        "keywords": ["before food", "empty stomach", "before meal"],
        "response": (
            "🕐 Some medications work best on an empty stomach (1 hour before or 2 hours after a meal).\n\n"
            "Medications typically taken BEFORE food:\n"
            "• Thyroid medications (levothyroxine) — take 30–60 minutes before breakfast\n"
            "• Some antibiotics (amoxicillin, ciprofloxacin) — check label\n"
            "• Iron supplements — better absorbed on an empty stomach\n"
            "• Diabetes medications (some sulfonylureas) — take 30 minutes before meals\n\n"
            "⚠️ If a medication causes stomach upset, your doctor may advise taking it with food instead."
        ),
    },
    "best_time": {
        "keywords": ["when", "best time", "time to take", "schedule", "routine"],
        "response": (
            "⏰ Creating a medication schedule:\n\n"
            "🌅 Morning (after breakfast): Take medications that can cause alertness or need to be taken on an empty stomach.\n"
            "☀️ Afternoon (after lunch): Midday dose for medications taken 2–3 times daily.\n"
            "🌙 Night (after dinner): Take medications that cause drowsiness or that work better overnight (e.g., statins).\n\n"
            "💡 Use PillSync to set personalized reminders for each medication at the correct time!"
        ),
    },
}


# ──────────────────────────────────────────────
#  5.  QUICK STATIC RESPONSES
# ──────────────────────────────────────────────
STATIC_RESPONSES = {
    "hello": [
        "Hello! 👋 I'm your PillSync AI Health Assistant. How can I help you with your health today?",
        "Hi there! 😊 Ready to help with medication questions, health tips, or wellness advice. What's on your mind?",
        "Hey! Welcome back. How can I support your health journey today?",
    ],
    "thanks": [
        "You're welcome! 😊 Always happy to help. Stay healthy!",
        "Glad I could help! 💚 Don't forget to take your medications on time.",
        "Anytime! 🙌 Take care of yourself!",
    ],
    "bye": [
        "Goodbye! Take care and stay healthy! 🌟",
        "See you later! Don't forget your medications! 💊",
        "Bye for now! Wishing you good health! 😊",
    ],
    "default": [
        "I'm your AI health assistant! I can help with:\n\n"
        "💊 **Medicine Info** — Ask about any medication\n"
        "🤝 **Drug Interactions** — Check if two meds are safe together\n"
        "🩺 **Health Tips** — Diet, exercise, sleep, stress advice\n"
        "⏰ **Reminder Help** — Dosage timing, missed doses, scheduling\n"
        "📊 **My Reminders** — View your reminder statistics\n"
        "🚨 **Emergency Advice** — What to do in urgent situations\n\n"
        "What would you like to know?",
        "Hi! I'm here to support your medication journey. Try asking:\n\n"
        "• 'What is Paracetamol?'\n"
        "• 'Can I take ibuprofen with paracetamol?'\n"
        "• 'Give me health tips'\n"
        "• 'I missed my dose'\n"
        "• 'Show my reminder statistics'",
    ],
}


# ──────────────────────────────────────────────
#  6.  MESSAGE CATEGORIZATION
# ──────────────────────────────────────────────

def _contains_any(text, keywords):
    """Check if any keyword appears in the text."""
    return any(k in text for k in keywords)


def _get_medicine_name(message):
    """Try to extract a medicine name from the user message."""
    message_lower = message.lower()

    # Check direct matches against our database
    for medicine_key in MEDICINE_INFO:
        if medicine_key in message_lower:
            return medicine_key
        # Check aliases
        for alias in MEDICINE_INFO[medicine_key]["aliases"]:
            if alias in message_lower:
                return medicine_key

    # Try extracting first capitalized word that might be a medicine
    words = message_lower.split()
    for word in words:
        word_clean = word.strip(".,?!;:'\"")
        if word_clean in MEDICINE_INFO:
            return word_clean

    return None


def _get_interaction(med1, med2):
    """Check drug interaction between two medicines."""
    # Normalize — check both orderings
    key = (med1, med2)
    reverse_key = (med2, med1)

    if key in DRUG_INTERACTIONS:
        return DRUG_INTERACTIONS[key]
    if reverse_key in DRUG_INTERACTIONS:
        return DRUG_INTERACTIONS[reverse_key]

    # Try alias expansion
    med1_names = [med1]
    med2_names = [med2]
    if med1 in MEDICINE_INFO:
        med1_names = [med1] + MEDICINE_INFO[med1]["aliases"]
    if med2 in MEDICINE_INFO:
        med2_names = [med2] + MEDICINE_INFO[med2]["aliases"]

    for m1 in med1_names:
        for m2 in med2_names:
            if (m1, m2) in DRUG_INTERACTIONS:
                return DRUG_INTERACTIONS[(m1, m2)]
            if (m2, m1) in DRUG_INTERACTIONS:
                return DRUG_INTERACTIONS[(m2, m1)]

    return None


def _format_medicine_info(medicine_key):
    """Format full medicine info as a readable string."""
    info = MEDICINE_INFO[medicine_key]
    name = medicine_key.capitalize()

    lines = [f"💊 **{name}**\n"]

    lines.append("📋 **Uses:**")
    for u in info["uses"]:
        lines.append(f"• {u}")
    lines.append("")

    lines.append("💧 **Dosage:**")
    for d in info["dosage"]:
        lines.append(f"• {d}")
    lines.append("")

    lines.append("⚠️ **Warnings:**")
    for w in info["warnings"]:
        lines.append(f"• {w}")
    lines.append("")

    lines.append("🩺 **Side Effects:**")
    for s in info["side_effects"]:
        lines.append(f"• {s}")
    lines.append("")

    lines.append("📦 **Storage:**")
    for st in info["storage"]:
        lines.append(f"• {st}")
    lines.append("")

    lines.append("✅ **Precautions:**")
    for p in info["precautions"]:
        lines.append(f"• {p}")

    return "\n".join(lines)


def _get_health_tips(limit=3):
    """Return a random selection of health tips."""
    selected = random.sample(HEALTH_TIPS, min(limit, len(HEALTH_TIPS)))
    return "\n\n".join(selected)


def _get_reminder_stats(user):
    """Get reminder statistics for the authenticated user."""
    now = timezone.now()
    today = now.date()

    all_reminders = Reminder.objects.filter(user=user)
    total = all_reminders.count()
    pending = all_reminders.filter(status="PENDING").count()
    taken = all_reminders.filter(status="TAKEN").count()
    missed = all_reminders.filter(status="MISSED").count()

    # Upcoming (today's pending reminders, order by time)
    upcoming = (
        all_reminders
        .filter(reminder_date=today, status="PENDING")
        .order_by("reminder_time")
        .select_related("medicine")
        .first()
    )

    stats = {
        "total": total,
        "pending": pending,
        "taken": taken,
        "missed": missed,
        "upcoming": None,
    }

    if upcoming:
        stats["upcoming"] = {
            "medicine": upcoming.medicine.medicine_name,
            "time": upcoming.reminder_time.strftime("%I:%M %p"),
            "date": upcoming.reminder_date.isoformat(),
        }

    return stats


def _format_reminder_stats(user):
    """Format reminder stats as a readable message."""
    stats = _get_reminder_stats(user)

    if stats["total"] == 0:
        return (
            "📊 **Reminder Statistics**\n\n"
            "You don't have any reminders set up yet.\n\n"
            "💡 Go to the **Reminders** page to create your first reminder!"
        )

    lines = [
        "📊 **Your Reminder Statistics**\n",
        f"📌 **Total Reminders:** {stats['total']}",
        f"⏳ **Pending:** {stats['pending']}",
        f"✅ **Completed:** {stats['taken']}",
        f"❌ **Missed:** {stats['missed']}",
    ]

    if stats["upcoming"]:
        lines.append(
            f"\n🕐 **Upcoming Reminder:**\n"
            f"   💊 {stats['upcoming']['medicine']} at {stats['upcoming']['time']}"
        )
    else:
        lines.append("\n🕐 **No upcoming reminders for today.**")

    # Adherence rate
    if stats["total"] > 0:
        rate = round((stats["taken"] / stats["total"]) * 100)
        lines.append(f"\n📈 **Adherence Rate:** {rate}%")

    return "\n".join(lines)


# ──────────────────────────────────────────────
#  7.  MAIN RESPONSE ENGINE
# ──────────────────────────────────────────────

def get_response(user_message, user=None):
    """
    Generate an intelligent response based on the user's message.
    Uses pattern matching + database lookups — no external API needed.
    """
    msg = user_message.lower().strip()

    # ── Emergency / urgent ──
    emergency_keywords = [
        "emergency", "urgent", "overdose", "poison", "severe",
        "ambulance", "911", "help", "unconscious", "not breathing",
        "heart attack", "stroke", "allergic reaction", "difficulty breathing",
        "chest pain", "choking",
    ]
    if _contains_any(msg, emergency_keywords):
        return (
            "🚨 **EMERGENCY — Seek immediate medical help!** 🚨\n\n"
            "• **Call 911** (or your local emergency number) **NOW** — do not wait.\n"
            "• If you suspect an overdose, contact Poison Control immediately.\n"
            "• Do NOT induce vomiting unless instructed by a medical professional.\n"
            "• Keep the medication container handy for identification.\n\n"
            "For non-life-threatening concerns, please consult your doctor as soon as possible."
        )

    # ── Greetings / thanks / bye ──
    if re.search(r"\b(hi|hello|hey|good morning|good evening)\b", msg):
        return random.choice(STATIC_RESPONSES["hello"])

    if re.search(r"\b(thanks?|thank you|appreciate)\b", msg):
        return random.choice(STATIC_RESPONSES["thanks"])

    if re.search(r"\b(bye|goodbye|see you|cya)\b", msg):
        return random.choice(STATIC_RESPONSES["bye"])

    # ── Reminder statistics ──
    stats_keywords = [
        "statistics", "stats", "my reminders", "reminder stats",
        "show reminders", "view reminders", "reminder status",
        "my statistics", "adherence", "progress",
    ]
    if _contains_any(msg, stats_keywords) and user is not None:
        return _format_reminder_stats(user)

    # ── Drug interaction queries ──
    # First, do a broad message-level scan against ALL interaction keys.
    # This handles multi-word medicines like "Vitamin C" that regex \\w+ cannot capture.
    for (med_a, med_b), interaction_data in DRUG_INTERACTIONS.items():
        if med_a in msg and med_b in msg:
            verdict = interaction_data["verdict"]
            emoji_map = {"Safe": "✅", "Use with caution": "⚠️", "Consult doctor": "🔴"}
            emoji = emoji_map.get(verdict, "❓")
            return (
                f"💊 **{med_a.title()}** + **{med_b.title()}**\n\n"
                f"{emoji} **Verdict:** {verdict}\n\n"
                f"{interaction_data['detail']}\n\n"
                "⚠️ *This is general guidance. Always consult your healthcare provider "
                "for personalized medical advice.*"
            )

    # Fallback: regex-based pattern matching for ad-hoc queries
    interaction_patterns = [
        r"can i take (\w+).+(?:with|and).+(\w+)",
        r"(\w+).+(?:with|and).+(\w+).+(?:interaction|together|safe)",
        r"can i (?:take|use) (\w+).+(\w+)",
        r"(\w+).+(\w+).+(?:interact|combine|compatible)",
    ]
    for pattern in interaction_patterns:
        match = re.search(pattern, msg)
        if match:
            med1 = match.group(1).lower()
            med2 = match.group(2).lower()
            interaction = _get_interaction(med1, med2)
            if interaction:
                verdict = interaction["verdict"]
                emoji_map = {"Safe": "✅", "Use with caution": "⚠️", "Consult doctor": "🔴"}
                emoji = emoji_map.get(verdict, "❓")
                return (
                    f"💊 **{med1.capitalize()}** + **{med2.capitalize()}**\n\n"
                    f"{emoji} **Verdict:** {verdict}\n\n"
                    f"{interaction['detail']}\n\n"
                    "⚠️ *This is general guidance. Always consult your healthcare provider "
                    "for personalized medical advice.*"
                )
            else:
                return (
                    f"I don't have specific interaction data for **{med1.capitalize()}** "
                    f"and **{med2.capitalize()}** in my database. "
                    "⚠️ Please consult your doctor or pharmacist before combining medications."
                )

    # ── Medicine information ──
    # Check if asking about a specific medicine
    medicine_asked = False
    med_query_patterns = [
        r"what is (\w+)",
        r"what are (.+?(?:side effects|uses|dosage))",
        r"tell me about (\w+)",
        r"information (?:on|about) (\w+)",
        r"details (?:on|about) (\w+)",
        r"(\w+) information",
    ]
    for pattern in med_query_patterns:
        match = re.search(pattern, msg)
        if match:
            # Extract potential medicine name
            potential_med = match.group(1).lower()
            # Clean up "side effects of X" pattern
            potential_med = re.sub(r"(side effects|uses|dosage|warnings?)\s+(?:of\s+)?", "", potential_med).strip()
            med_key = _get_medicine_name(potential_med)
            if med_key:
                return _format_medicine_info(med_key)
            elif potential_med not in ["side effects", "uses", "dosage", "warnings", "information", "details"]:
                # Check if it's a "side effects of X" where X is the medicine
                side_effect_match = re.search(r"(?:side effects|uses|dosage|warnings?)\s+(?:of\s+)?(.+)", msg)
                if side_effect_match:
                    med_key2 = _get_medicine_name(side_effect_match.group(1))
                    if med_key2:
                        return _format_medicine_info(med_key2)

    # Also check for "side effects of X" pattern specifically
    side_effect_pattern = r"(?:side effects|uses|dosage|warnings?)\s+(?:of\s+)?(\w+)"
    match = re.search(side_effect_pattern, msg)
    if match:
        med_key = _get_medicine_name(match.group(1))
        if med_key:
            return _format_medicine_info(med_key)

    # Check if message contains a known medicine name directly
    med_key = _get_medicine_name(msg)
    if med_key:
        # If it's a short query, return full info
        word_count = len(msg.split())
        if word_count <= 8:
            return _format_medicine_info(med_key)
        medicine_asked = True

    # ── Reminder / dosage guidance ──
    for guidance_key, guidance_data in REMINDER_GUIDANCE.items():
        if _contains_any(msg, guidance_data["keywords"]):
            return guidance_data["response"]

    # ── Health tips ──
    health_keywords = [
        "health tip", "health advice", "wellness", "healthy lifestyle",
        "immunity", "stress", "sleep", "exercise", "diet", "nutrition",
        "hydration", "water", "fitness", "meditation", "healthy",
        "improve", "better", "beneficial",
    ]
    if _contains_any(msg, health_keywords):
        tip_count = 3
        if "many" in msg or "lots" in msg or "several" in msg:
            tip_count = 5
        return (
            "🌱 **Here are some health tips for you:**\n\n"
            f"{_get_health_tips(tip_count)}\n\n"
            "💡 Want more tips on a specific topic? Just ask!"
        )

    # ── Extra dose / overdose ──
    extra_keywords = ["extra dose", "two doses", "double dose", "took twice", "took two"]
    if _contains_any(msg, extra_keywords):
        return REMINDER_GUIDANCE["overdose"]["response"]

    # ── Fever / headache / general symptoms ──
    fever_keywords = ["fever", "temperature", "cold", "flu", "cough", "sore throat"]
    if _contains_any(msg, fever_keywords):
        return (
            "🤒 **If you have a fever or cold symptoms:**\n\n"
            "1️⃣ **Rest** — your body needs energy to fight the infection.\n"
            "2️⃣ **Hydrate** — drink plenty of water, soups, and electrolytes.\n"
            "3️⃣ **Monitor** — check your temperature regularly.\n"
            "4️⃣ **Medicate if needed** — paracetamol (e.g., Crocin, Dolo) can help reduce fever. "
            "Follow the recommended dosage.\n"
            "5️⃣ **See a doctor if:** fever > 103°F (39.4°C), lasts more than 3 days, "
            "or is accompanied by severe headache, rash, stiff neck, or breathing difficulty.\n\n"
            "⚠️ *This is general guidance. For serious or persistent symptoms, consult a doctor.*"
        )

    headache_keywords = ["headache", "migraine", "head ache"]
    if _contains_any(msg, headache_keywords):
        return (
            "🤕 **Headache relief tips:**\n\n"
            "1️⃣ Rest in a quiet, dark room\n"
            "2️⃣ Apply a cold or warm compress to your forehead\n"
            "3️⃣ Stay hydrated — dehydration is a common cause\n"
            "4️⃣ Over-the-counter pain relief: paracetamol or ibuprofen (take one, not both)\n"
            "5️⃣ Avoid screens for a while\n\n"
            "⚠️ See a doctor if you experience: sudden severe headache, "
            "headache after injury, headache with fever/stiff neck, or persistent vision changes."
        )

    # ── Unable to understand ──
    return random.choice(STATIC_RESPONSES["default"])


# ──────────────────────────────────────────────
#  8.  API VIEW
# ──────────────────────────────────────────────

class AssistantView(APIView):
    """AI Assistant endpoint — responds to user queries with intelligent responses."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()

        if not message:
            return Response(
                {"error": "Message is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Try OpenAI if API key is configured
        openai_api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")

        if openai_api_key:
            try:
                import openai

                client = openai.OpenAI(api_key=openai_api_key)
                completion = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful health and medication assistant for PillSync, "
                                "an intelligent medicine reminder app. Provide concise, accurate health "
                                "information and medication advice. Always remind users to consult "
                                "healthcare professionals for medical decisions."
                            ),
                        },
                        {"role": "user", "content": message},
                    ],
                    max_tokens=500,
                )
                ai_response = completion.choices[0].message.content
                return Response(
                    {"response": ai_response, "user_message": message},
                    status=status.HTTP_200_OK,
                )
            except Exception:
                # Fall through to local responses
                pass

        # Intelligent local rule-based response
        ai_response = get_response(message, user=request.user)

        return Response(
            {"response": ai_response, "user_message": message},
            status=status.HTTP_200_OK,
        )


class ReminderStatsView(APIView):
    """Dedicated endpoint for reminder statistics."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = _get_reminder_stats(request.user)
        return Response(stats, status=status.HTTP_200_OK)
