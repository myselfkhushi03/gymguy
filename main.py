import json
import os
import random
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import engine, get_db
from utils import validate_input, encrypt_data, decrypt_data, to_fancy_font, check_image_quality, ask_gemini_with_fallback

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FitRoast AI Fitness API", version="1.0")

ROAST_MESSAGES_LATE = [
    "Arre bhai kahan gayab ho? Sone se body nahi banegi!",
    "Itna late reply? Lagta hai workout ki jagah sapne dekh rahe ho.",
    "Bina mehnat ke fat loss chahiye kya? App kholo jaldi!"
]

ROAST_MESSAGES_FORM = [
    "Form bilkul kharab hai, aise exercise karoge toh hospital jaoge!",
    "Yeh kaun sa style hai bhai? Thoda niche jao aur sidhe ho jao.",
    "Form galat hai, aur niche ja varna roast karta rahunga!"
]

class UserOnboardSchema(BaseModel):
    chat_id: str
    name: str
    age: int
    height_cm: float
    current_weight_kg: float
    target_weight_kg: float
    goal: str
    transformation_reason: str

class UserUpdateSchema(BaseModel):
    name: str | None = None
    age: int | None = None
    height_cm: float | None = None
    current_weight_kg: float | None = None
    target_weight_kg: float | None = None
    goal: str | None = None
    transformation_reason: str | None = None

class WorkoutLogSchema(BaseModel):
    chat_id: str
    exercise_name: str
    reps: int
    wrong_form_count: int
    duration_sec: int
    form_feedback: dict

class LateCheckSchema(BaseModel):
    chat_id: str
    last_bot_message_time: str

def handle_validation(field: str, value: any):
    res = validate_input(field, value)
    if not res["valid"]:
        raise HTTPException(
            status_code=400,
            detail=to_fancy_font("Ye valid nahi laga, ek baar sahi se batao")
        )

@app.post("/api/user/onboard")
def onboard_user(payload: UserOnboardSchema, db: Session = Depends(get_db)):
    fields_to_check = {
        "name": payload.name,
        "age": payload.age,
        "height_cm": payload.height_cm,
        "current_weight_kg": payload.current_weight_kg,
        "target_weight_kg": payload.target_weight_kg
    }
    for field, val in fields_to_check.items():
        handle_validation(field, val)

    height_m = payload.height_cm / 100.0
    bmi = round(payload.current_weight_kg / (height_m ** 2), 2)
    encrypted_reason = encrypt_data(payload.transformation_reason)

    user = models.User(
        chat_id=payload.chat_id,
        name=payload.name,
        age=payload.age,
        height_cm=payload.height_cm,
        current_weight_kg=payload.current_weight_kg,
        target_weight_kg=payload.target_weight_kg,
        goal=payload.goal,
        transformation_reason=encrypted_reason,
        bmi=bmi,
        data_encrypted=True
    )

    db.merge(user)
    db.commit()

    return {
        "status": to_fancy_font("Success"),
        "message": to_fancy_font("User onboard ho gaya successfully! 💪"),
        "bmi": bmi,
        "user": {
            "chat_id": user.chat_id,
            "name": to_fancy_font(user.name),
            "goal": user.goal
        }
    }

@app.get("/api/user/{chat_id}")
def get_user_profile(chat_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.chat_id == chat_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=to_fancy_font("User nahi mila!"))
    
    streak_count = db.query(models.Workout).filter(models.Workout.chat_id == chat_id).count()

    return {
        "chat_id": user.chat_id,
        "name": to_fancy_font(user.name),
        "age": user.age,
        "height_cm": user.height_cm,
        "current_weight_kg": user.current_weight_kg,
        "target_weight_kg": user.target_weight_kg,
        "goal": user.goal,
        "transformation_reason": decrypt_data(user.transformation_reason),
        "bmi": user.bmi,
        "streak": f"{streak_count} Days 🔥",
        "fancy_welcome": to_fancy_font(f"Welcome back {user.name}!")
    }

@app.put("/api/user/{chat_id}")
def update_user_profile(chat_id: str, payload: UserUpdateSchema, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.chat_id == chat_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=to_fancy_font("User nahi mila!"))

    data = payload.dict(exclude_unset=True)
    for field, val in data.items():
        if val is not None:
            handle_validation(field, val)
            if field == "transformation_reason":
                setattr(user, field, encrypt_data(val))
            else:
                setattr(user, field, val)

    height_m = user.height_cm / 100.0
    user.bmi = round(user.current_weight_kg / (height_m ** 2), 2)
    user.updated_at = datetime.utcnow()

    db.commit()
    return {"status": to_fancy_font("Profile updated successfully! ✨")}

@app.delete("/api/user/{chat_id}")
def delete_user_data(chat_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.chat_id == chat_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=to_fancy_font("User nahi mila!"))
    
    db.delete(user)
    db.commit()
    return {"status": to_fancy_font("Sara data uda diya gaya hai! 🗑️")}

@app.post("/api/workout/log")
def log_workout(payload: WorkoutLogSchema, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.chat_id == payload.chat_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=to_fancy_font("Pehle onboard toh ho jao!"))

    form_feedback_str = json.dumps(payload.form_feedback)
    workout = models.Workout(
        chat_id=payload.chat_id,
        exercise_name=payload.exercise_name,
        reps=payload.reps,
        wrong_form_count=payload.wrong_form_count,
        duration_sec=payload.duration_sec,
        form_feedback=form_feedback_str
    )
    db.add(workout)
    db.commit()

    roast_or_praise = "Shabash! Form ekdum mast tha! 🎯"
    if payload.wrong_form_count > 0:
        # Optionally use Gemini fallback to generate dynamic savage Hinglish roasts
        ai_prompt = f"Roast a gym user in Hinglish slang for doing wrong form in {payload.exercise_name} with {payload.wrong_form_count} wrong reps."
        gemini_roast = ask_gemini_with_fallback(ai_prompt)
        roast_or_praise = gemini_roast if gemini_roast else random.choice(ROAST_MESSAGES_FORM)

    return {
        "saved": True,
        "feedback": to_fancy_font(roast_or_praise)
    }

@app.post("/api/photo/upload")
async def upload_photo(
    chat_id: str = Form(...),
    photo_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    file_bytes = await file.read()
    is_blurry, is_dark, quality_msg = check_image_quality(file_bytes)

    encrypted_bytes = encrypt_data(file_bytes.hex())
    
    upload_dir = "/tmp/encrypted_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{chat_id}_{datetime.utcnow().timestamp()}.enc"
    
    with open(file_path, "w") as f:
        f.write(encrypted_bytes)

    photo = models.ProgressPhoto(
        chat_id=chat_id,
        photo_type=photo_type,
        file_path_encrypted=file_path,
        is_blurry=is_blurry
    )
    db.add(photo)
    db.commit()

    return {
        "saved": True,
        "quality_feedback": to_fancy_font(quality_msg)
    }

@app.get("/api/plan/{chat_id}")
def generate_diet_plan(chat_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.chat_id == chat_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=to_fancy_font("User nahi mila!"))

    bmr = (10 * user.current_weight_kg) + (6.25 * user.height_cm) - (5 * user.age) + 5
    tdee = bmr * 1.55

    if user.goal == "fat_loss":
        calories = tdee - 500
    elif user.goal in ["muscle_gain", "weight_gain"]:
        calories = tdee + 300
    else:
        calories = tdee

    protein = user.current_weight_kg * 2.0
    fat = (calories * 0.25) / 9
    carbs = (calories - (protein * 4) - (fat * 9)) / 4

    plan_details = {
        "meals": [
            {"meal": "Breakfast", "items": "Oats, Peanut Butter, Banana, 4 Egg whites"},
            {"meal": "Lunch", "items": "Brown Rice, Chicken Breast/Paneer, Salad"},
            {"meal": "Dinner", "items": "Roti, Dal, Mixed Veggies, Curd"}
        ]
    }

    diet_plan_db = models.DietPlan(
        chat_id=chat_id,
        daily_calories=round(calories, 2),
        protein_g=round(protein, 2),
        carbs_g=round(carbs, 2),
        fat_g=round(fat, 2),
        plan_json=json.dumps(plan_details)
    )
    db.merge(diet_plan_db)
    db.commit()

    return {
        "daily_calories": round(calories, 2),
        "protein_g": round(protein, 2),
        "carbs_g": round(carbs, 2),
        "fat_g": round(fat, 2),
        "plan": plan_details,
        "fancy_title": to_fancy_font("Your Custom Diet Plan")
    }

@app.post("/api/roast/check-late")
def check_late_reply(payload: LateCheckSchema):
    try:
        last_time = datetime.fromisoformat(payload.last_bot_message_time)
        diff_mins = (datetime.utcnow() - last_time).total_seconds() / 60.0
    except Exception:
        diff_mins = 0

    roast_msg = "Aap active ho!"
    if diff_mins > 60:
        roast_msg = random.choice(ROAST_MESSAGES_LATE)

    return {
        "badge": to_fancy_font("Dαιʟყ Bσηυѕ"),
        "roast_message": to_fancy_font(roast_msg),
        "minutes_elapsed": round(diff_mins, 1)
    }

@app.get("/api/progress/{chat_id}")
def get_progress(chat_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.chat_id == chat_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=to_fancy_font("User nahi mila!"))

    workouts = db.query(models.Workout).filter(models.Workout.chat_id == chat_id).all()
    photos = db.query(models.ProgressPhoto).filter(models.ProgressPhoto.chat_id == chat_id).all()

    weight_trend = [{"current_weight": user.current_weight_kg, "target": user.target_weight_kg}]
    photo_paths = [{"type": p.photo_type, "path": p.file_path_encrypted, "date": p.date} for p in photos]

    return {
        "weight_graph_data": weight_trend,
        "before_after_photos": photo_paths,
        "total_workouts_logged": len(workouts),
        "fancy_heading": to_fancy_font("Progress Report")
    }
