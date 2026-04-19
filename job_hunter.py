import os
import json
import requests
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

MY_RESUME_ID = "1hV2Jlp9aCU64w-QP9qtwPot6XC7O88SNT6rDI-HJiAE"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def get_drive_service():
    service_account_info = json.loads(os.getenv("GDRIVE_SERVICE_ACCOUNT_KEY"))
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, 
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

def get_private_resume(service):
    try:
        request = service.files().export_media(fileId=MY_RESUME_ID, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue().decode('utf-8')
    except Exception as e:
        print(f"Error reading Drive: {e}")
        return None

def update_resume_in_drive(service, new_content):
    """This function updates your Word doc with AI-optimized text"""
    try:
        media = MediaIoBaseUpload(io.BytesIO(new_content.encode('utf-8')), mimetype='text/plain')
        service.files().update(fileId=MY_RESUME_ID, media_body=media).execute()
        print("✅ Resume updated in Google Drive with optimized keywords.")
    except Exception as e:
        print(f"Error updating Drive: {e}")

def search_jobs():
    query = 'AI Engineer OR "Backend Lead" OR "Software Architect"'
    url = f"https://serpapi.com/search.json?engine=google_jobs&q={query}&hl=en&api_key={SERPAPI_KEY}"
    try:
        response = requests.get(url)
        return response.json().get('jobs_results', [])
    except: return []

def analyze_with_ai(job_title, job_desc, resume_text):
    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {CEREBRAS_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Compare this job to the candidate's resume:
    RESUME: {resume_text}
    JOB: {job_title} - {job_desc}
    
    Return a JSON with:
    1. "report": Full Arabic report (Match score, weaknesses, advice).
    2. "status": "SKIP" if match < 75 else "PROCEED".
    3. "optimized_bio": A 2-line professional summary tailored for THIS job to be inserted in the CV.
    """
    
    data = {
        "model": "llama3.1-8b",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    
    try:
        res = requests.post(url, headers=headers, json=data)
        return res.json()['choices'][0]['message']['content']
    except: return None

def send_to_discord(title, link, report):
    payload = {
        "content": f"🎯 **New High-Match Job: {title}**",
        "embeds": [{"description": report, "url": link, "color": 15158332}]
    }
    requests.post(DISCORD_WEBHOOK, json=payload)

def main():
    print("--- Job Hunter Bot Starting ---")
    service = get_drive_service()
    resume = get_private_resume(service)
    if not resume: return
    
    jobs = search_jobs()
    for job in jobs:
        title = job.get('title', 'Unknown')
        print(f"Processing: {title}")
        
        raw_analysis = analyze_with_ai(title, job.get('description', ''), resume)
        if not raw_analysis: continue
        
        analysis = json.loads(raw_analysis)
        if analysis.get("status") == "PROCEED":
            # 1. Update the CV with optimized bio
            # update_resume_in_drive(service, analysis['optimized_bio'] + "\n" + resume)
            
            # 2. Notify Discord
            link = job.get('related_links', [{}])[0].get('link', '')
            send_to_discord(title, link, analysis['report'])
            print(f"✅ Success for {title}")

if __name__ == "__main__":
    main()
