import json
import time
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configure Gemini API
genai.configure(api_key="AIzaSyAdJ5A4Q-9dAhZe52HB-_1PtrTVlM0Huds")  # Replace with your actual key

def setup_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)

def scrape_linkedin(driver, job_role, location, max_jobs=10):
    url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(job_role)}&location={urllib.parse.quote(location)}"
    driver.get(url)
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    jobs = []
    for card in soup.find_all("div", class_="base-search-card")[:max_jobs]:
        title_elem = card.find("h3", class_="base-search-card__title")
        company_elem = card.find("h4", class_="base-search-card__subtitle")
        link_elem = card.find("a", class_="base-card__full-link")
        if title_elem and company_elem and link_elem:
            jobs.append({
                "title": title_elem.get_text(strip=True),
                "company": company_elem.get_text(strip=True),
                "link": link_elem.get("href"),
                "description": "",  # To be updated with extracted keywords
                "site": "linkedin"
            })
    return jobs

def scrape_naukri(driver, job_role, location, skills, max_jobs=10):
    job_role_hyphen = job_role.lower().replace(" ", "-")
    job_role_encoded = urllib.parse.quote(job_role)
    location_encoded = urllib.parse.quote(location) if location else ""
    base_url = f"https://www.naukri.com/{job_role_hyphen}-jobs?k={job_role_encoded}&l={location_encoded}"
    driver.get(base_url)
    time.sleep(7)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    jobs = []
    job_cards = soup.find_all("article", class_="jobTuple") or soup.find_all("div", class_="srp-jobtuple-wrapper")
    for card in job_cards[:max_jobs]:
        title_elem = card.find("a", class_="title")
        if not title_elem:
            continue
        job_title = title_elem.get_text(strip=True)
        link = title_elem.get("href")
        company_elem = card.find("a", class_="comp-name")
        company = company_elem.get_text(strip=True) if company_elem else "N/A"
        jobs.append({
            "title": job_title,
            "company": company,
            "link": link,
            "description": "",  # To be updated with extracted keywords
            "site": "naukri"
        })
    return jobs

def get_job_description(driver, job_link, site):
    driver.get(job_link)
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    full_description = "Description not found"
    if site == "linkedin":
        desc_elem = soup.find("div", class_="description__text")
        if not desc_elem:
            desc_elem = soup.find("div", class_="show-more-less-html__markup")
    elif site == "naukri":
        desc_elem = soup.find("div", class_="job-description")
    else:
        desc_elem = soup.find("div", class_="job-description")
    if desc_elem:
        full_description = desc_elem.get_text(separator=" ", strip=True)
    return full_description

def extract_tech_keywords(text):
    tech_keywords_list = [
        "Python", "Django", "Flask", "REST", "API", "JavaScript", "React",
        "Node.js", "Angular", "Vue", "AWS", "Azure", "GCP", "Docker", "Kubernetes",
        "SQL", "NoSQL", "Machine Learning", "Deep Learning", "Data Science", "Java", "C++"
    ]
    found = []
    lower_text = text.lower()
    for keyword in tech_keywords_list:
        if keyword.lower() in lower_text:
            found.append(keyword)
    return ", ".join(list(set(found)))

def update_jobs_with_descriptions(driver, jobs):
    for job in jobs:
        print(f"Fetching description for job: {job['title']} at {job['company']}")
        full_desc = get_job_description(driver, job["link"], job["site"])
        job["description"] = extract_tech_keywords(full_desc)
    return jobs

def rank_jobs_with_gemini(resume_text, jobs):
    prompt = f"""
You are an AI assistant helping a job seeker find the most relevant job opportunities based on their resume.

### Resume:
{resume_text}

### Job Listings:
{json.dumps(jobs, indent=4)}

Each job listing has an extracted set of technical keywords in its "description" field.
Compare these keywords with the candidate's skills and experience.
For each job, assign a match score between 0 and 100 (100 means a perfect match).
Then, select exactly 5 jobs total with the condition that exactly 3 come from LinkedIn and exactly 2 come from Naukri.
Rank these selected jobs from most relevant (highest score) to least relevant.

**Output Format:**  
Return a valid JSON list of dictionaries, where each dictionary contains:
"title", "company", "link", "description", "site", and "score".  
Do not include any additional text.
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                # Optionally include response_schema here as needed.
            )
        )
        raw_response = response.text
        print("Gemini API Raw Response:", raw_response)
        # Parse the raw_response to a Python object.
        try:
            parsed_gemini_response = json.loads(raw_response)
        except Exception as parse_error:
            print("Parsing error:", parse_error)
            parsed_gemini_response = None

        try:
            ranked_jobs = json.loads(raw_response)
        except Exception:
            ranked_jobs = jobs  # fallback if parsing fails

        # Enforce filtering to get exactly 3 LinkedIn and 2 Naukri jobs.
        def filter_top_jobs(jobs_list):
            linkedin_jobs = [job for job in jobs_list if job.get("site") == "linkedin"]
            naukri_jobs = [job for job in jobs_list if job.get("site") == "naukri"]
            linkedin_sorted = sorted(linkedin_jobs, key=lambda x: x.get("score", 0), reverse=True)[:3]
            naukri_sorted = sorted(naukri_jobs, key=lambda x: x.get("score", 0), reverse=True)[:2]
            return linkedin_sorted + naukri_sorted

        if not (len(ranked_jobs) == 5 and 
                sum(1 for job in ranked_jobs if job.get("site") == "linkedin") == 3 and 
                sum(1 for job in ranked_jobs if job.get("site") == "naukri") == 2):
            ranked_jobs = filter_top_jobs(ranked_jobs)

        # Instead of returning the raw string, return the parsed JSON.
        return ranked_jobs, parsed_gemini_response
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return jobs, f"Error: {e}"


def get_all_jobs(job_role, location, skills, experience):
    driver = setup_driver()
    print("Scraping LinkedIn...")
    linkedin_jobs = scrape_linkedin(driver, job_role, location, max_jobs=10)
    print(f"Found {len(linkedin_jobs)} jobs on LinkedIn.")
    print("Scraping Naukri...")
    naukri_jobs = scrape_naukri(driver, job_role, location, skills, max_jobs=10)
    print(f"Found {len(naukri_jobs)} jobs on Naukri.")
    all_jobs = linkedin_jobs + naukri_jobs
    all_jobs = update_jobs_with_descriptions(driver, all_jobs)
    driver.quit()
    if not all_jobs:
        return [], "No jobs found."
    resume_text = f"Skills: {', '.join(skills)}. Experience: {experience}. Looking for a {job_role} role in {location}."
    ranked_jobs, gemini_response = rank_jobs_with_gemini(resume_text, all_jobs)
    return gemini_response
