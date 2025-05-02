import PyPDF2
import google.generativeai as genai
import json
import re

genai.configure(api_key="AIzaSyAdJ5A4Q-9dAhZe52HB-_1PtrTVlM0Huds")


def extract_text_from_pdf(pdf_path):
    """Extracts text content from a PDF file."""
    try:
        with open(pdf_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
            return text if text.strip() else None
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None


def extract_email(text):
    """Extracts email from text using regex."""
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else None


def extract_phone_number(text):
    """Extracts phone number from text using regex."""
    match = re.search(r"\+?\d{0,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}", text)
    return match.group(0) if match else None


def parse_resume_text(resume_text):
    """Extracts relevant job details from the resume text using generative AI."""
    if not resume_text:
        print("Error: No resume text provided.")
        return None

    prompt = (
        "You are an intelligent and highly accurate resume parser. Carefully read the given resume text and extract ONLY the following details:\n"
        "- Full Name\n"
        "- Email\n"
        "- Phone Number\n"
        "- Skills (as a list of individual skills)\n"
        "- Experience (as a list of objects with 'company' and 'jobTitle').\n"
        "  * IMPORTANT RULES for Experience extraction:\n"
        "    - Include ONLY real professional experiences like internships, part-time jobs, full-time jobs, or freelancing work.\n"
        "    - An experience MUST mention a valid company, organization, or client name.\n"
        "    - There should be an indication of formal work (job title, internship role, freelancing, etc.).\n"
        "    - DO NOT include college clubs, student societies, event participation, hackathons, competitions, academic projects, or volunteering unless it is with a recognized external organization.\n"
        "    - If no valid company or organization is mentioned, DO NOT add it to the experience list.\n"
        "- Education (extract both school and college details separately. For each, include institution name, degree/standard, and marks as percentage or CGPA, if available.)\n\n"
        "Return STRICTLY a valid JSON object matching this schema. DO NOT add any extra fields, text, or explanations outside the JSON object."
    )


    schema = {
        "type": "object",
        "properties": {
            "fullName": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "skills": {"type": "array", "items": {"type": "string"}},
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string"},
                        "jobTitle": {"type": "string"},
                    },
                },
            },
            "education": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "institution": {"type": "string"},
                        "level": {"type": "string"},  # School/College
                        "degree": {"type": "string"},
                        "score": {"type": "string"},  # Percentage or CGPA
                    },
                },
            },
        },
    }

    model = genai.GenerativeModel("gemini-1.5-flash")

    try:
        response = model.generate_content(
            prompt + f"\n\nResume Text:\n{resume_text}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )

        parsed_data = json.loads(response.text)
        parsed_data.setdefault("email", extract_email(resume_text))
        parsed_data.setdefault("phone", extract_phone_number(resume_text))

        if not parsed_data.get("experience"):
            parsed_data["experience"] = []

        if not parsed_data.get("education"):
            parsed_data["education"] = []

        return parsed_data

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print("LLM Response (for debugging):", response.text)
        return {"error": "Invalid JSON from LLM", "raw_response": response.text}
    except Exception as e:
        print(f"Error during LLM processing: {e}")
        return {"error": "LLM processing error", "error_message": str(e)}


def parse_resume(resume_path):
    """Parses a resume PDF and attempts to extract details."""
    resume_text = extract_text_from_pdf(resume_path)
    if resume_text:
        extracted_data = parse_resume_text(resume_text)
        return extracted_data
    else:
        return None

