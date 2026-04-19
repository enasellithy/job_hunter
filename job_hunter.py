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
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

def get_private_resume(service):
    print("Reading resume from Drive...")
    try:
        request = service.files().export_media(fileId=MY_RESUME_ID, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        content = fh.getvalue().decode('utf-8')
        print(f"Resume loaded ({len(content)} chars)")
        return content
    except Exception as e:
        print(f"Drive Error: {e}")
        return None

def search_jobs():
    print("Searching for jobs...")
    query = 'Backend Lead OR "AI Engineer" OR "Software Architect"'
    url = f"https://serpapi.com/search.json?engine=google_jobs&q={query}&hl=en&api_key={SERPAPI_KEY}"
    try:
        response = requests.get(url)
        jobs = response.json().get('jobs_results', [])
        print(f"Found {len(jobs)} jobs.")
        return jobs
    except Exception as e:
        print(f"Search Error: {e}")
        return []

def analyze_with_ai(job_title, job_desc, resume_text):
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"Analyze job match. Resume: {resume_text[:1500]}. Job: {job_title}. Report in Arabic. Include Match Score. If match < 50 start with SKIP."
    
    data = {
        "model": "llama3.1-8b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        res = requests.post(url, headers=headers, json=data)
        return res.json()['choices'][0]['message']['content']
    except: return "SKIP"

def send_to_discord(title, link, report):
    payload = {
        "content": f"🎯 **Job Match Found: {title}**",
        "embeds": [{"description": report, "url": link, "color": 15158332}]
    }
    r = requests.post(DISCORD_WEBHOOK, json=payload)
    print(f"Discord Response: {r.status_code}")

def main():
    print("--- Execution Started ---")
    
    requests.post(DISCORD_WEBHOOK, json={"content": "🚀 AI Job Hunter is now running and searching..."})
    
    service = get_drive_service()
    if not service: return
    
    resume = get_private_resume(service)
    if not resume: return
    
    jobs = search_jobs()
    for job in jobs:
        title = job.get('title', 'Unknown')
        print(f"Analyzing: {title}")
        report = analyze_with_ai(title, job.get('description', ''), resume)
        
        if "SKIP" not in report.upper():
            link = job.get('related_links', [{}])[0].get('link', '')
            send_to_discord(title, link, report)
        else:
            print(f"Skipped: {title}")

if __name__ == "__main__":
    main()
