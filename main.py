from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from playwright.async_api import async_playwright
import requests
import asyncio
import sys

app = FastAPI()
templates = Jinja2Templates(directory="templates")

API_URL = "https://tickets-api.stadium-360.net/ticketingmanagement/adminsales/getsectionsavailabilitystatistics"

API_PARAMS = {
    "eventid": 4430,
    "venueid": 7,
    "seasonid": 56,
    "producttypeid": 1
}

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def get_bearer_token(email, password):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://tickets.stadium-360.net/aek/login")
        await page.fill('input[id="email"]', email)
        await page.fill('input[placeholder="Enter your password"]', password)
        await page.click('button[type="submit"]')  # Adjust if button selector is different
        
         # Wait for navigation or successful login (adjust timeout if needed)
        await page.wait_for_timeout(5000)

        # Option 1: Extract Bearer token from localStorage
        cookies = await context.cookies()
        token_cookie = next((c["value"] for c in cookies if c["name"] == "token-aek"), None)

        # Option 2: Extract Authorization from cookies or headers if stored elsewhere

        await browser.close()
        return token_cookie

def fetch_ticket_data(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "portalcode": "aek",
        "portalid": "7",
        "Referer": "https://tickets.stadium-360.net/"
    }
    res = requests.get(API_URL, headers=headers, params=API_PARAMS)
    return res.json()["data"] if res.status_code == 200 else None



def calculate_tickets(sections):
    capacity = 0
    unavailable = 0
    for section in sections:
        if section["standId"] in (43,44):
            capacity += section["capacity"]
            unavailable += section["unavailableSeats"]


    available = capacity - unavailable

    return capacity, available, unavailable

@app.get("/", response_class=HTMLResponse)
def form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/check", response_class=HTMLResponse)
async def check_tickets(request: Request, email: str = Form(...), password: str = Form(...)):
    token = await get_bearer_token(email, password)
    if not token:
        return templates.TemplateResponse("form.html", {"request": request, "error": "Login failed. Try again."})

    sections = fetch_ticket_data(token)
    if not sections:
        return templates.TemplateResponse("form.html", {"request": request, "error": "Failed to fetch ticket data."})

    total, available, sold = calculate_tickets(sections)
    return templates.TemplateResponse("result.html", {
        "request": request,
        "total": total,
        "available": available,
        "sold": sold
    })