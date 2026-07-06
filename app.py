"""
FitPulse — Main Flask Application
AI-Powered Fitness Buddy with IBM watsonx.ai (Granite)
"""

import os
import json
from datetime import datetime, date, timedelta

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, session,
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user,
)
from dotenv import load_dotenv
from sqlalchemy import func

from models import db, User, ChatMessage, WorkoutLog, NutritionLog, HabitLog, WeightLog
from ai_agent import agent

# ── Bootstrap ────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"]          = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///fitpulse.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    """Inject commonly needed variables into all templates."""
    return {"now": datetime.utcnow()}


# ── Helpers ───────────────────────────────────────────────────
def _today_stats(user: User) -> dict:
    today = date.today()
    calories_burned = (
        db.session.query(func.sum(WorkoutLog.calories))
        .filter_by(user_id=user.id)
        .filter(WorkoutLog.date == today)
        .scalar() or 0
    )
    calories_consumed = (
        db.session.query(func.sum(NutritionLog.calories))
        .filter_by(user_id=user.id)
        .filter(NutritionLog.date == today)
        .scalar() or 0
    )
    water_ml = (
        db.session.query(func.sum(NutritionLog.water_ml))
        .filter_by(user_id=user.id)
        .filter(NutritionLog.date == today)
        .scalar() or 0
    )
    workouts_done = WorkoutLog.query.filter_by(user_id=user.id, date=today, completed=True).count()
    return {
        "calories_burned":   calories_burned,
        "calories_consumed": calories_consumed,
        "water_ml":          water_ml,
        "workouts_done":     workouts_done,
        "calorie_balance":   calories_consumed - calories_burned,
    }


def _chart_data(user: User, days: int = 30) -> dict:
    since = date.today() - timedelta(days=days)

    weight_logs = (
        WeightLog.query
        .filter_by(user_id=user.id)
        .filter(WeightLog.date >= since)
        .order_by(WeightLog.date)
        .all()
    )
    workout_logs = (
        WorkoutLog.query
        .filter_by(user_id=user.id)
        .filter(WorkoutLog.date >= since)
        .order_by(WorkoutLog.date)
        .all()
    )
    cal_logs = (
        NutritionLog.query
        .filter_by(user_id=user.id)
        .filter(NutritionLog.date >= since)
        .order_by(NutritionLog.date)
        .all()
    )

    return {
        "weight": {
            "labels": [str(w.date) for w in weight_logs],
            "data":   [w.weight   for w in weight_logs],
        },
        "workouts": {
            "labels": [str(w.date)     for w in workout_logs],
            "data":   [w.duration      for w in workout_logs],
            "calories": [w.calories    for w in workout_logs],
        },
        "calories": {
            "labels": [str(c.date)     for c in cal_logs],
            "data":   [c.calories      for c in cal_logs],
        },
    }


# ── Auth Routes ───────────────────────────────────────────────
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "warning")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return render_template("register.html")

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Welcome to FitPulse! Complete your profile to get started. 🎉", "success")
        return redirect(url_for("profile"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        remember   = bool(request.form.get("remember"))

        user = (
            User.query.filter_by(username=identifier).first()
            or User.query.filter_by(email=identifier).first()
        )
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))
        flash("Invalid credentials. Please try again.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ── Dashboard ─────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    stats      = _today_stats(current_user)
    chart_data = _chart_data(current_user)
    recent_workouts = (
        WorkoutLog.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkoutLog.date.desc())
        .limit(5)
        .all()
    )
    recent_meals = (
        NutritionLog.query
        .filter_by(user_id=current_user.id)
        .order_by(NutritionLog.date.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "dashboard.html",
        stats=stats,
        chart_data=json.dumps(chart_data),
        recent_workouts=recent_workouts,
        recent_meals=recent_meals,
        user=current_user,
    )


# ── Chat ──────────────────────────────────────────────────────
@app.route("/chat")
@login_required
def chat():
    session_id = request.args.get("session", "default")
    messages = (
        ChatMessage.query
        .filter_by(user_id=current_user.id, session_id=session_id)
        .order_by(ChatMessage.timestamp)
        .all()
    )
    return render_template("chat.html", messages=messages, session_id=session_id)


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data       = request.get_json(force=True)
    user_msg   = (data.get("message") or "").strip()
    session_id = data.get("session_id", "default")

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # Load conversation history from DB
    history_rows = (
        ChatMessage.query
        .filter_by(user_id=current_user.id, session_id=session_id)
        .order_by(ChatMessage.timestamp)
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    # Save user message
    db.session.add(ChatMessage(
        user_id=current_user.id,
        role="user",
        content=user_msg,
        session_id=session_id,
    ))
    db.session.commit()

    # Get AI response
    response_text = agent.chat(user_msg, history, current_user.profile_dict)

    # Save assistant response
    db.session.add(ChatMessage(
        user_id=current_user.id,
        role="assistant",
        content=response_text,
        session_id=session_id,
    ))
    db.session.commit()

    return jsonify({"response": response_text})


@app.route("/api/chat/clear", methods=["POST"])
@login_required
def clear_chat():
    session_id = request.get_json(force=True).get("session_id", "default")
    ChatMessage.query.filter_by(user_id=current_user.id, session_id=session_id).delete()
    db.session.commit()
    return jsonify({"status": "cleared"})


# ── Workout ───────────────────────────────────────────────────
@app.route("/workout")
@login_required
def workout():
    logs = (
        WorkoutLog.query
        .filter_by(user_id=current_user.id)
        .order_by(WorkoutLog.date.desc())
        .limit(30)
        .all()
    )
    return render_template("workout.html", logs=logs)


@app.route("/api/workout/log", methods=["POST"])
@login_required
def log_workout():
    data = request.get_json(force=True)
    log  = WorkoutLog(
        user_id      = current_user.id,
        date         = date.fromisoformat(data.get("date", str(date.today()))),
        workout_type = data.get("workout_type", ""),
        duration     = int(data.get("duration", 0)),
        calories     = int(data.get("calories", 0)),
        notes        = data.get("notes", ""),
        completed    = bool(data.get("completed", True)),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"status": "ok", "id": log.id})


@app.route("/api/workout/generate", methods=["POST"])
@login_required
def generate_workout():
    plan = agent.generate_workout_plan(current_user.profile_dict)
    return jsonify({"plan": plan})


@app.route("/api/workout/delete/<int:log_id>", methods=["DELETE"])
@login_required
def delete_workout(log_id: int):
    log = WorkoutLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    return jsonify({"status": "deleted"})


# ── Nutrition ─────────────────────────────────────────────────
@app.route("/nutrition")
@login_required
def nutrition():
    today = date.today()
    logs  = NutritionLog.query.filter_by(user_id=current_user.id, date=today).all()
    total_cal   = sum(l.calories for l in logs)
    total_prot  = round(sum(l.protein  for l in logs), 1)
    total_carbs = round(sum(l.carbs    for l in logs), 1)
    total_fat   = round(sum(l.fat      for l in logs), 1)
    total_water = sum(l.water_ml       for l in logs)
    return render_template(
        "nutrition.html",
        logs=logs,
        total_cal=total_cal,
        total_prot=total_prot,
        total_carbs=total_carbs,
        total_fat=total_fat,
        total_water=total_water,
        target_calories=int(current_user.tdee),
        target_water=int(current_user.weight * 35),  # 35 ml/kg
    )


@app.route("/api/nutrition/log", methods=["POST"])
@login_required
def log_nutrition():
    data = request.get_json(force=True)
    log  = NutritionLog(
        user_id  = current_user.id,
        date     = date.fromisoformat(data.get("date", str(date.today()))),
        meal_type = data.get("meal_type", ""),
        food_item = data.get("food_item", ""),
        calories  = int(data.get("calories", 0)),
        protein   = float(data.get("protein", 0)),
        carbs     = float(data.get("carbs", 0)),
        fat       = float(data.get("fat", 0)),
        water_ml  = int(data.get("water_ml", 0)),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"status": "ok", "id": log.id})


@app.route("/api/nutrition/delete/<int:log_id>", methods=["DELETE"])
@login_required
def delete_nutrition(log_id: int):
    log = NutritionLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    return jsonify({"status": "deleted"})


@app.route("/api/nutrition/meal-plan", methods=["POST"])
@login_required
def generate_meal_plan():
    plan = agent.generate_meal_plan(current_user.profile_dict)
    return jsonify({"plan": plan})


# ── Calculator ────────────────────────────────────────────────
@app.route("/calculator")
@login_required
def calculator():
    return render_template("calculator.html")


@app.route("/api/calculator/bmi", methods=["POST"])
def calc_bmi():
    data   = request.get_json(force=True)
    height = float(data.get("height", 0))
    weight = float(data.get("weight", 0))
    if height <= 0 or weight <= 0:
        return jsonify({"error": "Invalid input"}), 400
    h_m = height / 100
    bmi = round(weight / (h_m * h_m), 1)
    if bmi < 18.5:   cat = "Underweight"
    elif bmi < 25.0: cat = "Normal weight"
    elif bmi < 30.0: cat = "Overweight"
    else:            cat = "Obese"
    return jsonify({"bmi": bmi, "category": cat})


@app.route("/api/calculator/bmr", methods=["POST"])
def calc_bmr():
    data   = request.get_json(force=True)
    weight = float(data.get("weight", 70))
    height = float(data.get("height", 170))
    age    = int(data.get("age", 25))
    gender = data.get("gender", "male")
    activity = data.get("activity", "moderate")
    if gender == "male":
        bmr = round(10 * weight + 6.25 * height - 5 * age + 5)
    else:
        bmr = round(10 * weight + 6.25 * height - 5 * age - 161)
    multipliers = {
        "sedentary": 1.2, "light": 1.375,
        "moderate": 1.55, "active": 1.725, "very_active": 1.9,
    }
    tdee = round(bmr * multipliers.get(activity, 1.55))
    return jsonify({
        "bmr": bmr, "tdee": tdee,
        "weight_loss":  tdee - 500,
        "weight_gain":  tdee + 500,
        "maintenance":  tdee,
    })


# ── Habits ────────────────────────────────────────────────────
@app.route("/habits")
@login_required
def habits():
    today = date.today()
    logs  = HabitLog.query.filter_by(user_id=current_user.id, date=today).all()
    return render_template("habits.html", logs=logs, today=today)


@app.route("/api/habits/log", methods=["POST"])
@login_required
def log_habit():
    data = request.get_json(force=True)
    log  = HabitLog(
        user_id    = current_user.id,
        date       = date.fromisoformat(data.get("date", str(date.today()))),
        habit_name = data.get("habit_name", ""),
        completed  = bool(data.get("completed", False)),
        value      = float(data.get("value", 0)),
        unit       = data.get("unit", ""),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"status": "ok", "id": log.id})


# ── Weight Log ────────────────────────────────────────────────
@app.route("/api/weight/log", methods=["POST"])
@login_required
def log_weight():
    data = request.get_json(force=True)
    log  = WeightLog(
        user_id = current_user.id,
        date    = date.fromisoformat(data.get("date", str(date.today()))),
        weight  = float(data.get("weight", current_user.weight)),
        notes   = data.get("notes", ""),
    )
    db.session.add(log)
    # Also update user's current weight
    current_user.weight = float(data.get("weight", current_user.weight))
    db.session.commit()
    return jsonify({"status": "ok", "bmi": current_user.bmi})


# ── Profile ───────────────────────────────────────────────────
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.full_name        = request.form.get("full_name", "").strip()
        current_user.age              = int(request.form.get("age", 25))
        current_user.gender           = request.form.get("gender", "")
        current_user.height           = float(request.form.get("height", 170))
        current_user.weight           = float(request.form.get("weight", 70))
        current_user.fitness_goal     = request.form.get("fitness_goal", "general_fitness")
        current_user.activity_level   = request.form.get("activity_level", "moderate")
        current_user.fitness_level    = request.form.get("fitness_level", "beginner")
        current_user.diet_preference  = request.form.get("diet_preference", "vegetarian")
        current_user.equipment        = request.form.get("equipment", "none")
        current_user.workout_duration = int(request.form.get("workout_duration", 30))
        current_user.medical_notes    = request.form.get("medical_notes", "").strip()
        db.session.commit()
        flash("Profile updated successfully! 💪", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html")


# ── API: Stats ────────────────────────────────────────────────
@app.route("/api/stats/progress")
@login_required
def stats_progress():
    days = int(request.args.get("days", 30))
    return jsonify(_chart_data(current_user, days))


# ── Error handlers ────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Internal server error"), 500


# ── CLI: init-db ──────────────────────────────────────────────
@app.cli.command("init-db")
def init_db():
    """Create database tables."""
    with app.app_context():
        db.create_all()
    print("✅ Database initialised.")


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(
        host  = "0.0.0.0",
        port  = int(os.getenv("PORT", 5000)),
        debug = os.getenv("FLASK_DEBUG", "0") == "1",
    )
