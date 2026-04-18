import os
import json
import requests
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

MY_RESUME_ID = os.getenv("RESUME_FILE_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def get_private_resume():
    try:
        service_account_info = json.loads(os.getenv("GDRIVE_SERVICE_ACCOUNT_KEY"))
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, 
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=creds)
        
        request = service.files().export_media(fileId=MY_RESUME_ID, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue().decode('utf-8')
    except Exception as e:
        print(f"Error: {e}")
        return None

def search_jobs():
    query = 'site:linkedin.com/jobs "Staff AI" OR "AI Architect" OR "Backend Lead"'
    url = f"https://serpapi.com/search.json?engine=google_jobs&q={query}&hl=en&api_key={SERPAPI_KEY}"
    try:
        response = requests.get(url)
        return response.json().get('jobs_results', [])
    except:
        return []

def analyze_with_ai(job_title, job_desc, resume_text):
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Compare this job to the candidate's resume.
    
    RESUME:
    {resume_text}
    
    JOB: {job_title}
    DESCRIPTION: {job_desc}
    
    Provide a detailed report including:
    1. Match Score (0-100).
    2. Weaknesses: Specific skills or keywords missing from the resume for this role.
    3. CV Tweaks: Exact phrases or projects to add to the Word document to pass ATS.
    4. Interview Advice: A tough technical question based on the candidate's specific gaps.
    
    If match score is below 75, start the response with 'SKIP'.
    """
    
    data = {
        "model": "llama3.1-8b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        res = requests.post(url, headers=headers, json=data)
        return res.json()['choices'][0]['message']['content']
    except:
        return "SKIP"

def send_to_discord(title, link, report):
    if "SKIP" in report: return
    payload = {
        "content": f"🎯 **New High-Match Job Found: {title}**",
        "embeds": [{"description": report, "url": link, "color": 15158332}]
    }
    requests.post(DISCORD_WEBHOOK, json=payload)

def main():
    resume = get_private_resume()
    if not resume: return
    
    jobs = search_jobs()
    for job in jobs:
        report = analyze_with_ai(job['title'], job.get('description', ''), resume)
        if "SKIP" not in report:
            send_to_discord(job['title'], job.get('related_links', [{}])[0].get('link', ''), report)

if __name__ == "__main__":
    main()
