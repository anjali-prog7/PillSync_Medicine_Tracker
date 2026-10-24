import { useState, useRef, useEffect, useCallback } from "react";
import Navbar from "../components/Navbar";
import api from "../services/api";
import {
  FaRobot,
  FaUser,
  FaPaperPlane,
  FaSpinner,
  FaPills,
  FaHeartbeat,
  FaLightbulb,
  FaExclamationTriangle,
  FaFlask,
  FaCalendarCheck,
  FaClock,
  FaTrash,
  FaSun,
  FaBrain,
} from "react-icons/fa";
import "./AiAssistant.css";

// ──────────────────────────────────────────────
//  LOCAL INTELLIGENT RESPONSES (fallback)
// ──────────────────────────────────────────────
const LOCAL_MEDICINE_INFO = {
  paracetamol: {
    name: "Paracetamol",
    uses: "Relieves mild to moderate pain (headache, toothache, fever). Also used for cold/flu symptoms.",
    dosage: "Adults: 500–1000 mg every 4–6 hours. Max 4000 mg/day. Children: weight-based.",
    warnings: "Overdose causes severe liver damage. Avoid alcohol. Check other meds for paracetamol content.",
    side_effects: "Generally well-tolerated. Rare: rash, allergic reactions. Seek help for jaundice.",
    storage: "Store below 30°C, away from moisture and sunlight.",
    precautions: "Consult doctor if you have liver disease. Don't exceed 10 days for pain, 3 days for fever.",
  },
  dolo: {
    name: "Dolo (Dolo 650)",
    uses: "Fever reduction, body pain, headache relief. Dolo 650 is a strong 650 mg paracetamol tablet.",
    dosage: "Dolo 650: 1 tablet every 6 hours. Max 3 tablets (1950 mg) in 24 hours.",
    warnings: "Liver damage risk with overdose. Avoid alcohol. Don't combine with other paracetamol products.",
    side_effects: "Very safe at recommended doses. Rare: skin reactions, liver issues with chronic use.",
    storage: "Store in a cool dry place below 30°C, protect from light.",
    precautions: "Check expiry. Avoid if you have liver disease. Consult doctor during pregnancy.",
  },
  crocin: {
    name: "Crocin",
    uses: "Relieves headaches, toothaches, menstrual pain. Reduces fever in adults and children.",
    dosage: "Crocin 500: 1–2 tablets every 4–6 hours. Crocin 650: 1 tablet every 6 hours. Max 4000 mg/day.",
    warnings: "Liver toxicity with overdose. Avoid alcohol. Not for severe liver disease.",
    side_effects: "Rare and mild: nausea, vomiting, constipation. Rare: allergic dermatitis.",
    storage: "Store below 30°C in a dry place, protect from light.",
    precautions: "Track all paracetamol products. Consult doctor if symptoms persist.",
  },
  ibuprofen: {
    name: "Ibuprofen",
    uses: "Moderate pain relief, reduces inflammation and swelling, reduces fever. Used for arthritis and muscle strains.",
    dosage: "200–400 mg every 6–8 hours. Max 1200 mg/day OTC. Take with food.",
    warnings: "Heart attack/stroke risk with long-term use. Stomach bleeding risk. Avoid in last 3 months of pregnancy.",
    side_effects: "Common: heartburn, nausea. Serious: stomach bleeding, allergic reaction, kidney damage.",
    storage: "Store at room temperature, protect from moisture and heat.",
    precautions: "Avoid with other NSAIDs. Stay hydrated. Consult doctor if you have heart/kidney disease.",
  },
  amoxicillin: {
    name: "Amoxicillin",
    uses: "Treats bacterial infections — ear infections, sinusitis, bronchitis, pneumonia, UTIs, strep throat.",
    dosage: "250–500 mg three times daily (every 8 hours) or 875 mg twice daily. Complete full course.",
    warnings: "Only for bacterial infections. May cause allergic reactions. Frequent use leads to resistance.",
    side_effects: "Common: diarrhea, nausea, rash. Serious: severe allergic reaction, C. difficile diarrhea.",
    storage: "Store below 30°C. Liquid form may need refrigeration — check label.",
    precautions: "Inform doctor of penicillin allergy. May reduce birth control effectiveness. Take probiotics.",
  },
  metformin: {
    name: "Metformin",
    uses: "Controls blood sugar in type 2 diabetes. Reduces glucose production by the liver.",
    dosage: "Starting: 500 mg once/twice daily with meals. Maintenance: 1500–2000 mg/day.",
    warnings: "Rare: lactic acidosis (weakness, muscle pain, difficulty breathing). Avoid with severe kidney disease.",
    side_effects: "Common: diarrhea, nausea, bloating (improves over time). Long-term: vitamin B12 deficiency.",
    storage: "Store at room temperature, protect from light and moisture.",
    precautions: "Monitor blood sugar regularly. Get B12 levels checked. Don't skip meals. Carry sugar source.",
  },
};

const LOCAL_HEALTH_TIPS = [
  "🚰 Drink at least 8 glasses (2 liters) of water daily to stay hydrated and support all bodily functions.",
  "🥦 Eat a rainbow — include fruits and vegetables of different colors for a wide range of nutrients.",
  "😴 Aim for 7–9 hours of quality sleep every night for good memory, mood, and immune function.",
  "🚶 Walk for at least 30 minutes daily. Reduces risk of heart disease, diabetes, and many cancers.",
  "🧘 Practice deep breathing or meditation for 10 minutes daily to reduce stress and improve mental clarity.",
  "🛡️ Boost immunity: eat citrus fruits (vitamin C), zinc-rich foods (nuts, seeds), and get enough sleep.",
  "🌞 Get 15–20 minutes of morning sunlight for natural vitamin D — essential for immune function.",
  "🫐 Include probiotic foods like yogurt, kimchi, or kefir for gut health and immunity.",
  "🌿 Reduce stress: practice mindfulness, take short breaks, listen to calming music, or go for a nature walk.",
  "📝 Write down 3 things you are grateful for every day to reframe your mindset and lower stress.",
  "📱 Avoid screens 30–60 minutes before bedtime — blue light disrupts melatonin production.",
  "☕ Avoid caffeine after 2 PM to prevent sleep disruption.",
  "🏃 Start with small fitness goals: 10-minute walks, stretching. Consistency beats intensity.",
  "🍽️ Eat smaller, balanced meals throughout the day for steady energy and blood sugar levels.",
  "🧂 Reduce salt intake to under 5 g (about 1 tsp) per day for healthy blood pressure.",
  "🍬 Cut down on added sugars — check labels in sauces, drinks, and packaged foods.",
];

const QUICK_BUTTONS = [
  { id: "medicine", icon: <FaPills />, label: "Medicine Info", color: "#0D766E" },
  { id: "missed", icon: <FaExclamationTriangle />, label: "Missed Dose", color: "#E67E22" },
  { id: "tips", icon: <FaHeartbeat />, label: "Health Tips", color: "#E74C3C" },
  { id: "sideeffects", icon: <FaFlask />, label: "Side Effects", color: "#8E44AD" },
  { id: "interaction", icon: <FaLightbulb />, label: "Drug Interaction", color: "#2C3E50" },
  { id: "routine", icon: <FaSun />, label: "Daily Routine", color: "#16A085" },
];

const QUICK_PROMPTS = {
  medicine: "Tell me about Paracetamol, its uses, dosage, warnings, and side effects",
  missed: "I missed my medicine dose. What should I do?",
  tips: "Give me some health tips to improve my wellbeing",
  sideeffects: "What are the side effects of Ibuprofen?",
  interaction: "Can I take Paracetamol with Ibuprofen?",
  routine: "When is the best time to take my medications?",
};

// ──────────────────────────────────────────────
//  HELPER — get current time string
// ──────────────────────────────────────────────
function getTimeString() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ──────────────────────────────────────────────
//  HELPER — generate local fallback response
// ──────────────────────────────────────────────
function getLocalResponse(message) {
  const msg = message.toLowerCase().trim();

  // Emergency keywords
  if (["emergency", "urgent", "overdose", "ambulance", "911"].some((k) => msg.includes(k))) {
    return (
      "🚨 **EMERGENCY — Seek immediate medical help!** 🚨\n\n" +
      "• Call 911 (or your local emergency number) **NOW**.\n" +
      "• If you suspect an overdose, contact Poison Control immediately.\n" +
      "• Do NOT induce vomiting unless instructed by a professional.\n" +
      "• Keep the medication container handy.\n\n" +
      "For non-life-threatening concerns, consult your doctor as soon as possible."
    );
  }

  // Greetings
  if (/^(hi|hello|hey|good morning|good evening)\b/.test(msg)) {
    const greetings = [
      "Hello! 👋 I'm your PillSync AI Health Assistant. How can I help you with your health today?",
      "Hi there! 😊 Ready to help with medication questions, health tips, or wellness advice. What's on your mind?",
      "Hey! Welcome back. How can I support your health journey today?",
    ];
    return greetings[Math.floor(Math.random() * greetings.length)];
  }

  if (/\b(thanks?|thank you)\b/.test(msg)) {
    return "You're welcome! 😊 Always happy to help. Stay healthy and take your meds on time!";
  }

  if (/\b(bye|goodbye|see you)\b/.test(msg)) {
    return "Goodbye! Take care and stay healthy! 🌟 Don't forget your medications!";
  }

  // Medicine info lookup
  const medicineNames = Object.keys(LOCAL_MEDICINE_INFO);
  for (const key of medicineNames) {
    const info = LOCAL_MEDICINE_INFO[key];
    const keywords = [key, info.name.toLowerCase(), ...(info.name.toLowerCase().split(" "))];
    if (keywords.some((kw) => kw.length > 2 && msg.includes(kw))) {
      return (
        `💊 **${info.name}**\n\n` +
        `📋 **Uses:** ${info.uses}\n\n` +
        `💧 **Dosage:** ${info.dosage}\n\n` +
        `⚠️ **Warnings:** ${info.warnings}\n\n` +
        `🩺 **Side Effects:** ${info.side_effects}\n\n` +
        `📦 **Storage:** ${info.storage}\n\n` +
        `✅ **Precautions:** ${info.precautions}\n\n` +
        `_*This is general information. Always consult your doctor for medical advice._`
      );
    }
  }

  // Side effects query
  if (msg.includes("side effect")) {
    return (
      "🩺 **Common side effects to watch for:**\n\n" +
      "• **Paracetamol:** Rare — generally very safe at recommended doses.\n" +
      "• **Ibuprofen:** Heartburn, nausea, stomach pain. Serious: stomach bleeding.\n" +
      "• **Amoxicillin:** Diarrhea, nausea, rash. Serious: severe allergic reaction.\n" +
      "• **Metformin:** Diarrhea, nausea, bloating (usually temporary).\n\n" +
      "⚠️ If you experience severe side effects, stop the medication and consult your doctor immediately.\n" +
      "💡 For specific side effects of a medicine, ask: 'Side effects of [medicine name]'"
    );
  }

  // Drug interaction
  if (/\b(with|and|interact|together|combine)\b/.test(msg) &&
      /(medicine|drug|pill|ibuprofen|paracetamol|aspirin|dolo|crocin|vitamin|antibiotic|metformin)/.test(msg)) {
    if (msg.includes("paracetamol") && (msg.includes("ibuprofen") || msg.includes("advil"))) {
      return (
        "💊 **Paracetamol + Ibuprofen**\n\n" +
        "⚠️ **Verdict: Use with caution**\n\n" +
        "They can sometimes be taken together (staggered, 4–6 hours apart) for enhanced pain relief. " +
        "Do NOT take them at the exact same time regularly. Never exceed maximum daily doses. " +
        "Consult your doctor if you have liver or kidney concerns.\n\n" +
        "⚠️ *This is general guidance — consult your healthcare provider.*"
      );
    }
    if ((msg.includes("dolo") || msg.includes("crocin")) && msg.includes("paracetamol")) {
      return (
        "💊 **Combination Warning**\n\n" +
        "🔴 **Verdict: Consult doctor**\n\n" +
        "Dolo and Crocin both contain paracetamol as the active ingredient. Taking them together " +
        "doubles your paracetamol intake, significantly increasing the risk of liver damage.\n\n" +
        "✅ Use only ONE paracetamol-containing product at a time.\n\n" +
        "⚠️ *This is general guidance — consult your healthcare provider.*"
      );
    }
    if (msg.includes("ibuprofen") && msg.includes("aspirin")) {
      return (
        "💊 **Ibuprofen + Aspirin**\n\n" +
        "🔴 **Verdict: Consult doctor**\n\n" +
        "Ibuprofen can reduce the cardioprotective effects of low-dose aspirin. " +
        "Combining them increases the risk of stomach ulcers and gastrointestinal bleeding. " +
        "If you take aspirin for heart protection, consult your doctor before taking ibuprofen.\n\n" +
        "⚠️ *This is general guidance — consult your healthcare provider.*"
      );
    }
    return (
      "🤝 **Drug Interaction Check**\n\n" +
      "I don't have specific interaction data for that combination in my local database. " +
      "⚠️ Always consult your doctor or pharmacist before combining medications.\n\n" +
      "For known interactions, try asking:\n" +
      "• 'Can I take Paracetamol with Ibuprofen?'\n" +
      "• 'Can I take Crocin and Dolo together?'"
    );
  }

  // Missed dose
  if (/\b(miss|forgot|skip|missed|forget)\b/.test(msg) && /(dose|medicine|pill|medication|tablet)/.test(msg)) {
    return (
      "⏰ **Missed a dose? Here's what to do:**\n\n" +
      "1️⃣ Take it as soon as you remember — **IF** it's not almost time for your next dose.\n" +
      "2️⃣ If your next dose is due soon, **skip** the missed dose. Do NOT double up.\n" +
      "3️⃣ Resume your normal schedule.\n\n" +
      "💡 Use PillSync reminders to avoid missing doses in the future!\n" +
      "⚠️ For medications like heart, diabetes, or blood pressure, consult your doctor about what to do."
    );
  }

  // Extra dose / overdose
  if (/\b(extra|double|overdose|too much|excess|two doses)\b/.test(msg)) {
    return (
      "⚠️ **If you have taken an extra dose:**\n\n" +
      "1️⃣ Do NOT panic — but do not wait either.\n" +
      "2️⃣ Contact your local poison control or emergency services immediately.\n" +
      "3️⃣ Have the medication container with you for details.\n" +
      "4️⃣ If you feel unwell (drowsy, confused, vomiting), call an ambulance.\n\n" +
      "📞 US Poison Control: **1-800-222-1222**\n" +
      "📞 India Poison Info: **1800-11-6111**"
    );
  }

  // When to take / timing
  if (/\b(when|best time|time to take|schedule|routine|after food|before food|empty stomach)\b/.test(msg)) {
    if (/\b(after food|with food|full stomach|after meal)\b/.test(msg)) {
      return (
        "🍽️ **Taking medication AFTER food**\n\n" +
        "Medications that should be taken WITH food:\n" +
        "• NSAIDs (ibuprofen, aspirin) — to reduce stomach irritation\n" +
        "• Metformin — to reduce nausea\n" +
        "• Corticosteroids (prednisolone)\n" +
        "• Fat-soluble vitamins (A, D, E, K)\n\n" +
        "Always check your prescription label — some need an empty stomach!"
      );
    }
    if (/\b(before food|empty stomach|before meal)\b/.test(msg)) {
      return (
        "🕐 **Taking medication BEFORE food**\n\n" +
        "Medications typically taken on an empty stomach:\n" +
        "• Thyroid meds (levothyroxine) — 30–60 min before breakfast\n" +
        "• Some antibiotics (amoxicillin, ciprofloxacin)\n" +
        "• Iron supplements\n" +
        "• Some diabetes medications\n\n" +
        "⚠️ If a medication upsets your stomach, your doctor may advise taking it with food instead."
      );
    }
    return (
      "⏰ **Creating a medication schedule**\n\n" +
      "🌅 **Morning (after breakfast):** Meds that cause alertness or need empty stomach.\n" +
      "☀️ **Afternoon (after lunch):** Midday dose for 2–3x daily medications.\n" +
      "🌙 **Night (after dinner):** Meds that cause drowsiness or work overnight (statins).\n\n" +
      "💡 Use PillSync reminders to get personalized alerts for each medication!"
    );
  }

  // Fever / headache
  if (/\b(fever|cold|flu|cough|sore throat|temperature)\b/.test(msg)) {
    return (
      "🤒 **If you have fever or cold symptoms:**\n\n" +
      "1️⃣ **Rest** — your body needs energy to fight infection.\n" +
      "2️⃣ **Hydrate** — drink water, soups, and electrolytes.\n" +
      "3️⃣ **Monitor** — check your temperature regularly.\n" +
      "4️⃣ **Medicate** — paracetamol (Crocin, Dolo) can help reduce fever.\n" +
      "5️⃣ **See a doctor if:** fever > 103°F (39.4°C), lasts > 3 days, or severe symptoms.\n\n" +
      "⚠️ *This is general guidance. For serious symptoms, consult a doctor.*"
    );
  }

  if (/\b(headache|migraine|head ache)\b/.test(msg)) {
    return (
      "🤕 **Headache relief tips:**\n\n" +
      "1️⃣ Rest in a quiet, dark room\n" +
      "2️⃣ Apply a cold or warm compress to your forehead\n" +
      "3️⃣ Stay hydrated — dehydration is a common cause\n" +
      "4️⃣ OTC relief: paracetamol or ibuprofen (pick ONE)\n" +
      "5️⃣ Avoid screens for a while\n\n" +
      "⚠️ See a doctor for: sudden severe headache, headache after injury, or with fever/stiff neck."
    );
  }

  // Health tips
  if (/\b(health|tip|wellness|immunity|stress|sleep|exercise|diet|nutrition|hydration|water|fitness|improve|better)\b/.test(msg)) {
    const count = msg.includes("many") || msg.includes("lots") ? 5 : 3;
    const shuffled = [...LOCAL_HEALTH_TIPS].sort(() => 0.5 - Math.random());
    const tips = shuffled.slice(0, count).join("\n\n");
    return (
      "🌱 **Here are some health tips for you:**\n\n" + tips + "\n\n" +
      "💡 Want more tips on a specific topic? Just ask!"
    );
  }

  // Reminder statistics keyword detection (handled by API call, fallback here)
  if (/\b(stats|statistics|my reminder|reminder stats|adherence|progress)\b/.test(msg)) {
    return (
      "📊 **Reminder Statistics**\n\n" +
      "To view your personalized reminder statistics, please make sure you are logged in and try again.\n\n" +
      "💡 Go to the **Reminders** page to see and manage all your reminders!"
    );
  }

  // Default fallback
  const defaults = [
    "I'm your AI health assistant! I can help with:\n\n" +
    "💊 **Medicine Info** — Ask about any medication\n" +
    "🤝 **Drug Interactions** — Check if two meds are safe together\n" +
    "🩺 **Health Tips** — Diet, exercise, sleep, stress advice\n" +
    "⏰ **Reminder Help** — Dosage timing, missed doses, scheduling\n" +
    "📊 **My Reminders** — View your reminder statistics\n" +
    "🚨 **Emergency Advice** — What to do in urgent situations\n\n" +
    "What would you like to know?",

    "Hi! I'm your health companion. Try asking:\n\n" +
    "• 'What is Paracetamol?'\n" +
    "• 'Can I take ibuprofen with paracetamol?'\n" +
    "• 'Give me health tips'\n" +
    "• 'I missed my dose'\n" +
    "• 'Show my reminder statistics'",
  ];
  return defaults[Math.floor(Math.random() * defaults.length)];
}

// ──────────────────────────────────────────────
//  HELPER — build a chat message object
// ──────────────────────────────────────────────
function createMessage(role, content, timestamp = getTimeString()) {
  return { id: Date.now() + "_" + Math.random(), role, content, timestamp };
}

// ──────────────────────────────────────────────
//  MAIN COMPONENT
// ──────────────────────────────────────────────
function AiAssistant() {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem("pillSync_chat_history");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {
      // corrupted data — ignore
    }
    return [
      createMessage(
        "assistant",
        "Hello! I'm your PillSync AI Health Assistant 🤖\n\n" +
        "I can help you with:\n" +
        "💊 **Medicine Information** — Uses, dosage, side effects, warnings\n" +
        "🤝 **Drug Interactions** — Check if medications are safe together\n" +
        "🩺 **Health Tips** — Diet, exercise, sleep, stress advice\n" +
        "⏰ **Reminder Help** — Missed dose, timing, scheduling\n" +
        "📊 **Reminder Statistics** — View your adherence and stats\n" +
        "🚨 **Emergency Advice** — What to do in urgent situations\n\n" +
        "How can I help you today?"
      ),
    ];
  });

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showQuickButtons, setShowQuickButtons] = useState(true);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // ── Persist chat history ──
  useEffect(() => {
    try {
      localStorage.setItem("pillSync_chat_history", JSON.stringify(messages));
    } catch {
      // storage full — ignore
    }
  }, [messages]);

  // ── Auto scroll ──
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // ── Focus input on mount ──
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // ── Clear chat history ──
  const clearHistory = () => {
    if (window.confirm("Clear entire chat history?")) {
      setMessages([
        createMessage(
          "assistant",
          "Chat history cleared. How can I help you now? 😊"
        ),
      ]);
      localStorage.removeItem("pillSync_chat_history");
    }
  };

  // ── Send message ──
  const sendMessage = async (messageText) => {
    const text = messageText || input;
    if (!text.trim() || loading) return;

    const userMsg = createMessage("user", text.trim());
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setError(null);
    setLoading(true);
    setShowQuickButtons(false);

    try {
      const response = await api.post("assistant/", { message: text.trim() });
      const aiMsg = createMessage("assistant", response.data.response);
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      console.error("AI Assistant error:", err);

      let fallbackMsg;
      let errDetail = "I'm having trouble connecting right now.";

      if (!err.response) {
        // Network error
        errDetail = "It seems the server is offline or unavailable.";
      } else if (err.response.status === 401) {
        errDetail = "Your session may have expired. Try logging in again.";
      } else if (err.response.status >= 500) {
        errDetail = "The server encountered an error. Please try again later.";
      }

      // Generate local fallback response
      const localResponse = getLocalResponse(text.trim());

      fallbackMsg = createMessage(
        "assistant",
        `⚠️ ${errDetail}\n\n---\n\n${localResponse}\n\n_💡 Using local responses — some features may be limited._`
      );

      setMessages((prev) => [...prev, fallbackMsg]);
      setError(
        err.response?.status === 401
          ? "Session expired. Please log in again."
          : "Server offline. Using local responses."
      );
      setTimeout(() => setError(null), 5000);
    } finally {
      setLoading(false);
    }
  };

  // ── Key event ──
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Quick button click ──
  const handleQuickClick = (id) => {
    const prompt = QUICK_PROMPTS[id];
    if (prompt) sendMessage(prompt);
  };

  // ── Suggestion chip click ──
  const handleSuggestionClick = (suggestion) => {
    sendMessage(suggestion);
  };

  // ── Render message content (support bold, line breaks) ──
  const renderContent = (content) => {
    // Support **bold** markdown and convert \n to <br />
    const parts = content.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      return part.split("\n").map((line, j) => (
        <span key={`${i}_${j}`}>
          {j > 0 && <br />}
          {line}
        </span>
      ));
    });
  };

  // ── Suggestion chips (shown initially) ──
  const suggestions = [
    "What is Paracetamol?",
    "Can I take Crocin and Dolo together?",
    "Give me health tips",
    "What if I miss a dose?",
    "Side effects of Ibuprofen",
    "Show my reminder statistics",
  ];

  return (
    <>
      <Navbar />
      <div className="ai-assistant-page">
        {/* ── Header ── */}
        <div className="ai-header">
          <div className="ai-header-content">
            <div className="ai-header-icon">
              <FaRobot />
            </div>
            <div>
              <h1>AI Health Assistant</h1>
              <p>Your intelligent health companion — medicine info, tips, and reminders</p>
            </div>
          </div>
          <div className="ai-header-actions">
            <button className="clear-history-btn" onClick={clearHistory} title="Clear chat history">
              <FaTrash />
            </button>
            <div className="ai-status">
              <span className="status-dot"></span>
              Online
            </div>
          </div>
        </div>

        {/* ── Quick Action Buttons ── */}
        {showQuickButtons && (
          <div className="quick-buttons-bar">
            {QUICK_BUTTONS.map((btn) => (
              <button
                key={btn.id}
                className="quick-btn"
                style={{ "--btn-color": btn.color }}
                onClick={() => handleQuickClick(btn.id)}
                disabled={loading}
              >
                <span className="quick-btn-icon">{btn.icon}</span>
                <span className="quick-btn-label">{btn.label}</span>
              </button>
            ))}
          </div>
        )}

        {/* ── Feature Chips ── */}
        <div className="ai-features-bar">
          <div className="ai-feature-chip">
            <FaBrain /> Health Advice
          </div>
          <div className="ai-feature-chip">
            <FaPills /> Medication Info
          </div>
          <div className="ai-feature-chip">
            <FaHeartbeat /> Wellness Tips
          </div>
          <div className="ai-feature-chip">
            <FaCalendarCheck /> Reminder Stats
          </div>
        </div>

        {/* ── Error Banner ── */}
        {error && (
          <div className="error-banner">
            <FaExclamationTriangle />
            <span>{error}</span>
          </div>
        )}

        {/* ── Chat Container ── */}
        <div className="chat-container">
          <div className="chat-messages" id="chat-messages">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`chat-message ${
                  msg.role === "user" ? "user-message" : "assistant-message"
                }`}
              >
                <div className="message-avatar">
                  {msg.role === "user" ? (
                    <div className="user-avatar">
                      <FaUser />
                    </div>
                  ) : (
                    <div className="assistant-avatar">
                      <FaRobot />
                    </div>
                  )}
                </div>
                <div className="message-content">
                  <div className="message-header">
                    <span className="message-sender">
                      {msg.role === "user" ? "You" : "PillSync AI"}
                    </span>
                    <span className="message-time">
                      <FaClock className="time-icon" />
                      {msg.timestamp}
                    </span>
                  </div>
                  <div className="message-bubble">
                    {renderContent(msg.content)}
                  </div>
                </div>
              </div>
            ))}

            {/* Typing Indicator */}
            {loading && (
              <div className="chat-message assistant-message">
                <div className="message-avatar">
                  <div className="assistant-avatar">
                    <FaRobot />
                  </div>
                </div>
                <div className="message-content">
                  <div className="message-header">
                    <span className="message-sender">PillSync AI</span>
                    <span className="message-time">
                      <FaClock className="time-icon" />
                      {getTimeString()}
                    </span>
                  </div>
                  <div className="message-bubble typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* ── Suggestion Chips ── */}
          <div className="chat-suggestions">
            <FaBrain className="suggestions-icon" />
            <div className="suggestions-list">
              {suggestions.map((suggestion, index) => (
                <button
                  key={index}
                  className="suggestion-chip"
                  onClick={() => handleSuggestionClick(suggestion)}
                  disabled={loading}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>

          {/* ── Input Bar ── */}
          <div className="chat-input-bar">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything about your health, medicines, or reminders..."
              disabled={loading}
              className="chat-input"
            />
            <button
              className="send-btn"
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              title="Send message"
            >
              {loading ? <FaSpinner className="spin-icon" /> : <FaPaperPlane />}
            </button>
          </div>
        </div>

        {/* ── Footer info ── */}
        <div className="ai-footer">
          <p>
            <FaRobot /> PillSync AI Assistant — Your health companion. Responses are for informational
            purposes only and do not constitute medical advice. Always consult a healthcare professional.
          </p>
        </div>
      </div>
    </>
  );
}

export default AiAssistant;
