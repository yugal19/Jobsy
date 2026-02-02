# 🚀 Jobsy — AI Powered Resume-Aware Job Matcher

**Jobsy** is an intelligent job search and ranking system that automatically scrapes the latest job postings from platforms like LinkedIn and Naukri, parses a user’s resume, and ranks jobs based on skill and experience relevance.

Instead of manually scrolling through hundreds of job posts, Jobsy brings the **most relevant jobs to the top** using resume-aware scoring.

---

## 🧠 Problem It Solves

Job portals show thousands of jobs, but:

- They are not personalized to your resume
- Filtering is keyword based, not skill/experience aware
- You manually open and check each job description

**Jobsy automates this entire flow.**

You upload your resume → Jobsy understands your skills & experience → scrapes latest jobs → scores and ranks them for you.

---

## ⚙️ Complete Flow

User Resume (PDF)
↓
Resume Parsing (skills, experience extraction)
↓
Live Job Scraping (LinkedIn, Naukri)
↓
Job Description Parsing
↓
Similarity + Scoring Algorithm
↓
Ranked Job List with Match Score


---

## 🧩 Project Structure
```
├── app/
│ ├── init.py
│ ├── test.py
│ ├── parser.py
│ ├── scrapper.py
│ └── main.py
├── uploads/
├── requirements.txt
├── README.md
└── .gitignore

```
---

## 🔍 Core Modules

### `scrapper.py`

- Scrapes latest job postings from LinkedIn and Naukri
- Extracts job title, company, description, skills, and experience

### `parser.py`

- Parses uploaded resume (PDF)
- Extracts skills, experience, and important keywords
- Parses job descriptions for fair comparison

### `main.py`

- Connects the complete pipeline
- Applies scoring logic between resume and job post
- Ranks jobs by relevance score

---

## 🧮 How Scoring Works

Jobsy performs **skill-aware matching**, not simple keyword matching.

Score is based on:

- Skill overlap
- Experience relevance
- Keyword similarity
- Context similarity between resume and job description

Higher score → Better match → Ranked higher.

---

## 🛠️ Tech Stack

- Python (FastAPI)
- Gemini API (LLM integration)
- BeautifulSoup / Requests (Web Scraping)
- PDF Parsing
- Text Processing & NLP Techniques

---

## ▶️ How to Run

### 1️⃣ Install dependencies

```bash
pip install -r requirements.txt
2️⃣ Add your resume
Place your resume inside the uploads/ folder.

3️⃣ Run the project
python app/main.py
4️⃣ Enter the job role when prompted
Jobsy will output ranked jobs with match scores.

📌 Example Output
1. Backend Developer — Flipkart — Match Score: 87%
2. Python Engineer — Razorpay — Match Score: 82%
