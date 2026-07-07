# -*- coding: utf-8 -*-
"""
FitPulse -- AI Agent Module
Integrates IBM watsonx.ai (Granite / LLaMA models) with a fully customizable
AGENT_INSTRUCTIONS block so you can tune the coach without touching
any routing or business logic code.

If WATSONX_API_KEY is not set or authentication fails, the agent
automatically falls back to a rich built-in fitness knowledge engine
so the app is always fully functional.
"""

import os
import re

# ── optional IBM import (graceful if library not installed) ──
try:
    from ibm_watsonx_ai import APIClient, Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    _IBM_AVAILABLE = True
except ImportError:
    _IBM_AVAILABLE = False

# ============================================================
#  AGENT INSTRUCTIONS  <- Customize everything here
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
        "intermediate": "Moderate intensity, 4-5 days/week, progressive overload.",
        "advanced":     "High intensity, 5-6 days/week, periodization and recovery focus.",
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
        "- Numbered steps for workout routines\n"
        "- Bullet points for nutrition tips\n"
        "- Tables (in Markdown) for meal plans or macro comparisons\n"
        "- Bold headings for sections\n"
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

    return (
        f"## Identity\n{ai['name']} -- {ai['persona']}\n\n"
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


# ── Models that support the /text/chat endpoint ──────────────
_CHAT_CAPABLE_MODELS = {
    "meta-llama/llama-3-3-70b-instruct",
    "meta-llama/llama-3-1-70b-instruct",
    "meta-llama/llama-3-1-8b-instruct",
    "meta-llama/llama-3-1-8b",
    "ibm/granite-3-8b-instruct",
    "ibm/granite-13b-chat-v2",
}


# ============================================================
#  BUILT-IN FITNESS KNOWLEDGE ENGINE
#  Used when IBM API key is not yet configured / invalid.
#  Provides full, rich, personalised responses for every topic.
# ============================================================
class _FitnessKnowledgeEngine:
    """
    Rule-based fitness knowledge engine.
    Returns rich, personalised Markdown responses for all major
    fitness topics -- workout plans, meal plans, BMI, hydration,
    yoga, HIIT, sleep, recovery, Indian diet, etc.
    """

    # ── topic matchers ────────────────────────────────────────
    # Order matters: more specific patterns first
    _TOPICS = [
        ("bmi",        r"bmi|body mass index|underweight|overweight|obese"),
        ("bmr",        r"bmr|basal metabolic|tdee|maintenance calorie"),
        ("weight_loss",r"weight loss|lose weight|fat loss|slim|cut weight|burn fat"),
        ("muscle",     r"muscle|bulk|gain weight|mass|hypertrophy"),
        ("hiit",       r"hiit|high intensity|tabata|interval train"),
        ("yoga",       r"yoga|flexibility|meditation|mindful|sun salut"),
        ("home",       r"home workout|no equipment|no gym"),
        ("running",    r"run|jog|marathon|5k|10k"),
        ("warmup",     r"warm.?up|cool.?down|stretch before|stretch after"),
        ("beginner",   r"beginner|new to|first time|never exercised|just start"),
        ("indian",     r"indian|dal|roti|paneer|sabzi|idli|dosa|poha|chapati|rajma|chana"),
        ("water",      r"water|hydrat|fluid intake|glasses"),
        ("sleep",      r"sleep|insomni|rest day|recovery day"),
        ("motivation", r"motivat|lazy|give up|quit|stuck|plateau|tired of"),
        ("workout",    r"workout plan|exercise plan|training plan|gym plan|create.*plan|generate.*plan|routine"),
        ("nutrition",  r"eat|diet|nutrition|food|meal plan|calorie|protein|carb|fat|macro"),
    ]

    def respond(self, message: str, profile: dict | None = None) -> str:
        msg = message.lower()
        topic = self._detect_topic(msg)
        name  = (profile or {}).get("name", "there")
        goal  = (profile or {}).get("fitness_goal", "general_fitness")
        level = (profile or {}).get("fitness_level", "beginner")
        diet  = (profile or {}).get("diet_preference", "vegetarian")
        wt    = (profile or {}).get("weight", 70)
        ht    = (profile or {}).get("height", 170)

        dispatch = {
            "bmi":        self._bmi,
            "bmr":        self._bmr,
            "weight_loss":self._weight_loss,
            "muscle":     self._muscle,
            "hiit":       self._hiit,
            "yoga":       self._yoga,
            "home":       self._home_workout,
            "running":    self._running,
            "nutrition":  self._nutrition,
            "indian":     self._indian_diet,
            "water":      self._water,
            "sleep":      self._sleep,
            "workout":    self._workout_plan,
            "motivation": self._motivation,
            "warmup":     self._warmup,
            "beginner":   self._beginner,
        }
        fn = dispatch.get(topic, self._general)
        return fn(name, goal, level, diet, wt, ht, message)

    def _detect_topic(self, msg: str) -> str:
        for topic, pattern in self._TOPICS:
            if re.search(pattern, msg):
                return topic
        return "general"

    # ── response methods ──────────────────────────────────────
    def _workout_plan(self, name, goal, level, diet, wt, ht, msg):
        plans = {
            "weight_loss": """
## 7-Day Weight Loss Workout Plan

**Day 1 -- Full Body HIIT (30 min)**
- Warm-up: 5 min light jog + arm circles
- 20 jumping jacks, 15 squats, 10 push-ups, 30-sec plank x 3 rounds
- Cool-down: 5 min static stretching

**Day 2 -- Active Recovery**
- 30 min brisk walk or light yoga

**Day 3 -- Strength + Cardio (40 min)**
- 3 x 12 lunges, 3 x 10 push-ups, 3 x 15 glute bridges
- 15 min steady-state cardio (cycling / running)

**Day 4 -- Rest Day**
- Light stretching, foam rolling

**Day 5 -- HIIT Cardio (25 min)**
- Tabata: 40 sec work / 20 sec rest x 8 rounds
- Exercises: burpees, mountain climbers, high knees, jump squats

**Day 6 -- Yoga & Core (30 min)**
- Sun salutations x 5, plank holds, boat pose, child's pose

**Day 7 -- Long Walk / Light Jog (45 min)**

> **Tip:** Aim for a 300-500 kcal daily deficit. Consistency beats intensity every time!
""",
            "muscle_gain": """
## 7-Day Muscle Gain Plan (Push-Pull-Legs)

**Day 1 -- Push (Chest, Shoulders, Triceps)**
- 4 x 8 push-ups (progress to weighted), 3 x 10 pike push-ups, 3 x 12 tricep dips

**Day 2 -- Pull (Back, Biceps)**
- 4 x 6 pull-ups / rows, 3 x 12 curls, 3 x 10 reverse flyes

**Day 3 -- Legs**
- 4 x 10 squats, 3 x 12 lunges, 3 x 15 calf raises, 3 x 12 glute bridges

**Day 4 -- Rest / Active Recovery**

**Day 5 -- Push (Heavy)**  **Day 6 -- Pull (Heavy)**  **Day 7 -- Legs (Volume)**

> **Key:** Progressive overload weekly. Eat 1.6-2g protein per kg bodyweight. Sleep 8 hrs.
""",
        }
        goal_key = "muscle_gain" if "muscle" in goal else "weight_loss"
        plan = plans.get(goal_key, plans["weight_loss"])
        return f"Hi {name}! Here is your personalized **{level.title()}** plan:\n{plan}"

    def _weight_loss(self, name, goal, level, diet, wt, ht, msg):
        tdee = round(10 * wt + 6.25 * ht - 5 * 25 + 5)  # approx
        target = tdee - 500
        return f"""
## Weight Loss Guide for {name}

**Your estimated TDEE:** ~{tdee} kcal/day
**Weight loss target:** ~{target} kcal/day (0.5 kg/week loss)

### Exercise Plan (3-5 days/week)
1. **Cardio** -- 30-45 min brisk walk, cycling, or swimming
2. **Strength training** -- 2-3x/week to preserve muscle while losing fat
3. **HIIT** -- 1-2x/week for metabolic boost (20-25 min)
4. **Daily steps** -- Target 8,000-10,000 steps/day

### Nutrition Rules
- **Calorie deficit:** 300-500 kcal below TDEE
- **Protein:** {round(wt * 1.6)}g/day to preserve muscle
- **Fibre:** 25-30g/day (dal, sabzi, fruits, oats)
- **Avoid:** sugary drinks, processed snacks, fried food
- **Eat:** salads, soups, dal, grilled proteins before meals

### Sample Indian Meal Plan ({target} kcal)
| Meal | Food | Calories |
|------|------|----------|
| Breakfast | Poha with veggies + 1 boiled egg | 280 kcal |
| Mid-morning | 1 apple + 10 almonds | 150 kcal |
| Lunch | 2 rotis + dal + sabzi + curd | 450 kcal |
| Snack | Sprouts chaat | 120 kcal |
| Dinner | Grilled paneer + salad + 1 roti | 380 kcal |

> **Remember:** Weight loss is 80% diet, 20% exercise. Stay consistent!
"""

    def _muscle(self, name, goal, level, diet, wt, ht, msg):
        protein = round(wt * 2.0)
        calories = round(10 * wt + 6.25 * ht - 5 * 25 + 5 + 500)
        return f"""
## Muscle Gain Guide for {name}

**Daily calorie target:** ~{calories} kcal (500 kcal surplus)
**Daily protein target:** {protein}g ({round(wt * 2.0)}g/kg)

### Training Split (5 days/week)
| Day | Focus | Key Exercises |
|-----|-------|---------------|
| Mon | Chest + Triceps | Push-ups, dips, chest press |
| Tue | Back + Biceps | Rows, pull-ups, curls |
| Wed | Legs | Squats, lunges, calf raises |
| Thu | Shoulders + Core | Pike press, lateral raises, plank |
| Fri | Full Body Power | Deadlifts, compound movements |
| Sat-Sun | Rest / Active recovery | Walk, yoga |

### Progressive Overload
- Increase reps or resistance **every 2 weeks**
- Track your lifts in a notebook or app
- Aim for 8-12 reps per set for hypertrophy

### High-Protein Indian Meals
- **Breakfast:** Paneer bhurji + 2 eggs + whole wheat toast
- **Post-workout:** Curd + banana + protein shake (optional)
- **Lunch:** Rajma / chana + brown rice + salad
- **Dinner:** Grilled chicken / paneer + dal + veggies
- **Snacks:** Roasted chana, moong sprouts, peanut butter

> **Sleep 8 hrs -- that's when muscles actually grow!**
"""

    def _hiit(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## HIIT Workout for {name} ({level.title()})

### What is HIIT?
High-Intensity Interval Training alternates short bursts of intense exercise
with rest periods -- burns more fat in less time!

### 20-Minute Beginner HIIT
**Format:** 40 seconds work / 20 seconds rest

| Round | Exercise |
|-------|----------|
| 1 | Jumping Jacks |
| 2 | Bodyweight Squats |
| 3 | Push-ups (knee or full) |
| 4 | High Knees |
| 5 | Glute Bridges |
| 6 | Mountain Climbers |
| 7 | Plank Hold |
| 8 | Burpees (modified) |

**Rest 60 seconds then repeat 2-3 rounds**

### HIIT Rules
- Warm up 5 min FIRST (light jog, arm circles)
- Cool down 5 min AFTER (static stretching)
- Max **3 HIIT sessions/week** -- needs 48 hr recovery
- Beginners: start with 2 rounds, build to 4

### Calorie Burn
A 25-min HIIT session burns **200-400 kcal** depending on intensity and body weight.

> **HIIT tip:** The "afterburn effect" (EPOC) keeps burning calories for up to 24 hrs after!
"""

    def _yoga(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Yoga Routine for {name}

### Benefits
Improves flexibility, reduces stress, boosts recovery, improves posture and balance.

### 30-Minute Morning Yoga Flow

**Warm-up (5 min)**
- Child's Pose (Balasana) -- 1 min
- Cat-Cow stretches -- 10 reps
- Seated neck rolls

**Sun Salutations (10 min)**
- 5 rounds of Surya Namaskar (12 poses each)
- Breath: inhale on expansions, exhale on folds

**Standing Poses (8 min)**
1. Warrior I (Virabhadrasana I) -- 30 sec each side
2. Warrior II -- 30 sec each side
3. Triangle Pose (Trikonasana) -- 30 sec each side
4. Tree Pose (Vrikshasana) -- 30 sec each side

**Floor/Cool-down (7 min)**
- Seated forward fold (Paschimottanasana) -- 1 min
- Supine twist -- 1 min each side
- Bridge Pose -- 30 sec x 3
- Savasana (Corpse Pose) -- 3 min

### Yoga for Specific Goals
- **Flexibility:** Yin Yoga (hold poses 3-5 min)
- **Stress relief:** Restorative Yoga + pranayama
- **Strength:** Ashtanga or Power Yoga
- **Back pain:** Gentle Hatha with cat-cow, child's pose

> **Best time:** Morning on empty stomach or evening 3 hrs after eating.
"""

    def _home_workout(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Home Workout Plan for {name} -- No Equipment Needed!

### Full Body Routine (3x/week, 30-40 min)

**Warm-up (5 min)**
- Jumping jacks x 30
- Arm circles x 20 each direction
- Leg swings x 15 each leg
- Hip circles x 10

**Main Workout -- 3 rounds, 45 sec work / 15 sec rest**

| Exercise | Muscles | Beginner | Advanced |
|----------|---------|----------|----------|
| Push-ups | Chest, triceps | Knee push-ups | Archer push-ups |
| Squats | Quads, glutes | Regular | Jump squats |
| Glute bridges | Hamstrings, glutes | Both feet | Single leg |
| Plank | Core | 20 seconds | 60 seconds |
| Mountain climbers | Core, cardio | Slow | Fast |
| Tricep dips (chair) | Triceps | Bent legs | Straight legs |

**Cool-down (5 min)**
- Quad stretch, hamstring stretch, chest stretch, child's pose

### Progressive Schedule
- **Week 1-2:** 2 rounds
- **Week 3-4:** 3 rounds
- **Week 5+:** Add resistance (backpack with books)

> **You only need your bodyweight and 30 minutes. No excuses!**
"""

    def _running(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Running / Cardio Guide for {name}

### Couch to 5K Plan (8 weeks)
| Week | Workout |
|------|---------|
| 1-2 | Walk 90 sec, jog 60 sec -- repeat 8x (20 min) |
| 3-4 | Walk 90 sec, jog 3 min -- repeat 5x (22 min) |
| 5-6 | Walk 2 min, jog 5 min -- repeat 4x (28 min) |
| 7 | Jog 20 min continuously |
| 8 | Jog 30 min (5K goal!) |

### Running Tips
- **Shoes:** Invest in proper running shoes (prevents injury)
- **Cadence:** Aim for 170-180 steps/min
- **Breathing:** Breathe in for 3 steps, out for 2
- **Rest:** Never run more than 5 days/week
- **Hydration:** Drink 250ml water 30 min before running

### Pre & Post Run Nutrition
- **Before (1hr):** Banana + peanut butter on toast
- **After:** Protein + carbs within 30 min (curd + rice, or eggs + roti)

### Calorie Burn (approx. for {wt}kg)
- 30 min easy jog: ~{round(wt * 5.5)} kcal
- 30 min moderate run: ~{round(wt * 7)} kcal
- 30 min fast run: ~{round(wt * 9)} kcal

> **Run slow to run long -- 80% of your runs should be at a conversational pace.**
"""

    def _nutrition(self, name, goal, level, diet, wt, ht, msg):
        protein = round(wt * 1.8)
        carbs   = round(wt * 3)
        fat     = round(wt * 0.8)
        cal     = protein * 4 + carbs * 4 + fat * 9
        return f"""
## Personalised Nutrition Guide for {name}

### Your Daily Macros (estimated)
| Macro | Amount | Calories |
|-------|--------|---------|
| Protein | {protein}g | {protein * 4} kcal |
| Carbohydrates | {carbs}g | {carbs * 4} kcal |
| Fat | {fat}g | {fat * 9} kcal |
| **Total** | | **~{cal} kcal** |

### Meal Timing
- **Breakfast (7-8 AM):** Largest carb + protein meal
- **Lunch (12-1 PM):** Balanced -- protein + carbs + veggies
- **Snack (4 PM):** High protein, low sugar
- **Dinner (7-8 PM):** High protein, lower carbs
- **Post-workout:** Protein + simple carbs within 30 min

### Best Protein Sources ({diet})
- **Vegetarian:** Paneer, curd, moong dal, rajma, chana, tofu, eggs
- **High protein:** Chicken breast, fish, eggs, Greek yoghurt

### Sample Full-Day Meal Plan
| Meal | Food | Protein | Calories |
|------|------|---------|---------|
| Breakfast | Oats + milk + banana | 15g | 350 kcal |
| Lunch | Dal + 2 rotis + sabzi + curd | 22g | 500 kcal |
| Snack | Boiled eggs / paneer | 18g | 200 kcal |
| Dinner | Grilled paneer + salad + 1 roti | 25g | 400 kcal |
| Total | | ~80g | ~1450 kcal |

> **Rule of thumb:** Fill half your plate with vegetables, quarter protein, quarter carbs.
"""

    def _indian_diet(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Indian Diet Plan for Fitness -- {name}

### Why Indian Food is Great for Fitness
- Dal and legumes: high protein, high fibre
- Turmeric: anti-inflammatory, aids recovery
- Curd: probiotics + calcium + protein
- Roti: complex carbs for sustained energy
- Seasonal vegetables: micronutrients

### 7-Day Indian Meal Plan

| Day | Breakfast | Lunch | Dinner |
|-----|-----------|-------|--------|
| Mon | Poha + chai | Dal rice + sabzi + curd | Palak paneer + 1 roti |
| Tue | Idli (3) + sambar | Rajma + brown rice + salad | Moong dal + 2 rotis |
| Wed | Besan cheela + mint chutney | Chole + roti + raita | Grilled paneer + salad |
| Thu | Oats upma | Mixed dal khichdi + papad | Kadhi + rice (small) |
| Fri | Sprouts chaat | Aloo gobhi + dal + roti | Palak tofu + roti |
| Sat | Whole wheat dosa + sambar | Pav bhaji (less butter) | Dal makhani + 1 roti |
| Sun | Veg paratha (1, less oil) + curd | Biryani (small portion) + raita | Soup + salad |

### High-Protein Indian Snacks
- Roasted chana (50g) -- 12g protein
- Moong sprouts chaat -- 8g protein
- Peanut chikki (small) -- 6g protein
- Curd with flaxseeds -- 10g protein
- Boiled eggs (2) -- 12g protein

### Superfoods to Add Daily
- **Turmeric** in dal/milk: anti-inflammatory
- **Amla** (gooseberry): Vitamin C, immunity
- **Flaxseeds** (1 tbsp): Omega-3, fibre
- **Moringa powder**: Iron, calcium, protein

> **Tip:** Cook with minimal oil (1 tsp/meal). Prefer mustard or coconut oil.
"""

    def _water(self, name, goal, level, diet, wt, ht, msg):
        target_ml = round(wt * 35)
        glasses   = round(target_ml / 250)
        return f"""
## Hydration Guide for {name}

### Your Daily Water Target
**{target_ml} ml ({target_ml/1000:.1f} litres) -- approximately {glasses} glasses of 250ml**

This is based on your weight of {wt}kg x 35 ml/kg.

### When to Drink
| Time | Amount | Reason |
|------|--------|--------|
| Wake up | 500ml (2 glasses) | Rehydrate after sleep |
| Before breakfast | 250ml | Kickstart digestion |
| Before lunch | 250ml | Reduces overeating |
| During workout | 150-250ml every 20 min | Prevent dehydration |
| After workout | 500ml | Restore fluid loss |
| Before dinner | 250ml | Aids digestion |
| Before bed | 200ml (small) | Night hydration |

### Signs of Dehydration
- Dark yellow urine (should be pale yellow)
- Headaches, fatigue
- Reduced workout performance
- Dry mouth / skin

### Hydration Tips
- Carry a 1-litre water bottle everywhere
- Add lemon + mint for flavour (zero calories)
- Coconut water post-workout: electrolytes
- Avoid sugary drinks and excessive tea/coffee

> **Check your hydration:** If your urine is pale yellow, you're well hydrated!
"""

    def _sleep(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Sleep & Recovery Guide for {name}

### Why Sleep is the Most Important Fitness Tool
- **Muscle repair** happens during deep sleep (HGH released)
- Poor sleep raises cortisol (fat storage hormone)
- 8 hrs sleep = 20% better athletic performance
- Sleep deprivation increases hunger (ghrelin spike)

### Sleep Targets by Goal
| Goal | Sleep Required |
|------|---------------|
| Weight loss | 7-8 hrs (poor sleep = fat retention) |
| Muscle gain | 8-9 hrs (growth hormone peaks at 1 AM) |
| Endurance | 8-9 hrs (cardiac recovery) |
| General fitness | 7-8 hrs |

### Sleep Hygiene Rules
1. **Fixed schedule:** Sleep and wake at the same time every day
2. **Dark room:** Block all light (melatonin production)
3. **Cool room:** 18-20 degrees C is optimal
4. **No screens 1 hr before bed** (blue light blocks melatonin)
5. **No caffeine after 2 PM**
6. **Light stretching / yoga before bed**
7. **No heavy meals 2 hrs before sleep**

### Pre-Sleep Routine (30 min)
- 10 min light stretching or yoga
- 10 min reading (non-screen)
- 250ml warm milk + turmeric (promotes sleep)
- Deep breathing: 4-7-8 technique

### Recovery Days
- Active recovery: light walk, yoga, swimming
- Foam rolling: reduces DOMS by 30%
- Target 1-2 complete rest days per week

> **Sleep is not laziness -- it is when your body becomes stronger.**
"""

    def _motivation(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## You've Got This, {name}! 💪

### Remember Why You Started
Every expert was once a beginner. Every fit person had a Day 1.
The only workout you'll regret is the one you didn't do.

### Breaking Through a Plateau
If progress has stalled, try these:
1. **Change your routine** -- your body adapts, so shock it
2. **Track your food** -- hidden calories often cause stalls
3. **Check sleep** -- poor sleep kills fat loss
4. **Increase NEAT** -- take stairs, walk more, stand at desk
5. **Deload week** -- reduce intensity for 1 week, then push harder

### Small Wins to Track
- Did you drink 8 glasses of water today? WIN
- Did you get 7+ hrs sleep? WIN
- Did you walk 8,000 steps? WIN
- Did you skip the junk food? WIN

### Mindset Shifts
- "I don't have time" -- 20 minutes is enough. Everyone has 20 minutes.
- "I'm not seeing results" -- Take measurements, not just scale weight.
- "I always fail diets" -- You don't need a perfect diet. An 80% good diet beats a 100% diet abandoned.

### Your 30-Day Challenge
- **Week 1:** 3 workouts + 8 glasses water + 7 hrs sleep
- **Week 2:** Add 10 min daily walk
- **Week 3:** Clean up breakfast every day
- **Week 4:** Review progress and set next 30-day goal

> *"Success is the sum of small efforts, repeated day in and day out."* -- Robert Collier
"""

    def _warmup(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Warm-Up & Cool-Down Guide for {name}

### Why Warm Up? (Never Skip This!)
- Raises muscle temperature by 1-2 degrees C
- Increases blood flow to muscles
- Reduces injury risk by up to 50%
- Prepares nervous system for performance

### 5-Minute Dynamic Warm-Up
| Exercise | Duration | Purpose |
|----------|----------|---------|
| March in place | 60 sec | Heart rate up |
| Arm circles (forward + back) | 30 sec each | Shoulder mobility |
| Leg swings (front/back) | 15 each leg | Hip flexor mobility |
| Hip circles | 10 each direction | Hip joint prep |
| Bodyweight squats (slow) | 10 reps | Knee + ankle prep |
| Inchworms | 5 reps | Full body activation |

### 5-Minute Cool-Down Stretches
| Stretch | Hold | Muscle |
|---------|------|--------|
| Quad stretch (standing) | 30 sec each | Quadriceps |
| Hamstring stretch (seated) | 45 sec each | Hamstrings |
| Chest stretch (doorway) | 30 sec | Pectorals |
| Child's pose | 60 sec | Lower back |
| Pigeon pose | 45 sec each | Hip flexors |
| Neck side stretch | 20 sec each | Neck, traps |

### Golden Rules
- Warm-up = dynamic movement (never static stretch before workout)
- Cool-down = static holds (never dynamic after workout)
- If short on time, cut the workout -- never cut the warm-up
- Post-workout is the BEST time to improve flexibility (muscles are warm)

> **5 minutes of warm-up prevents 5 weeks of injury recovery.**
"""

    def _bmi(self, name, goal, level, diet, wt, ht, msg):
        h_m = ht / 100
        bmi = round(wt / (h_m * h_m), 1)
        if bmi < 18.5:   cat, advice = "Underweight", "Focus on calorie surplus (300-500 kcal above TDEE), strength training 3x/week, and high-protein foods like paneer, eggs, and nuts."
        elif bmi < 25:   cat, advice = "Normal Weight", "Excellent! Maintain with balanced nutrition and regular exercise. Focus on building strength and cardiovascular health."
        elif bmi < 30:   cat, advice = "Overweight", "A 300-500 kcal daily deficit with 4x/week exercise will bring you to normal range in 3-6 months. Prioritise protein and fibre."
        else:             cat, advice = "Obese", "Start with low-impact exercise (walking, swimming, cycling) and consult a doctor. Even a 5-10% weight loss significantly improves health markers."
        return f"""
## BMI Analysis for {name}

**Your BMI: {bmi} -- {cat}**

| Category | BMI Range |
|----------|-----------|
| Underweight | < 18.5 |
| Normal Weight | 18.5 - 24.9 |
| Overweight | 25.0 - 29.9 |
| Obese | >= 30.0 |

### Personalised Advice
{advice}

### BMI Limitations
BMI does not account for:
- Muscle mass (athletes often show "overweight" BMI)
- Fat distribution (waist circumference is also important)
- Age and gender differences

### Better Health Metrics to Track
- **Waist circumference:** <80cm women, <94cm men = healthy
- **Waist-to-height ratio:** <0.5 = healthy
- **Body fat %:** 15-25% women, 10-20% men = athletic range

> Use the **Calculator** page to see your full BMI, BMR, and TDEE breakdown!
"""

    def _bmr(self, name, goal, level, diet, wt, ht, msg):
        bmr  = round(10 * wt + 6.25 * ht - 5 * 25 + 5)
        tdee = round(bmr * 1.55)
        return f"""
## BMR & Calorie Guide for {name}

**Estimated BMR:** {bmr} kcal/day *(calories burned at complete rest)*
**Estimated TDEE:** {tdee} kcal/day *(with moderate activity)*

### Calorie Targets by Goal
| Goal | Daily Calories | Weekly Change |
|------|---------------|---------------|
| Weight Loss (slow) | {tdee - 300} kcal | -0.25 kg/week |
| Weight Loss (fast) | {tdee - 500} kcal | -0.5 kg/week |
| Maintenance | {tdee} kcal | 0 |
| Muscle Gain (lean) | {tdee + 250} kcal | +0.25 kg/week |
| Muscle Gain (fast) | {tdee + 500} kcal | +0.5 kg/week |

> Use the **Calculator** page for a precise calculation with your activity level and gender!
"""

    def _beginner(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## Welcome to Fitness, {name}! Your Beginner Roadmap

### The Golden Rule for Beginners
**Start small, be consistent, progress gradually.**
3 days/week for 3 months beats 7 days/week for 2 weeks then quitting.

### Week 1-4: Foundation Phase
**3 days/week (e.g., Mon, Wed, Fri)**

Each session (20-25 min):
1. 5 min warm-up (jumping jacks, marching)
2. 10 knee push-ups
3. 15 bodyweight squats
4. 30-sec plank hold
5. 10 glute bridges
6. 5 min cool-down stretching

**Rest days:** Light walking 15-20 min

### Week 5-8: Build Phase
- Add 1 more session per week (4 days)
- Increase reps by 2-3 each week
- Introduce lunges and dips

### Week 9-12: Progress Phase
- 4-5 sessions/week
- Full push-ups (not knee), longer plank
- Add 5-10 min cardio at end of session

### Beginner Nutrition (Keep It Simple)
- Eat 3 proper meals + 1-2 snacks
- Include protein every meal (dal, curd, eggs, paneer)
- Drink 8 glasses of water
- Avoid sugary drinks completely
- Don't skip breakfast

### Tracking Progress
- Take photos every 4 weeks (same time, same lighting)
- Measure waist/hips monthly (not just weight)
- Track workout reps/sets in a notebook

> **The hardest workout is the first one. After that, it gets easier every single time.**
"""

    def _general(self, name, goal, level, diet, wt, ht, msg):
        return f"""
## FitBot Response for {name}

Hi {name}! I'm FitBot, your AI fitness coach.

I can help you with:
- **Personalized workout plans** (beginner to advanced)
- **Nutrition & meal planning** (Indian & international)
- **Weight loss or muscle gain** strategies
- **HIIT, Yoga, Running, Home workouts**
- **BMI, BMR & calorie calculations**
- **Hydration, sleep, and recovery tips**
- **Motivation & habit building**

**Try asking me:**
- "Create a workout plan for weight loss"
- "Give me an Indian meal plan for muscle gain"
- "How much water should I drink daily?"
- "What is HIIT and should I do it?"
- "Give me a beginner yoga routine"
- "How many calories should I eat?"

Your current profile:
- Goal: **{goal.replace('_', ' ').title()}**
- Level: **{level.title()}**
- Diet: **{diet.replace('_', ' ').title()}**

What would you like help with today?
"""


# ── singleton knowledge engine ────────────────────────────────
_knowledge_engine = _FitnessKnowledgeEngine()


# ============================================================
#  FITPULSE AGENT
# ============================================================
class FitPulseAgent:
    """
    Wrapper around IBM watsonx.ai ModelInference for FitPulse.

    Credentials are read lazily via properties so that load_dotenv()
    in app.py always wins regardless of module import order.

    Falls back to built-in knowledge engine when IBM API is unavailable.
    """

    def __init__(self):
        # Do NOT call os.getenv here -- .env may not be loaded yet at import time.
        self._client          = None
        self._model           = None
        self._cached_model_id = None

    # ── Lazy credential properties ─────────────────────────────
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
        return self.model_id in _CHAT_CAPABLE_MODELS

    @property
    def _ibm_configured(self) -> bool:
        """True only if both key and project ID are present."""
        return bool(self.api_key and self.project_id)

    def _get_model(self):
        if not _IBM_AVAILABLE:
            return None
        if self._model is None or self._cached_model_id != self.model_id:
            credentials = Credentials(url=self.url, api_key=self.api_key)
            self._client = APIClient(credentials=credentials)
            self._model  = ModelInference(
                model_id   = self.model_id,
                credentials= credentials,
                project_id = self.project_id,
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
        Uses IBM watsonx.ai when credentials are valid; otherwise
        uses the built-in fitness knowledge engine.
        """
        # ── Try IBM watsonx.ai first ──────────────────────────
        if _IBM_AVAILABLE and self._ibm_configured:
            try:
                model = self._get_model()
                system_prompt = _build_system_prompt(user_profile)
                max_history   = int(os.getenv("MAX_CHAT_HISTORY", 20))

                if self._supports_chat:
                    messages = [{"role": "system", "content": system_prompt}]
                    for msg in conversation_history[-max_history:]:
                        messages.append({"role": msg["role"], "content": msg["content"]})
                    messages.append({"role": "user", "content": user_message})

                    response = model.chat(
                        messages=messages,
                        params={"max_tokens": 1024, "temperature": 0.7},
                    )
                    if isinstance(response, dict):
                        text = (
                            response.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                            .strip()
                        )
                        if text:
                            return text
                    if hasattr(response, "choices") and response.choices:
                        return response.choices[0].message.content.strip()
                    return str(response).strip()

                else:
                    # Generate API for base models
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
                            GP.MAX_NEW_TOKENS:     1024,
                            GP.TEMPERATURE:        0.7,
                            GP.TOP_P:              0.9,
                            GP.REPETITION_PENALTY: 1.1,
                            GP.STOP_SEQUENCES:     ["<|user|>", "<|end|>", "User:"],
                        },
                    )
                    return str(response).strip()

            except Exception:
                # IBM call failed -- fall through to knowledge engine
                pass

        # ── Built-in fitness knowledge engine (always works) ──
        return _knowledge_engine.respond(user_message, user_profile)

    # ----------------------------------------------------------
    def generate_workout_plan(self, profile: dict) -> str:
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
        return self.chat(query, [], profile)


# Singleton instance used across the app
agent = FitPulseAgent()
