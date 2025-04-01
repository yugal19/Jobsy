
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
import os
import shutil
import logging
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from app.parser import parse_resume  # Resume parsing function
from app.scrapper import get_all_jobs  # Scraper function (job search and ranking)

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MONGO_URI = "mongodb+srv://yugal19:MinorProject@project1.eh0gg.mongodb.net/"
DB_NAME = "resume_parser_db"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db["user"]
resumes_collection = db["parse_resume"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserDetails(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    
    
@app.post("/user-register")
async def register(user_details: UserDetails):
    existing_user = await users_collection.find_one({"email": user_details.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = pwd_context.hash(user_details.password)
    user_info = {
        "full_name": user_details.full_name,
        "email": user_details.email,
        "password": hashed_password,
    }
    result = await users_collection.insert_one(user_info)
    return {"message": "User registered successfully!", "user_id": str(result.inserted_id)}

@app.post("/parse-resume/")
async def parse_resume_endpoint(
    file: UploadFile = File(...),
    user_email: str = Query(..., description="Registered user's email"),
    job_role: str = Query(..., description="Desired job role"),
    location: str = Query(None, description="Preferred job location")
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    user = await users_collection.find_one({"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    user_id = str(user["_id"])
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"Resume uploaded: {file.filename} by user: {user_email}")
        parsed_data = parse_resume(file_path)
        if not parsed_data:
            logger.error("Failed to parse resume.")
            return JSONResponse(status_code=400, content={"error": "Failed to parse resume."})
        
        skills = parsed_data.get("skills", [])
        experience_data = parsed_data.get("experience", [])
        if not isinstance(experience_data, list):
            experience_data = []

        resume_data = {
            "user_id": user_id,
            "full_name": parsed_data.get("fullName", ""),
            "email": parsed_data.get("email", ""),
            "phone": parsed_data.get("phone", ""),
            "skills": skills,
            "experience": experience_data,
        }
        resume_result = await resumes_collection.insert_one(resume_data)
        resume_id = str(resume_result.inserted_id)
        logger.info(f"Resume stored in MongoDB. Resume ID: {resume_id}")
        
        location = location or parsed_data.get("location", "Remote")
        logger.info(f"Searching jobs for: Role = {job_role}, Location = {location}, Skills = {', '.join(skills) or 'Not provided'}")
        
        # Get ranked jobs and raw Gemini API response
        gemini_response = get_all_jobs(job_role, location, skills, experience_data)
        if not gemini_response:
            return {"message": "Resume parsed successfully, but no matching jobs found.", "resume_id": resume_id}
        return {"gemini_api_response": gemini_response}
    
    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        return JSONResponse(status_code=500, content={"error": f"Internal server error: {e}"})

@app.get("/")
async def root():
    return {"message": "Welcome to the resume parser API!"}
