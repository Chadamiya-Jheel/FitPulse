# FitPulse — AI-Powered Fitness Buddy 🏋️‍♂️

> An intelligent fitness web application powered by **IBM watsonx.ai Granite models**,  
> built with Python Flask, Bootstrap 5, and SQLite.

---

## 🌟 Features

| Feature | Description |
|---|---|
| 🤖 **AI Chat Coach** | Real-time chat with FitBot (IBM Granite) for workouts, nutrition & wellness |
| 🏋️ **Workout Planner** | AI-generated personalized plans: beginner → advanced, HIIT, yoga, strength |
| 🥗 **Nutrition Planner** | Indian & international meal plans, macros, calorie tracking |
| 📊 **Progress Dashboard** | Chart.js graphs for weight, workouts, and calorie trends |
| 🧮 **BMI & BMR Calculator** | Full health metrics with activity-adjusted TDEE |
| 💧 **Calorie & Water Tracker** | Daily intake, macros, and hydration monitoring |
| ✅ **Habit Tracker** | Sleep, steps, meditation, and custom habits |
| 👤 **User Profiles** | Personalized AI context: age, goals, diet, equipment |
| 🌙 **Dark Mode** | Full dark/light theme toggle with persistence |
| 📱 **Mobile Responsive** | Optimized for all screen sizes |

---

## 🏗️ Project Structure

```
fitpulse/
├── app.py                  # Main Flask application & all routes
├── models.py               # SQLAlchemy database models
├── ai_agent.py             # IBM watsonx.ai integration + AGENT_INSTRUCTIONS
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── Procfile                # Heroku/Code Engine deployment
├── static/
│   ├── css/style.css       # Custom styles (Bootstrap 5 extensions, dark mode)
│   └── js/app.js           # Frontend JavaScript (charts, chat, forms)
└── templates/
    ├── base.html           # Master layout (navbar, footer, flash messages)
    ├── index.html          # Landing page
    ├── dashboard.html      # Fitness dashboard with charts
    ├── chat.html           # AI chat interface
    ├── workout.html        # Workout planner & logger
    ├── nutrition.html      # Nutrition tracker & meal planner
    ├── calculator.html     # BMI & BMR calculator
    ├── habits.html         # Habit tracker
    ├── profile.html        # User profile management
    ├── login.html          # Login page
    ├── register.html       # Registration page
    └── error.html          # Error pages (404, 500)
```

---

## 🚀 Quick Start (Local)

### 1. Clone / Download the project

```bash
git clone https://github.com/your-username/fitpulse.git
cd fitpulse
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
SECRET_KEY=your-very-secret-flask-key-change-me
WATSONX_API_KEY=your-ibm-cloud-api-key-here
WATSONX_PROJECT_ID=your-watsonx-project-id-here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-3-8b-instruct
```

### 5. Initialize the database

```bash
flask init-db
```

### 6. Run the application

```bash
python app.py
```

Open **http://localhost:5000** in your browser. 🎉

---

## 🔑 Getting IBM watsonx.ai Credentials

1. Sign up at [IBM Cloud](https://cloud.ibm.com/) (free tier available)
2. Create a **Watson Machine Learning** service instance
3. Go to **watsonx.ai** → Create a project
4. Copy your **API Key** from IAM → API Keys
5. Copy your **Project ID** from the watsonx project settings

---

## 🤖 Customizing the AI Coach (AGENT_INSTRUCTIONS)

Open [`ai_agent.py`](ai_agent.py) and modify the `AGENT_INSTRUCTIONS` dictionary at the top:

```python
AGENT_INSTRUCTIONS = {
    "name": "FitBot",                          # Coach name
    "persona": "Your expert fitness coach...", # Personality description
    "tone": "Warm and encouraging...",         # Communication tone
    "specialization": "Weight loss, HIIT...", # Fitness expertise
    "safety": "Always recommend doctor...",    # Safety guidelines
    "motivation": "Positive reinforcement...", # Motivation style
    "intensity": {
        "beginner":     "3 days/week, low impact",
        "intermediate": "4-5 days/week, moderate",
        "advanced":     "5-6 days/week, periodization",
    },
    "indian_diet": "Prioritize dal, sabzi...", # Indian diet preferences
    "format_instructions": "Use bullet points...",
    "prohibited": "No illegal supplements...",
}
```

No restart required for production — just save the file and redeploy.

---

## ☁️ IBM Cloud Code Engine Deployment

### Prerequisites
- IBM Cloud CLI installed
- Code Engine plugin: `ibmcloud plugin install code-engine`

### Steps

```bash
# 1. Login to IBM Cloud
ibmcloud login --apikey YOUR_API_KEY -r us-south

# 2. Target your Code Engine project
ibmcloud ce project select --name fitpulse-project

# 3. Create the application
ibmcloud ce application create \
  --name fitpulse \
  --image docker.io/your-username/fitpulse:latest \
  --env WATSONX_API_KEY=your-key \
  --env WATSONX_PROJECT_ID=your-project-id \
  --env SECRET_KEY=your-secret-key \
  --min-scale 1 \
  --port 5000

# Or deploy from source (Code Engine build)
ibmcloud ce buildrun submit \
  --build fitpulse-build \
  --source https://github.com/your-username/fitpulse
```

### Using a Procfile (Heroku / Railway / Render)

```Procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

---

## 🐳 Docker Deployment

```bash
# Build image
docker build -t fitpulse:latest .

# Run container
docker run -d \
  -p 5000:5000 \
  --env-file .env \
  --name fitpulse \
  fitpulse:latest
```

**Dockerfile** (create in project root):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN flask init-db
EXPOSE 5000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
```

---

## 🗄️ Database Models

| Model | Fields |
|---|---|
| `User` | id, username, email, age, gender, height, weight, fitness_goal, activity_level, diet_preference, equipment, etc. |
| `ChatMessage` | id, user_id, role (user/assistant), content, timestamp, session_id |
| `WorkoutLog` | id, user_id, date, workout_type, duration, calories, notes, completed |
| `NutritionLog` | id, user_id, date, meal_type, food_item, calories, protein, carbs, fat, water_ml |
| `HabitLog` | id, user_id, date, habit_name, completed, value, unit |
| `WeightLog` | id, user_id, date, weight, notes |

---

## 🔒 Security Notes

- Never commit `.env` to source control
- `SECRET_KEY` must be random and long in production
- Use HTTPS in production (Code Engine provides this by default)
- Passwords are hashed using **Werkzeug** (PBKDF2-SHA256)

---

## 📦 Key Dependencies

| Package | Purpose |
|---|---|
| `Flask` | Web framework |
| `Flask-SQLAlchemy` | ORM & database |
| `Flask-Login` | Authentication & sessions |
| `ibm-watsonx-ai` | IBM Granite AI integration |
| `python-dotenv` | Environment variable management |
| `gunicorn` | Production WSGI server |

---

## 🏆 Hackathon Ready

This project is structured for hackathon presentations:
- **Clean modular architecture** — separate concerns in each file
- **Fully functional** out of the box with fallback responses when API is offline
- **Visually impressive** — modern UI with animations, dark mode, charts
- **Customizable AI** — AGENT_INSTRUCTIONS for easy personality tuning
- **Indian-first design** — diet preferences, meal plans, regional foods

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built with ❤️ using IBM watsonx.ai, Flask, and Bootstrap 5*
