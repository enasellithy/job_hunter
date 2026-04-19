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

def get_drive_service():
    try:
        service_account_info = json.loads(os.getenv("GDRIVE_SERVICE_ACCOUNT_KEY"))
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, 
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        return build('drive', 'v3', credentials=creds)
    except:
        return None

def get_private_resume(service):
    try:
        request = service.files().export_media(fileId=MY_RESUME_ID, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue().decode('utf-8')
    except:
        return None

def search_jobs():
    query = 'AI Engineer OR "Backend Lead" OR "Software Architect"'
    url = f"https://serpapi.com/search.json?engine=google_jobs&q={query}&hl=en&api_key={SERPAPI_KEY}"
    try:
        response = requests.get(url)
        return response.json().get('jobs_results', [])
    except:
        return []

def analyze_with_ai(job_title, job_desc, resume_text):
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}
    prompt = f"Analyze match between resume and job. Resume: {resume_text[:1000]}. Job: {job_title} - {job_desc}. Provide Arabic report: Match score, Weaknesses, CV tweaks, and Interview advice. If score < 70, start with SKIP."
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
    payload = {
        "content": f"🎯 **Job Found: {title}**",
        "embeds": [{"description": report, "url": link, "color": 15158332}]
    }
    requests.post(DISCORD_WEBHOOK, json=payload)

def main():
    service = get_drive_service()
    if not service: return
    resume = get_private_resume(service)
    if not resume: return
    jobs = search_jobs()
    for job in jobs:
        report = analyze_with_ai(job.get('title'), job.get('description', ''), resume)
        if not report.strip().upper().startswith("SKIP"):
            link = job.get('related_links', [{}])[0].get('link', '')
            send_to_discord(job.get('title'), link, report)

if __name__ == "__main__":
    main()
