from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
import base64
import json
import uuid
import datetime

app = FastAPI(title="Spread Technical ITSM API - GitHub Edition")

# Enable CORS for your frontend portal
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For production, restrict this to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "8680843182:AAH9S4IKmXquADKzanbNA7mVUU0VuMnZpeE"
TELEGRAM_CHAT_ID = "712453173"

GITHUB_TOKEN = "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"
GITHUB_REPO = "jvp3107/itsm-db-itsupport" # e.g., "vaibhav/itsm-db"
TICKETS_FILE = "tickets.json"
USERS_FILE = "users.json"

# ==========================================
# GITHUB API ENGINE
# ==========================================
def get_github_file(filepath: str):
    """Fetches a file from GitHub. Returns (data, sha) or ([], None) if not found."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        content_info = response.json()
        decoded_bytes = base64.b64decode(content_info['content'])
        try:
            data = json.loads(decoded_bytes.decode('utf-8'))
        except:
            data = []
        return data, content_info['sha']
    return [], None

def update_github_file(filepath: str, data: list, sha: str, message: str):
    """Pushes updated JSON data back to the GitHub repository."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    encoded_content = base64.b64encode(json.dumps(data, indent=4).encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": message,
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha
        
    response = requests.put(url, headers=headers, json=payload)
    if response.status_code not in [200, 201]:
        print(f"GitHub Sync Error: {response.text}")

# ==========================================
# INITIALIZE DATABASE
# ==========================================
def init_db():
    # Verify/Create Users File
    users, sha = get_github_file(USERS_FILE)
    if not sha:
        master_admin = {
            "email": "vaibhav@spreadtechnical.com", "password": "Support@1999", 
            "company": "Spread Technical", "name": "Vaibhav Patel", 
            "role": "Master Admin", "reset_token": ""
        }
        update_github_file(USERS_FILE, [master_admin], None, "Init Users DB")
        
    # Verify/Create Tickets File
    tickets, sha = get_github_file(TICKETS_FILE)
    if not sha:
        update_github_file(TICKETS_FILE, [], None, "Init Tickets DB")

init_db()

# ==========================================
# TELEGRAM NOTIFICATIONS
# ==========================================
def send_telegram_notification(text: str):
    if not TELEGRAM_BOT_TOKEN or "YOUR_" in TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

# ==========================================
# DATA MODELS
# ==========================================
class PayloadModel(BaseModel):
    action: str
    email: Optional[str] = None
    password: Optional[str] = None
    new_password: Optional[str] = None
    company: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    portalUrl: Optional[str] = None
    token: Optional[str] = None
    
    # Ticket specific fields
    id: Optional[str] = None
    phone: Optional[str] = None
    request_type: Optional[str] = None
    category: Optional[str] = None
    impact_level: Optional[str] = None
    asset: Optional[str] = "N/A"
    device: Optional[str] = None
    remote_support: Optional[str] = None
    priority: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None
    fileData: Optional[str] = None
    fileName: Optional[str] = None
    resolve_description: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_date: Optional[str] = None
    sender: Optional[str] = None
    message: Optional[str] = None
    time: Optional[str] = None

# ==========================================
# API ROUTES
# ==========================================
@app.get("/exec")
def get_tickets():
    tickets, _ = get_github_file(TICKETS_FILE)
    return {"status": "success", "tickets": tickets}

@app.post("/exec")
def handle_request(payload: PayloadModel):
    action = payload.action
    
    # ---------------------------------------------------------
    # USER MANAGEMENT & AUTHENTICATION
    # ---------------------------------------------------------
    if action in ["get_users", "register_client", "register_admin", "login_client", "login_admin", "send_reset_email", "update_password", "admin_reset_password"]:
        users, sha = get_github_file(USERS_FILE)
        
        if action == "get_users":
            safe_users = [{"email": u["email"], "company": u["company"], "name": u["name"], "role": u["role"]} for u in users]
            return {"status": "success", "users": safe_users}
            
        if action in ["register_client", "register_admin"]:
            users.append({
                "email": payload.email.lower(), "password": payload.password, 
                "company": payload.company, "name": payload.name, 
                "role": payload.role if action == "register_admin" else "Client", 
                "reset_token": ""
            })
            update_github_file(USERS_FILE, users, sha, f"Registered user {payload.email}")
            return {"status": "success"}

        if action in ["login_client", "login_admin"]:
            req_email = payload.email.lower()
            for u in users:
                if u["email"].lower() == req_email and u["password"] == payload.password:
                    if action == "login_admin" and u["role"] == "Client":
                        return {"status": "error", "message": "Access Denied."}
                    
                    peers = []
                    if action == "login_client":
                        peers = [{"email": p["email"], "name": p["name"]} for p in users if p["company"] == u["company"] and p["role"] == "Client"]
                    
                    return {"status": "success", "company": u["company"], "name": u["name"], "role": u["role"], "peers": peers}
            return {"status": "error", "message": "Invalid Credentials."}

        if action == "admin_reset_password":
            for u in users:
                if u["email"].lower() == payload.email.lower():
                    u["password"] = payload.new_password
                    update_github_file(USERS_FILE, users, sha, f"Admin reset password for {payload.email}")
                    return {"status": "success"}
            return {"status": "error", "message": "User not found."}

        if action == "send_reset_email":
            req_email = payload.email.lower()
            for u in users:
                if u["email"].lower() == req_email:
                    token = str(uuid.uuid4())
                    u["reset_token"] = token
                    update_github_file(USERS_FILE, users, sha, f"Generated reset token for {req_email}")
                    reset_link = f"{payload.portalUrl}?action=reset_password&token={token}&email={req_email}"
                    print(f"SMTP TRIGGERED: Sending {reset_link} to {req_email}") # Replace with actual SMTP logic
                    return {"status": "success"}
            return {"status": "error", "message": "Email not found."}

        if action == "update_password":
            for u in users:
                if u["email"].lower() == payload.email.lower() and u["reset_token"] == payload.token:
                    u["password"] = payload.password
                    u["reset_token"] = ""
                    update_github_file(USERS_FILE, users, sha, f"User self-reset password for {payload.email}")
                    return {"status": "success"}
            return {"status": "error", "message": "Invalid Token."}

    # ---------------------------------------------------------
    # TICKET MANAGEMENT
    # ---------------------------------------------------------
    if action in ["update", "chat", "create_ticket"]:
        tickets, sha = get_github_file(TICKETS_FILE)

        if action == "update":
            for t in tickets:
                if t["id"] == payload.id:
                    t["status"] = payload.status
                    if payload.resolve_description: t["resolve_description"] = payload.resolve_description
                    if payload.assigned_to:
                        t["assigned_to"] = payload.assigned_to
                        t["assigned_date"] = payload.assigned_date
                    update_github_file(TICKETS_FILE, tickets, sha, f"Updated ticket {payload.id}")
                    return {"status": "success"}
            return {"status": "error", "message": "Ticket ID not found."}

        elif action == "chat":
            for t in tickets:
                if t["id"] == payload.id:
                    chat_arr = json.loads(t.get("chat_history", "[]"))
                    chat_arr.append({"sender": payload.sender, "message": payload.message, "time": payload.time})
                    t["chat_history"] = json.dumps(chat_arr)
                    update_github_file(TICKETS_FILE, tickets, sha, f"Appended chat to {payload.id}")
                    
                    if payload.sender == "User":
                        send_telegram_notification(f"💬 <b>NEW MESSAGE TICKET {payload.id}</b>\n\n<i>\"{payload.message}\"</i>")
                    return {"status": "success"}
            return {"status": "error", "message": "Ticket ID not found."}
            
        elif action == "create_ticket":
            new_ticket = {
                "id": payload.id, "name": payload.name, "company": payload.company, "phone": payload.phone, 
                "email": payload.email, "request_type": payload.request_type, "category": payload.category, 
                "impact_level": payload.impact_level, "asset": payload.asset, "device": payload.device, 
                "remote_support": payload.remote_support, "priority": payload.priority, "subject": payload.subject, 
                "description": payload.description, "date": payload.date, "status": payload.status, 
                "attachment": "No Attachment", "resolve_description": "", "assigned_to": "", 
                "assigned_date": "", "chat_history": "[]"
            }
            tickets.append(new_ticket)
            update_github_file(TICKETS_FILE, tickets, sha, f"Created ticket {payload.id}")
            
            header = "⏳ <b>ACTION REQUIRED: APPROVAL PENDING</b>" if payload.status == "Pending Approval" else "🎫 <b>NEW IT TICKET LOGGED</b>"
            priority_tag = "🚨 HIGH" if payload.impact_level == "High" else ("⚠️ MEDIUM" if payload.impact_level == "Medium" else "🟢 LOW")
            
            telegram_msg = (
                f"{header}\n\n<b>ID:</b> <code>{payload.id}</code>\n<b>Priority:</b> {priority_tag}\n"
                f"<b>Company:</b> {payload.company}\n<b>Requester:</b> {payload.name} ({payload.phone})\n"
                f"<b>Category:</b> {payload.category}\n\n<b>Summary:</b> {payload.subject}\n"
                f"<b>Details:</b>\n<i>{payload.description}</i>\n\n🕒 <i>{payload.date}</i>"
            )
            send_telegram_notification(telegram_msg)
            return {"status": "success", "id": payload.id}

    return {"status": "error", "message": "Unknown action."}

# Run server with: uvicorn main:app --host 0.0.0.0 --port 8000
