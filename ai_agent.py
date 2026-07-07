# -*- coding: utf-8 -*-
"""
FitPulse — AI Agent Module
Integrates IBM watsonx.ai (Granite models) with a fully customizable
AGENT_INSTRUCTIONS block so you can tune the coach without touching
any routing or business logic code.
"""

import os
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

# ============================================================
#  AGENT INSTRUCTIONS  ← Customize everything here
# ============================================================
AGENT_INSTRUCTIONS = {
    # --- Identity & Personality ---
    "name": "FitBot",
    "persona": (
        "You are FitBot, a friendly, motivating, and knowledgeable AI fitness coach "
        "powered by IBM Granite. You combine the expertise of a certified personal trainer, "
        "sports nutritionist, and wellness coach into one supportive companion."
    ),

    # --- Tone & Communication Style ---
    "tone": (
        "Warm, encouraging, and professional. Use simple language that everyone understands. "
        "Celebrate every small win. Never shame or demotivate. Be concise yet thorough."
    ),

    # --- Fitness Specialization ---
    "specialization": (
        "Expert in: weight loss, muscle gain, strength training, HIIT, yoga, flexibility, "
        "endurance, home workouts, and rehabilitation. Adapt all advice to the user's fitness "
        "level (beginner / intermediate / advanced)."
    ),

    # --- Safety Guidelines ---
    "safety": (
        "ALWAYS recommend consulting a doctor before starting any new exercise or diet program, "
        "especially for users with medical conditions, pregnancy, or injuries. "
        "Never diagnose medical conditions. Remind users to listen to their body and rest when needed. "
        "For emergency symptoms (chest pain, dizziness, severe pain), instruct them to seek "
        "immediate medical attention."
    ),

    # --- Motivation Style ---
    "motivation": (
        "Use positive reinforcement. Acknowledge effort over results. "
        "Share short motivational quotes when relevant. "
        "Break big goals into small, achievable milestones to build momentum."
    ),

    # --- Workout Intensity Guidance ---
    "intensity": {
        "beginner":     "Low impact, 3 days/week, focus on form and consistency.",
        "intermediate": "Moderate intensity, 4–5 days/week, progressive overload.",
        "advanced":     "High intensity, 5–6 days/week, periodization and recovery focus.",
    },

    # --- Indian Diet Preferences ---
    "indian_diet": (
        "Prioritize Indian dietary preferences when relevant: dals, sabzis, roti, rice, "
        "paneer, curd, sprouts, poha, idli, dosa, and seasonal vegetables. "
        "Suggest budget-friendly Indian meal plans. Respect vegetarian, vegan, Jain, and "
        "regional preferences (North/South/East/West Indian cuisine). "
        "Incorporate superfoods like turmeric, amla, moringa, and flaxseeds."
    ),

    # --- International Diet Support ---
    "international_diet": (
        "Also support Mediterranean, keto, paleo, vegan, and high-protein international diets. "
        "Provide macro breakdowns and easy recipes."
    ),

    # --- Response Format ---
    "format_instructions": (
        "Structure your responses clearly using:\n"
        "• Numbered steps for workout routines\n"
        "• Bullet points for nutrition tips\n"
        "• Tables (in Markdown) for meal plans or macro comparisons\n"
        "• Bold headings for sections\n"
        "Keep responses under 600 words unless a detailed plan is explicitly requested."
    ),

    # --- Prohibited Topics ---
    "prohibited": (
        "Do not discuss: illegal supplements, extreme crash diets (<1000 kcal/day without "
        "medical supervision), steroid use, or any content unrelated to fitness, nutrition, "
        "wellness, or mental health related to fitness."
    ),
}
# ============================================================
#  END AGENT INSTRUCTIONS
# ============================================================


def _build_system_prompt(user_profile: dict | None = None) -> str:
    """Assemble the full system prompt from AGENT_INSTRUCTIONS + user profile."""
    ai = AGENT_INSTRUCTIONS
    profile_ctx = ""
    if user_profile:
        profile_ctx = (
            f"\n\n## Current User Profile\n"
            f"- Name: {user_profile.get('name', 'User')}\n"
            f"- Age: {user_profile.get('age', 'N/A')}\n"
            f"- Gender: {user_profile.get('gender', 'N/A')}\n"
            f"- Height: {user_profile.get('height', 'N/A')} cm\n"
            f"- Weight: {user_profile.get('weight', 'N/A')} kg\n"
            f"- BMI: {user_profile.get('bmi', 'N/A')}\n"
            f"- Fitness Goal: {user_profile.get('fitness_goal', 'General fitness')}\n"
            f"- Activity Level: {user_profile.get('activity_level', 'Moderate')}\n"
            f"- Diet Preference: {user_profile.get('diet_preference', 'No preference')}\n"
            f"- Available Equipment: {user_profile.get('equipment', 'None')}\n"
            f"- Workout Duration: {user_profile.get('workout_duration', '30')} minutes\n"
            f"- Medical Notes: {user_profile.get('medical_notes', 'None')}\n"
        )

    system_prompt = (
        f"## Identity\n{ai['name']} — {ai['persona']}\n\n"
        f"## Tone\n{ai['tone']}\n\n"
        f"## Specialization\n{ai['specialization']}\n\n"
        f"## Safety\n{ai['safety']}\n\n"
        f"## Motivation\n{ai['motivation']}\n\n"
        f"## Workout Intensity Levels\n"
        f"- Beginner: {ai['intensity']['beginner']}\n"
        f"- Intermediate: {ai['intensity']['intermediate']}\n"
        f"- Advanced: {ai['intensity']['advanced']}\n\n"
        f"## Indian Diet Guidance\n{ai['indian_diet']}\n\n"
        f"## International Diets\n{ai['international_diet']}\n\n"
        f"## Response Format\n{ai['format_instructions']}\n\n"
        f"## Prohibited Topics\n{ai['prohibited']}"
        f"{profile_ctx}"
    )
    return system_prompt


# Models that support the /text/chat endpoint
_CHAT_CAPABLE_MODELS = {
    "meta-llama/llama-3-3-70b-instruct",
    "meta-llama/llama-3-1-70b-instruct",
    "meta-llama/llama-3-1-8b-instruct",
    "meta-llama/llama-3-1-8b",
    "ibm/granite-3-8b-instruct",
    "ibm/granite-13b-chat-v2",
}


class FitPulseAgent:
    """Wrapper around IBM watsonx.ai ModelInference for FitPulse.

    Credentials are read lazily via properties so that load_dotenv() in
    app.py always wins regardless of module import order.
    """

    def __init__(self):
        # Do NOT call os.getenv here — .env may not be loaded yet at import time.
        self._client = None
        self._model  = None
        self._cached_model_id = None  # track when model_id changes

    # ── Lazy credential properties ────────────────────────────
    @property
    def api_key(self) -> str:
        return os.getenv("WATSONX_API_KEY", "").strip()

    @property
    def project_id(self) -> str:
        return os.getenv("WATSONX_PROJECT_ID", "").strip()

    @property
    def url(self) -> str:
        return os.getenv("WATSONX_URL", "https://au-syd.ml.cloud.ibm.com").rstrip("/")

    @property
    def model_id(self) -> str:
        return os.getenv("WATSONX_MODEL_ID", "meta-llama/llama-3-3-70b-instruct").strip()

    @property
    def _supports_chat(self) -> bool:
        """True if the configured model supports the /text/chat endpoint."""
        return self.model_id in _CHAT_CAPABLE_MODELS

    def _get_model(self) -> ModelInference:
        # Rebuild if model_id changed or not yet created
        if self._model is None or self._cached_model_id != self.model_id:
            credentials = Credentials(
                url=self.url,
                api_key=self.api_key,
            )
            self._client = APIClient(credentials=credentials)
            self._model = ModelInference(
                model_id=self.model_id,
                credentials=credentials,
                project_id=self.project_id,
            )
            self._cached_model_id = self.model_id
        return self._model

    # ----------------------------------------------------------
    def chat(
        self,
        user_message: str,
        conversation_history: list[dict],
        user_profile: dict | None = None,
    ) -> str:
        """
        Send a chat message and return the AI response text.
        Automatically uses .chat() for instruct models or .generate()
        for base/completion models.

        conversation_history: list of {"role": "user"|"assistant", "content": str}
        """
        if not self.api_key or not self.project_id:
            return self._fallback_response(user_message)

        try:
            model = self._get_model()
            system_prompt = _build_system_prompt(user_profile)
            max_history = int(os.getenv("MAX_CHAT_HISTORY", 20))

            if self._supports_chat:
                # ── Chat API (instruct / instruction-tuned models) ──
                messages = [{"role": "system", "content": system_prompt}]
                for msg in conversation_history[-max_history:]:
                    messages.append({"role": msg["role"], "content": msg["content"]})
                messages.append({"role": "user", "content": user_message})

                response = model.chat(
                    messages=messages,
                    params={"max_tokens": 1024, "temperature": 0.7},
                )
                if isinstance(response, dict):
                    return (
                        response.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                if hasattr(response, "choices") and response.choices:
                    return response.choices[0].message.content.strip()
                return str(response).strip()

            else:
                # ── Generate API (base / completion models) ──
                # Build a structured prompt string
                history_text = ""
                for msg in conversation_history[-max_history:]:
                    role = "User" if msg["role"] == "user" else "FitBot"
                    history_text += f"\n{role}: {msg['content']}"

                prompt = (
                    f"<|system|>\n{system_prompt}\n<|end|>\n"
                    f"{history_text}\n"
                    f"<|user|>\n{user_message}\n<|end|>\n"
                    f"<|assistant|>\n"
                )
                from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GP
                response = model.generate_text(
                    prompt=prompt,
                    params={
                        GP.MAX_NEW_TOKENS:       1024,
                        GP.TEMPERATURE:          0.7,
                        GP.TOP_P:                0.9,
                        GP.REPETITION_PENALTY:   1.1,
                        GP.STOP_SEQUENCES:       ["<|user|>", "<|end|>", "User:"],
                    },
                )
                return str(response).strip()

        except Exception as exc:  # noqa: BLE001
            return (
                "I'm having trouble connecting to my AI brain right now. "
                f"Please check your API configuration.\n\nError: {exc}"
            )

    # ----------------------------------------------------------
    def generate_workout_plan(self, profile: dict) -> str:
        """Generate a structured workout plan for the given profile."""
        prompt = (
            f"Create a detailed 7-day workout plan for:\n"
            f"- Goal: {profile.get('fitness_goal', 'general fitness')}\n"
            f"- Level: {profile.get('fitness_level', 'beginner')}\n"
            f"- Age: {profile.get('age', 25)}, Gender: {profile.get('gender', 'unspecified')}\n"
            f"- Available time: {profile.get('workout_duration', 30)} minutes/day\n"
            f"- Equipment: {profile.get('equipment', 'none')}\n"
            f"Include warm-up, main workout, cool-down, sets, reps, rest periods, "
            f"and recovery tips. Format each day clearly."
        )
        return self.chat(prompt, [], profile)

    # ----------------------------------------------------------
    def generate_meal_plan(self, profile: dict) -> str:
        """Generate a personalized weekly meal plan."""
        prompt = (
            f"Create a detailed 7-day meal plan for:\n"
            f"- Goal: {profile.get('fitness_goal', 'general health')}\n"
            f"- Daily calories: {profile.get('daily_calories', 2000)} kcal\n"
            f"- Diet preference: {profile.get('diet_preference', 'vegetarian')}\n"
            f"- Weight: {profile.get('weight', 70)} kg\n"
            f"Include breakfast, lunch, dinner, and 2 snacks per day. "
            f"Show macros (protein/carbs/fat) for each day. "
            f"Prefer Indian meals with international alternatives. "
            f"Include hydration tips and a grocery list."
        )
        return self.chat(prompt, [], profile)

    # ----------------------------------------------------------
    def get_nutrition_advice(self, query: str, profile: dict) -> str:
        """Answer a specific nutrition question."""
        return self.chat(query, [], profile)

    # ----------------------------------------------------------
    @staticmethod
    def _fallback_response(message: str) -> str:
        """Return a helpful offline response when API is not configured."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["workout", "exercise", "training"]):
            return (
                "🏋️ **Quick Workout Tip**\n\n"
                "Configure your IBM watsonx.ai API key in the `.env` file to get "
                "personalized AI-powered workout plans!\n\n"
                "**Meanwhile, try this beginner routine:**\n"
                "1. 10 push-ups\n2. 20 squats\n3. 30-sec plank\n"
                "4. 10 lunges each leg\n5. 15 glute bridges\n\n"
                "Repeat 3 rounds with 1-min rest between rounds. 💪"
            )
        if any(w in msg_lower for w in ["eat", "diet", "nutrition", "food", "meal"]):
            return (
                "🥗 **Quick Nutrition Tip**\n\n"
                "Configure your IBM watsonx.ai API key to get personalized meal plans!\n\n"
                "**General guidelines:**\n"
                "• Eat 5–6 small meals/day\n"
                "• 1g protein per kg body weight\n"
                "• Drink 8+ glasses of water\n"
                "• Include leafy greens in every meal\n"
                "• Limit processed foods and sugar 🥦"
            )
        return (
            "👋 **FitBot is almost ready!**\n\n"
            "Please add your `WATSONX_API_KEY` and `WATSONX_PROJECT_ID` "
            "to the `.env` file to unlock full AI-powered fitness coaching.\n\n"
            "See `.env.example` for setup instructions."
        )


# Singleton instance used across the app
agent = FitPulseAgent()
