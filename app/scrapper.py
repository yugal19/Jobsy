import json
import time
import re
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configure Gemini API
genai.configure(
    api_key="AIzaSyAdJ5A4Q-9dAhZe52HB-_1PtrTVlM0Huds"
)  # Replace with your actual key


def setup_driver(headless=True):
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")
    if headless:
        options.add_argument("--headless=new")  # new headless mode

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})
    return driver


def scrape_linkedin(driver, job_role, location, skills, max_jobs=4):
    """Scrape LinkedIn jobs ensuring all company names are unique"""
    try:
        url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(job_role)}&location={urllib.parse.quote(location)}"
        driver.get(url)
        time.sleep(5)  # Initial load wait

        # Scroll to load more jobs
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        jobs = []
        seen_companies = set()  # Track companies we've already added

        # Multiple selector patterns for job cards
        job_cards = (
            soup.select("div.base-search-card")
            or soup.select("li.jobs-search-results__list-item")
            or soup.select("div.job-card-container")
        )

        for card in job_cards:
            try:
                # Extract company name with multiple selector options
                company_elem = (
                    card.select_one("h4.base-search-card__subtitle a")
                    or card.select_one("a.job-card-container__company-name")
                    or card.select_one("a.hidden-nested-link")
                )

                if not company_elem:
                    continue

                company = company_elem.get_text(strip=True)

                # Skip if we already have this company
                if company in seen_companies:
                    continue

                seen_companies.add(company)  # Mark company as seen

                # Extract other job details
                title_elem = card.select_one(
                    "h3.base-search-card__title"
                ) or card.select_one("a.job-card-list__title")
                title = title_elem.get_text(strip=True) if title_elem else "N/A"

                link_elem = card.select_one(
                    "a.base-card__full-link"
                ) or card.select_one("a.job-card-container__link")
                link = link_elem.get("href", "").split("?")[0] if link_elem else "N/A"

                # Build job record
                jobs.append(
                    {
                        "title": title,
                        "company": company,
                        "link": link,
                        "description": "",
                        "experience_required": "",
                        "site": "linkedin",
                    }
                )

                # Stop when we have enough unique jobs
                if len(jobs) >= max_jobs:
                    break

            except Exception as e:
                print(f"Error processing job card: {e}")
                continue

        return jobs

    except Exception as e:
        print(f"LinkedIn scraping failed: {e}")
        return []


def scrape_naukri(driver, job_role, location, skills, max_jobs=4):
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
    job_cards = soup.find_all("article", class_="jobTuple") or soup.find_all(
        "div", class_="srp-jobtuple-wrapper"
    )
    for card in job_cards[:max_jobs]:
        title_elem = card.find("a", class_="title")
        if not title_elem:
            continue
        job_title = title_elem.get_text(strip=True)
        link = title_elem.get("href")
        company_elem = card.find("a", class_="comp-name")
        company = company_elem.get_text(strip=True) if company_elem else "N/A"
        jobs.append(
            {
                "title": job_title,
                "company": company,
                "link": link,
                "description": "",  # extracted tech keywords
                "experience_required": "",  # extracted experience requirement
                "site": "naukri",
            }
        )
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
        # Try multiple selectors for Naukri job pages, including the new class
        desc_elem = soup.find("div", class_="job-description")
        if not desc_elem:
            desc_elem = soup.find("div", class_="jdSection")
        if not desc_elem:
            desc_elem = soup.find("div", id="jobDescriptionText")
        if not desc_elem:
            desc_elem = soup.find("section", class_="styles_job-desc-container__txpYf")
    else:
        desc_elem = soup.find("div", class_="job-description")

    if desc_elem:
        full_description = desc_elem.get_text(separator=" ", strip=True)

    return full_description


def extract_tech_keywords(text):
    """
    Enhanced tech keyword extraction with:
    - Comprehensive keyword list
    - Better matching (whole word matching)
    """
    if not text or not isinstance(text, str):
        return {}

    tech_keywords = {
        "Programming Languages": [
            "Python",
            "Java",
            "JavaScript",
            "C++",
            "C#",
            "Go",
            "Rust",
            "TypeScript",
            "Swift",
            "Kotlin",
        ],
        "Web Development": [
            "HTML",
            "CSS",
            "React",
            "Angular",
            "Vue",
            "Django",
            "Flask",
            "Node.js",
            "Express",
            "Spring",
        ],
        "Cloud/DevOps": [
            "AWS",
            "Azure",
            "GCP",
            "Docker",
            "Kubernetes",
            "Terraform",
            "CI/CD",
            "Jenkins",
            "Ansible",
        ],
        "Data": [
            "SQL",
            "NoSQL",
            "MySQL",
            "PostgreSQL",
            "MongoDB",
            "Redis",
            "Data Science",
            "Machine Learning",
            "Deep Learning",
            "TensorFlow",
            "PyTorch",
        ],
        "APIs": ["REST", "GraphQL", "gRPC", "API", "Microservices"],
        "Other": [
            "Git",
            "Linux",
            "Agile",
            "Scrum",
            "JIRA",
            "VS Code",
            "GitHub",
            "Data Structures",
            "Algorithms",
            "OOPs",
            "Employee Management System",
            "IOT Based Smart Shopping Cart",
            "Backend Developer",
            "FastAPI"
        ]
    }

    found_keywords = set()
    lower_text = text.lower()

    for keywords in tech_keywords.values():
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword.lower()) + r"\b", lower_text):
                found_keywords.add(keyword)

    # Convert to sorted list
    found_keywords = sorted(list(found_keywords))

    # Format the output as index-key format
    formatted_output = {index: keyword for index, keyword in enumerate(found_keywords)}

    return formatted_output if formatted_output else {}



def extract_experience(text):
    """
    Look for patterns like 'X years', 'X-Y years', or 'minimum X years'
    """
    pattern = r"(\d+\s*(\+|to|-)?\s*\d*\s*years?)"
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    experiences = [match[0].strip() for match in matches]
    return ", ".join(set(experiences)) if experiences else "Not specified"


def update_jobs_with_descriptions(driver, jobs):
    for job in jobs:
        print(f"Fetching description for job: {job['title']} at {job['company']}")
        full_desc = get_job_description(driver, job["link"], job["site"])
        job["description"] = extract_tech_keywords(full_desc)
        job["experience_required"] = extract_experience(full_desc)
    return jobs


def rank_jobs_with_gemini(resume_text, jobs):
    # Define the JSON schema for the expected response
    response_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "company": {"type": "string"},
                "link": {"type": "string"},
                "description": {"type": "string"},
                "experience_required": {"type": "string"},
                "site": {"type": "string"},
                "score": {"type": "number"},
            },
            "required": [
                "title",
                "company",
                "link",
                "description",
                "experience_required",
                "site",
                "score",
            ],
        },
    }

    prompt = f"""
You are an AI assistant helping a job seeker find the most relevant job opportunities based on their resume.

### Resume:
{resume_text}

### Job Listings:
{json.dumps(jobs, indent=4)}

Each job listing contains two key details:
- "description": Technical keywords extracted from the job description.
- "experience_required": The experience requirements extracted from the description.

*Scoring Instructions:*
Compare the candidate's skills and experience with each job's details.
Assign each job a match score between 0 and 100 (where 100 means a perfect match).
And also that minimum score assigned to any job must be 50 that is i want that each job post should have greater then equal to 50 score.
The score should reflect how well the job's technical keywords and experience requirements align with the candidate's skills and experience.
For example, if the candidate's resume shows all the skills and the required experience is met or exceeded, the score should be close to 100. Lower scores indicate a weaker match.

Then, select exactly 5 jobs total with the condition that exactly 3 come from LinkedIn and exactly 2 come from Naukri.
Rank these selected jobs from most relevant (highest score) to least relevant.

*Output Format:*  
Return a valid JSON list of dictionaries following the provided schema.
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json", response_schema=response_schema
            ),
        )
        raw_response = response.text
        print("Gemini API Raw Response:", raw_response)
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
            linkedin_sorted = sorted(
                linkedin_jobs, key=lambda x: x.get("score", 0), reverse=True
            )[:3]
            naukri_sorted = sorted(
                naukri_jobs, key=lambda x: x.get("score", 0), reverse=True
            )[:2]
            return linkedin_sorted + naukri_sorted

        if not (
            len(ranked_jobs) == 5
            and sum(1 for job in ranked_jobs if job.get("site") == "linkedin") == 3
            and sum(1 for job in ranked_jobs if job.get("site") == "naukri") == 2
        ):
            ranked_jobs = filter_top_jobs(ranked_jobs)

        return ranked_jobs, parsed_gemini_response
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return jobs, f"Error: {e}"


def get_all_jobs(job_role, location, skills, experience):
    driver = setup_driver()
    print("Scraping LinkedIn...")
    linkedin_jobs = scrape_linkedin(driver, job_role, location, skills, max_jobs=10)
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
