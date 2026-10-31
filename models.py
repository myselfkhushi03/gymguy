from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    chat_id = Column(String, primary_key=True, index=True)
    name = Column(String(20), nullable=False)
    age = Column(Integer, nullable=False)
    height_cm = Column(Float, nullable=False)
    current_weight_kg = Column(Float, nullable=False)
    target_weight_kg = Column(Float, nullable=False)
    goal = Column(String, nullable=False)
    transformation_reason = Column(Text, nullable=True)
    bmi = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    data_encrypted = Column(Boolean, default=True)

    workouts = relationship("Workout", back_populates="user", cascade="all, delete-orphan")
    photos = relationship("ProgressPhoto", back_populates="user", cascade="all, delete-orphan")
    diet_plan = relationship("DietPlan", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_id = Column(String, ForeignKey("users.chat_id"), nullable=False)
    exercise_name = Column(String, nullable=False)
    reps = Column(Integer, nullable=False)
    wrong_form_count = Column(Integer, default=0)
    duration_sec = Column(Integer, nullable=False)
    form_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="workouts")

class ProgressPhoto(Base):
    __tablename__ = "progress_photos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_id = Column(String, ForeignKey("users.chat_id"), nullable=False)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    photo_type = Column(String, nullable=False)
    file_path_encrypted = Column(String, nullable=False)
    is_blurry = Column(Boolean, default=False)

    user = relationship("User", back_populates="photos")

class DietPlan(Base):
    __tablename__ = "diet_plans"

    chat_id = Column(String, ForeignKey("users.chat_id"), primary_key=True)
    daily_calories = Column(Float, nullable=False)
    protein_g = Column(Float, nullable=False)
    carbs_g = Column(Float, nullable=False)
    fat_g = Column(Float, nullable=False)
    plan_json = Column(Text, nullable=False)

    user = relationship("User", back_populates="diet_plan")
