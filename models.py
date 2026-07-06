"""
FitPulse — SQLAlchemy Database Models
"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id               = db.Column(db.Integer, primary_key=True)
    username         = db.Column(db.String(80),  unique=True, nullable=False)
    email            = db.Column(db.String(120), unique=True, nullable=False)
    password_hash    = db.Column(db.String(256), nullable=False)
    created_at       = db.Column(db.DateTime,    default=datetime.utcnow)

    # Profile
    full_name        = db.Column(db.String(120), default="")
    age              = db.Column(db.Integer,     default=25)
    gender           = db.Column(db.String(20),  default="")
    height           = db.Column(db.Float,       default=170.0)   # cm
    weight           = db.Column(db.Float,       default=70.0)    # kg
    fitness_goal     = db.Column(db.String(50),  default="general_fitness")
    activity_level   = db.Column(db.String(30),  default="moderate")
    fitness_level    = db.Column(db.String(20),  default="beginner")
    diet_preference  = db.Column(db.String(30),  default="vegetarian")
    equipment        = db.Column(db.String(100), default="none")
    workout_duration = db.Column(db.Integer,     default=30)      # minutes
    medical_notes    = db.Column(db.Text,        default="")
    avatar_url       = db.Column(db.String(256), default="")

    # Relationships
    chat_messages    = db.relationship("ChatMessage",    back_populates="user", cascade="all, delete-orphan")
    workouts         = db.relationship("WorkoutLog",     back_populates="user", cascade="all, delete-orphan")
    nutrition_logs   = db.relationship("NutritionLog",   back_populates="user", cascade="all, delete-orphan")
    habit_logs       = db.relationship("HabitLog",       back_populates="user", cascade="all, delete-orphan")
    weight_logs      = db.relationship("WeightLog",      back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def bmi(self) -> float:
        if self.height and self.weight and self.height > 0:
            h_m = self.height / 100
            return round(self.weight / (h_m * h_m), 1)
        return 0.0

    @property
    def bmi_category(self) -> str:
        b = self.bmi
        if b < 18.5: return "Underweight"
        if b < 25.0: return "Normal weight"
        if b < 30.0: return "Overweight"
        return "Obese"

    @property
    def bmr(self) -> float:
        """Mifflin-St Jeor Equation."""
        if self.gender == "male":
            return round(10 * self.weight + 6.25 * self.height - 5 * self.age + 5, 0)
        return round(10 * self.weight + 6.25 * self.height - 5 * self.age - 161, 0)

    @property
    def tdee(self) -> float:
        """Total Daily Energy Expenditure."""
        multipliers = {
            "sedentary":    1.2,
            "light":        1.375,
            "moderate":     1.55,
            "active":       1.725,
            "very_active":  1.9,
        }
        return round(self.bmr * multipliers.get(self.activity_level, 1.55), 0)

    @property
    def profile_dict(self) -> dict:
        return {
            "name":             self.full_name or self.username,
            "age":              self.age,
            "gender":           self.gender,
            "height":           self.height,
            "weight":           self.weight,
            "bmi":              self.bmi,
            "bmi_category":     self.bmi_category,
            "bmr":              self.bmr,
            "tdee":             self.tdee,
            "fitness_goal":     self.fitness_goal,
            "activity_level":   self.activity_level,
            "fitness_level":    self.fitness_level,
            "diet_preference":  self.diet_preference,
            "equipment":        self.equipment,
            "workout_duration": self.workout_duration,
            "medical_notes":    self.medical_notes,
            "daily_calories":   self.tdee,
        }

    def __repr__(self):
        return f"<User {self.username}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id         = db.Column(db.Integer,   primary_key=True)
    user_id    = db.Column(db.Integer,   db.ForeignKey("users.id"), nullable=False)
    role       = db.Column(db.String(10), nullable=False)   # "user" | "assistant"
    content    = db.Column(db.Text,      nullable=False)
    timestamp  = db.Column(db.DateTime,  default=datetime.utcnow)
    session_id = db.Column(db.String(64), default="default")

    user = db.relationship("User", back_populates="chat_messages")


class WorkoutLog(db.Model):
    __tablename__ = "workout_logs"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date         = db.Column(db.Date,    default=date.today)
    workout_type = db.Column(db.String(50), default="")
    duration     = db.Column(db.Integer, default=0)    # minutes
    calories     = db.Column(db.Integer, default=0)
    notes        = db.Column(db.Text,    default="")
    completed    = db.Column(db.Boolean, default=True)

    user = db.relationship("User", back_populates="workouts")


class NutritionLog(db.Model):
    __tablename__ = "nutrition_logs"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date         = db.Column(db.Date,    default=date.today)
    meal_type    = db.Column(db.String(30), default="")   # breakfast/lunch/dinner/snack
    food_item    = db.Column(db.String(200), default="")
    calories     = db.Column(db.Integer, default=0)
    protein      = db.Column(db.Float,   default=0.0)
    carbs        = db.Column(db.Float,   default=0.0)
    fat          = db.Column(db.Float,   default=0.0)
    water_ml     = db.Column(db.Integer, default=0)

    user = db.relationship("User", back_populates="nutrition_logs")


class HabitLog(db.Model):
    __tablename__ = "habit_logs"

    id         = db.Column(db.Integer,  primary_key=True)
    user_id    = db.Column(db.Integer,  db.ForeignKey("users.id"), nullable=False)
    date       = db.Column(db.Date,     default=date.today)
    habit_name = db.Column(db.String(100), default="")
    completed  = db.Column(db.Boolean,  default=False)
    value      = db.Column(db.Float,    default=0.0)   # e.g. hours slept, glasses of water
    unit       = db.Column(db.String(20), default="")

    user = db.relationship("User", back_populates="habit_logs")


class WeightLog(db.Model):
    __tablename__ = "weight_logs"

    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date    = db.Column(db.Date,    default=date.today)
    weight  = db.Column(db.Float,   nullable=False)
    notes   = db.Column(db.String(200), default="")

    user = db.relationship("User", back_populates="weight_logs")
