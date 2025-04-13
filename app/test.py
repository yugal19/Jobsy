@app.post("/parse-resume/")
async def parse_resume_endpoint(
    file: UploadFile = File(...),
    user_email: str = Query(..., description="Registered user's email"),
    job_role: str = Query(..., description="Desired job role"),
    location: str = Query(None, description="Preferred job location"),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    user = await users_collection.find_one({"email": user_email})
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found. Please register first."
        )

    user_id = str(user["_id"])
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"Resume uploaded: {file.filename} by user: {user_email}")
        parsed_data = parse_resume(file_path)
        if not parsed_data:
            logger.error("Failed to parse resume.")
            return JSONResponse(
                status_code=400, content={"error": "Failed to parse resume."}
            )

        skills = parsed_data.get("skills", [])
        experience_data = parsed_data.get("experience", [])
        if not isinstance(experience_data, list):
            experience_data = []

        education = parsed_data.get("education", [])
        resume_data = {
            "user_id": (user_id),
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
        logger.info(
            f"Searching jobs for: Role = {job_role}, Location = {location}, Skills = {', '.join(skills) or 'Not provided'}"
        )

        gemini_response = get_all_jobs(job_role, location, skills, experience_data)
        if not gemini_response:
            return {
                "message": "Resume parsed successfully, but no matching jobs found.",
                "resume_id": resume_id,
            }

        for job in gemini_response:
            job["user_id"] = user_id
            await job_collection.insert_one(job)

        return {
            "message": "Resume parsed and matching jobs fetched successfully.",
            "resume_id": resume_id,
            "jobs_found": len(gemini_response),
        }

    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        return JSONResponse(
            status_code=500, content={"error": f"Internal server error: {e}"}
        )

