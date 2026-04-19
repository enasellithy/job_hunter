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
    print("Checking Google Drive for resume...")
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
        
        content = fh.getvalue().decode('utf-8')
        print(f"Successfully loaded resume. Size: {len(content)} characters.")
        return content
    except Exception as e:
        print(f"Error accessing Google Drive: {e}")
        return None

def search_jobs():
    print("Searching for jobs via SerpApi...")
    # Expanded query to find more results
    query = 'AI Engineer OR "Backend Lead" OR "Software Architect" OR "Python Developer"'
    url = f"https://serpapi.com/search.json?engine=google_jobs&q={query}&hl=en&api_key={SERPAPI_KEY}"
    try:
        response = requests.get(url)
        jobs = response.json().get('jobs_results', [])
        print(f"Found {len(jobs)} total jobs from search.")
        return jobs
    except Exception as e:
        print(f"Error searching jobs: {e}")
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
    
    Provide a detailed report in Arabic including:
    1. Match Score (0-100).
    2. Weaknesses: Specific skills or keywords missing from the resume for this role.
    3. CV Tweaks: Exact phrases or projects to add to the Word document to pass ATS.
    4. Interview Advice: A tough technical question based on the candidate's specific gaps.
    
    If match score is below 70, start the response with 'SKIP'.
    """
    
    data = {
        "model": "llama3.1-8b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        res = requests.post(url, headers=headers, json=data)
        content = res.json()['choices'][0]['message']['content']
        return content
    except Exception as e:
        print(f"Error analyzing with AI: {e}")
        return "SKIP"

def send_to_discord(title, link, report):
    print(f"Match found for '{title}'. Sending to Discord...")
    payload = {
        "content": f"🎯 **New High-Match Job Found: {title}**",
        "embeds": [{"description": report, "url": link, "color": 15158332}]
    }
    try:
        resp = requests.post(DISCORD_WEBHOOK, json=payload)
        if resp.status_code == 204:
            print("Message sent successfully to Discord.")
        else:
            print(f"Failed to send to Discord. Status: {resp.status_code}")
    except Exception as e:
        print(f"Error sending to Discord: {e}")

def main():
    print("--- Starting Job Hunter Bot ---")
    resume = get_private_resume()
    if not resume:
        print("Stopping: Resume content is empty.")
        return
    
    jobs = search_jobs()
    if not jobs:
        print("Stopping: No jobs found in search.")
        return

    for job in jobs:
        title = job.get('title', 'Unknown Title')
        print(f"Processing job: {title}")
        
        report = analyze_with_ai(title, job.get('description', ''), resume)
        
        if report.strip().upper().startswith("SKIP"):
            print(f"Skipping job: {title} (Low match score)")
        else:
            link = job.get('related_links', [{}])[0].get('link', 'No link provided')
            send_to_discord(title, link, report)

    print("--- Job Hunter Bot Finished ---")

if __name__ == "__main__":
    main()
