from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from fastapi.encoders import jsonable_encoder
import os
import random
import shutil
import logging
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime, timezone, timedelta


from app.parser import parse_resume
from app.scrapper import get_all_jobs

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
job_collection = db["user_jobs"]
recommended_jobs_collection = db["recommended_jobs_collection"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserDetails(BaseModel):
    full_name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or replace * with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    return {
        "message": "User registered successfully!",
        "user_id": str(result.inserted_id),
    }


@app.post("/user-login")
async def login(userlogin: UserLogin):
    user = await users_collection.find_one({"email": userlogin.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not pwd_context.verify(userlogin.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    user_id = str(user["_id"])
    resume = await resumes_collection.find_one({"user_id": user_id})

    user_id = str(user["_id"])
    return {
        "message": "Login successful!",
        "user_id": user_id,
        "resume_uploaded": bool(resume),
    }


# @app.post("/parse-resume/")
# async def parse_resume_endpoint(
#     file: UploadFile = File(...),
#     user_email: str = Query(..., description="Registered user's email"),
#     job_role: str = Query(..., description="Desired job role"),
#     location: str = Query(None, description="Preferred job location"),
# ):
#     if file.content_type != "application/pdf":
#         raise HTTPException(status_code=400, detail="Only PDF files are allowed")

#     user = await users_collection.find_one({"email": user_email})
#     if not user:
#         raise HTTPException(
#             status_code=404, detail="User not found. Please register first."
#         )

#     user_id = str(user["_id"])
#     file_path = os.path.join(UPLOAD_DIR, file.filename)
#     try:
#         with open(file_path, "wb") as f:
#             shutil.copyfileobj(file.file, f)
#         logger.info(f"Resume uploaded: {file.filename} by user: {user_email}")
#         parsed_data = parse_resume(file_path)
#         if not parsed_data:
#             logger.error("Failed to parse resume.")
#             return JSONResponse(
#                 status_code=400, content={"error": "Failed to parse resume."}
#             )

#         skills = parsed_data.get("skills", [])
#         experience_data = parsed_data.get("experience", [])
#         if not isinstance(experience_data, list):
#             experience_data = []

#         education = parsed_data.get("education", [])
#         resume_data = {
#             "user_id": (user_id),
#             "full_name": parsed_data.get("fullName", ""),
#             "email": parsed_data.get("email", ""),
#             "phone": parsed_data.get("phone", ""),
#             "skills": skills,
#             "experience": experience_data,
#         }
#         resume_result = await resumes_collection.insert_one(resume_data)
#         resume_id = str(resume_result.inserted_id)
#         logger.info(f"Resume stored in MongoDB. Resume ID: {resume_id}")

#         location = location or parsed_data.get("location", "Remote")
#         logger.info(
#             f"Searching jobs for: Role = {job_role}, Location = {location}, Skills = {', '.join(skills) or 'Not provided'}"
#         )

#         gemini_response = get_all_jobs(job_role, location, skills, experience_data)
#         if not gemini_response:
#             return {
#                 "message": "Resume parsed successfully, but no matching jobs found.",
#                 "resume_id": resume_id,
#             }

#         for job in gemini_response:
#             job["user_id"] = user_id
#             await job_collection.insert_one(job)

#         return {
#             "message": "Resume parsed and matching jobs fetched successfully.",
#             "resume_id": resume_id,
#             "jobs_found": len(gemini_response),
#         }

#     except Exception as e:
#         logger.error(f"Internal Server Error: {e}")
#         return JSONResponse(
#             status_code=500, content={"error": f"Internal server error: {e}"}
#         )


def convert_mongo_obj(doc):
    return {k: str(v) if isinstance(v, ObjectId) else v for k, v in doc.items()}


@app.post("/find-jobs")
async def find_jobs(
    user_id: str = Query(..., description="Registered user's ID"),
    job_role: str = Query(..., description="Desired job role"),
    location: str = Query(None, description="Preferred job location"),
):
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user_present = await users_collection.find_one({"_id": user_obj_id})
    if not user_present:
        raise HTTPException(
            status_code=404, detail="User not found. Please register first."
        )

    resume = await resumes_collection.find_one({"user_id": user_id})
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Parsed resume not found. Please upload and parse your resume first.",
        )

    skills = resume.get("skills", [])
    experience_data = resume.get("experience", [])
    location = location or resume.get("location", "Remote")

    logger.info(
        f"Searching jobs for user_id: {user_id}, Role: {job_role}, "
        f"Location: {location}, Skills: {', '.join(skills) or 'Not provided'}"
    )

    # First, check if the job_role already exists in the recommended_jobs_collection
    existing_jobs = await recommended_jobs_collection.find(
        {"role": {"$regex": f"^{job_role}$", "$options": "i"}}
    ).to_list(length=5)

    if existing_jobs:
        logger.info(f"Found existing recommendations for job role: {job_role}")
        response_content = {
            "message": "Matching jobs fetched from the database.",
            "jobs_found": len(existing_jobs),
            "all_jobs": [convert_mongo_obj(job) for job in existing_jobs],
        }
        return JSONResponse(status_code=200, content=jsonable_encoder(response_content))
        # If not found, call the get_all_jobs function to fetch from external API
    gemini_response = get_all_jobs(job_role, location, skills, experience_data)
    if not gemini_response:
        return JSONResponse(
            status_code=200, content={"message": "No matching jobs found."}
        )

    jobs = []
    for job in gemini_response:
        job["role"] = job_role
        insertion_result = await recommended_jobs_collection.insert_one(job)
        job["_id"] = insertion_result.inserted_id  # Add generated _id
        jobs.append(convert_mongo_obj(job))  # Convert ObjectId to str

    response_content = {
        "message": "Matching jobs fetched and stored successfully.",
        "jobs_found": len(jobs),
        "all_jobs": jobs,
    }
    return JSONResponse(status_code=200, content=jsonable_encoder(response_content))


def clean_obj(obj):
    """
    Recursively converts ObjectId values and other non-serializable items in a structure
    to serializable types (like strings).
    """
    if isinstance(obj, dict):
        return {k: clean_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_obj(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj


@app.post("/scrape-and-store-recommended-jobs")
async def scrape_and_store_recommended_jobs(
    user_id: str = Query(..., description="User ID to fetch resume data"),
    job_role: str = Query(..., description="Desired job role"),
    location: str = Query(None, description="Preferred job location (default: Remote)"),
):
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Validate user
    user = await users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Get parsed resume
    resume = await resumes_collection.find_one({"user_id": user_id})
    if not resume:
        raise HTTPException(status_code=404, detail="Parsed resume not found.")

    # Extract user profile details
    skills = resume.get("skills", [])
    experience_data = resume.get("experience", [])
    location = location or resume.get("location", "Remote")

    logger.info(
        f"Scraping jobs for role={job_role}, location={location}, skills={skills}"
    )

    # Call scraper
    scraped_jobs = get_all_jobs(job_role, location, skills, experience_data)
    if not scraped_jobs:
        return JSONResponse(
            status_code=200, content={"message": "No matching jobs found."}
        )

    stored_jobs = []
    for job in scraped_jobs:
        job["role"] = job_role
        # Insert job into the recommended_jobs_collection
        result = await recommended_jobs_collection.insert_one(job)
        job["_id"] = result.inserted_id  # Add the inserted _id to the job data
        stored_jobs.append(convert_mongo_obj(job))

    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(
            {
                "message": "Jobs scraped and stored successfully in recommended_jobs.",
                "new_jobs_added": len(stored_jobs),
                "sample_jobs": stored_jobs,  # Preview of the first 5 jobs
            }
        ),
    )


def sanitize_job(doc: dict) -> dict:
    """
    Convert MongoDB document so it's JSON serializable:
    - _id → id (str)
    - Any other ObjectId fields → str
    """
    job = doc.copy()
    # Convert the MongoDB _id to a string id
    if "_id" in job:
        job["id"] = str(job.pop("_id"))
    # Convert user_id if it's an ObjectId
    if "user_id" in job and isinstance(job["user_id"], ObjectId):
        job["user_id"] = str(job["user_id"])
    return job


@app.get("/recommended-jobs")
async def get_recommended_jobs_for_user(
    user_id: str = Query(..., description="User ID to fetch recommended jobs")
):
    # 1. Validate user ID
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # 2. Ensure user exists
    user = await users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 3. Load parsed resume (use ObjectId for lookup if that’s how you stored it)
    resume = await resumes_collection.find_one({"user_id": user_id})
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found. Please upload and parse your resume first.",
        )

    # 4. Extract and normalize user skills
    raw_skills = resume.get("skills", [])
    if not isinstance(raw_skills, list):
        raw_skills = []
    user_skills = [s.strip().lower() for s in raw_skills if isinstance(s, str)]

    # 5. Define important matching keywords
    important_keywords = [
        "python",
        "java",
        "javascript",
        "c++",
        "c#",
        "go",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "django",
        "flask",
        "spring",
        "react",
        "angular",
        "vue",
        "node.js",
        "express",
        "laravel",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "devops",
        "terraform",
        "ansible",
        "data analyst",
        "data scientist",
        "machine learning",
        "ml engineer",
        "ai engineer",
        "r",
        "pandas",
        "numpy",
        "tensorflow",
        "pytorch",
        "spark",
        "hadoop",
        "sql",
        "nosql",
        "frontend developer",
        "backend developer",
        "full stack developer",
        "ux/ui designer",
        "qa engineer",
        "qa tester",
        "product manager",
        "project manager",
        "business analyst",
        "cybersecurity",
        "network engineer",
        "security engineer",
    ]

    # 6. Find which important keywords appear in user's skills
    matched_keywords = [
        kw for kw in important_keywords if any(kw in skill for skill in user_skills)
    ]
    if not matched_keywords:
        return JSONResponse(
            status_code=200,
            content={"message": "No relevant job keywords found in user's skills."},
        )

    # 7. Build regex filters on description + title
    regex_filters = [
        {"job_description": {"$regex": kw, "$options": "i"}} for kw in matched_keywords
    ]
    title_filters = [
        {"title": {"$regex": kw, "$options": "i"}} for kw in matched_keywords
    ]

    # 8. Get the list of jobs the user has already applied for
    applied_jobs = await job_collection.find(
        {"user_id": user_id, "is_applied": True}
    ).to_list(length=1000)
    applied_job_ids = {job["_id"] for job in applied_jobs}

    # 9. Find jobs that match the filters but are not applied for
    cursor = recommended_jobs_collection.find(
        {
            "$and": [
                {"$or": regex_filters + title_filters},
                {"_id": {"$nin": list(applied_job_ids)}},
            ]
        }
    )

    # 10. Fetch up to 100 matches, then pick 9 at random
    matched_jobs = await cursor.to_list(length=100)
    if not matched_jobs:
        return JSONResponse(
            status_code=200,
            content={
                "message": "No jobs found matching your key skills or you have already applied for all matching jobs."
            },
        )

    # 11. Randomly select up to 9 and sanitize each one
    selected = random.sample(matched_jobs, min(6, len(matched_jobs)))
    sanitized = [sanitize_job(job) for job in selected]

    # 12. Return recommendations
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(
            {
                "message": "Jobs matched based on your skills.",
                "jobs_returned": len(sanitized),
                "recommended_jobs": sanitized,
            }
        ),
    )


@app.get("/jobs-by-role")
async def jobs_by_role(
    job_role: str = Query(..., description="e.g., Python Developer, ML Engineer")
):
    """
    Fetch up to 5 jobs from recommended_jobs based on job role.
    Tries exact match first, then falls back to partial match (regex).
    """

    # Step 1: Try exact match
    cursor = recommended_jobs_collection.find({"role": job_role}).limit(5)
    jobs = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        jobs.append(doc)

    # Step 2: Fallback to regex match if no exact match
    if not jobs:
        cursor = recommended_jobs_collection.find(
            {"title": {"$regex": job_role, "$options": "i"}}
        ).limit(5)
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            jobs.append(doc)

    # Step 3: Still nothing found
    if not jobs:
        raise HTTPException(
            status_code=404, detail=f"No jobs found for role '{job_role}'"
        )

    # Step 4: Return results
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder(
            {"job_role": job_role, "count": len(jobs), "jobs": jobs}
        ),
    )


@app.post("/get-parse-resume")
async def get_parse_resume(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="Registered user's ID"),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found. Please register first."
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        # Save uploaded file to disk
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"Resume uploaded: {file.filename} by user_id: {user_id}")

        # Parse the resume file
        parsed_data = parse_resume(file_path)
        if not parsed_data:
            return JSONResponse(
                status_code=400, content={"error": "Failed to parse resume."}
            )

        # Extract and clean parsed fields
        skills = parsed_data.get("skills", [])
        experience_data = parsed_data.get("experience", [])
        if not isinstance(experience_data, list):
            experience_data = []
        education = parsed_data.get("education", [])

        resume_data = {
            "user_id": str(user_id),
            "full_name": parsed_data.get("fullName", ""),
            "email": parsed_data.get("email", ""),
            "phone": parsed_data.get("phone", ""),
            "skills": clean_obj(skills),
            "experience": clean_obj(experience_data),
            "education": clean_obj(education),
        }

        # Insert the resume data into MongoDB
        update_result = await resumes_collection.update_one(
            {"user_id": user_id}, {"$set": resume_data}, upsert=True
        )

        await users_collection.update_one(
            {"_id": user_obj_id}, {"$set": {"resume_uploaded": True}}
        )

        if update_result.upserted_id:
            resume_id = str(update_result.upserted_id)
            logger.info(f"Inserted new resume. Resume ID: {resume_id}")
        else:
            existing = await resumes_collection.find_one(
                {"user_id": user_id}, {"_id": 1}
            )
            resume_id = str(existing["_id"])
            logger.info(f"Updated existing resume. Resume ID: {resume_id}")

        # Return a cleaned and serializable response
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(
                {
                    "message": "Resume parsed and saved successfully.",
                    "parsed_data": clean_obj(resume_data),
                }
            ),
        )

    except Exception as e:
        logger.error(f"Error while parsing resume: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/get-all-jobs")
async def get_all_jobs_endpoint(user_id: str):
    try:
        jobs_cursor = job_collection.find(
            {"user_id": user_id}
        )  # Match jobs for this user
        all_jobs = []
        async for job in jobs_cursor:  # Async loop!
            job["_id"] = str(job["_id"])  # Convert ObjectId to str
            all_jobs.append(job)

        if not all_jobs:
            return {"message": "No jobs found"}

        return all_jobs

    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/profile")
async def user_profile(user_id: str):
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        resume = await resumes_collection.find_one({"user_id": user_id})
        if not resume:
            raise HTTPException(
                status_code=404,
                detail="Resume data not found. Please Upload your resume first.",
            )

        profile_data = {
            "user_id": str(user["_id"]),
            "full_name": user.get("full_name", ""),
            "email": user.get("email", ""),
            "phone": resume.get("phone", "Not Provided"),
            "skills": resume.get("skills", []),
            "experience": resume.get("experience", []),
            "education": resume.get("education", []),
        }
        return profile_data

    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.put("/apply-job")
async def apply_job(
    user_id: str = Query(..., description="Registered user's ID"),
    job_id: str = Query(..., description="Job ID to mark as applied"),
):
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Check if the user exists
    user = await users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found. Please register first."
        )

    try:
        job_obj_id = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    # Fetch the job from recommended_jobs_collection
    job = await recommended_jobs_collection.find_one({"_id": job_obj_id})
    if not job:
        raise HTTPException(
            status_code=404, detail="Job not found in recommended jobs."
        )

    # Check if the job already exists for this user and is applied
    existing_job = await job_collection.find_one(
        {"_id": job_obj_id, "user_id": user_id, "is_applied": True}
    )
    if existing_job:
        raise HTTPException(
            status_code=400, detail="Job is already marked as applied for this user."
        )
    IST = timezone(timedelta(hours=5, minutes=30))
    # Capture timestamp
    applied_at = datetime.now(IST).isoformat()  # ISO string in UTC

    # Prepare the document to be inserted
    applied_job_doc = {
        "_id": job_obj_id,
        "user_id": user_id,
        "company": job.get("company"),
        "description": job.get("description"),
        "experience_required": job.get("experience_required"),
        "link": job.get("link"),
        "score": job.get("score"),
        "site": job.get("site"),
        "title": job.get("title"),
        "is_applied": True,  # Mark as applied
        "applied_at": applied_at,  # ← new
    }

    # Insert the job into job_collection
    try:
        insertion_result = await job_collection.insert_one(applied_job_doc)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error inserting job into collection: {str(e)}"
        )

    # Add the inserted job's ObjectId to the response document
    applied_job_doc["_id"] = str(
        insertion_result.inserted_id
    )  # Ensure ObjectId is converted to string

    return JSONResponse(
        status_code=200,
        content={
            "message": "Job successfully marked as applied.",
            "job": applied_job_doc,
        },
    )


@app.get("/applied-jobs")
async def get_applied_jobs(
    user_id: str = Query(..., description="Registered user's ID")
):
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = await users_collection.find_one({"_id": user_obj_id})
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found. Please register first."
        )

    jobs_cursor = job_collection.find({"user_id": user_id, "is_applied": True})
    applied_jobs = []
    async for job in jobs_cursor:
        job["_id"] = str(job["_id"])
        applied_jobs.append(job)

    return JSONResponse(
        status_code=200, content=jsonable_encoder({"applied_jobs": applied_jobs})
    )


@app.get("/")
async def root():
    return {"message": "Welcome to the resume parser API!"}
