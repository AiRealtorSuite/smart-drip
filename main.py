import os
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI()

# Shared secret between Lovable -> your backend (optional but recommended)
SMART_DRIP_SECRET = os.getenv("SMART_DRIP_SECRET", "")

# For testing ONLY: one token in env. Next step is storing per-user tokens.
TEST_GHL_PRIVATE_TOKEN = os.getenv("TEST_GHL_PRIVATE_TOKEN", "")

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = os.getenv("GHL_VERSION", "2021-07-28")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/smart-drip/import")
async def smart_drip_import(
    request: Request,
    x_smart_drip_secret: Optional[str] = Header(default=None),
):
    # (1) Optional secret validation
    if SMART_DRIP_SECRET:
        if x_smart_drip_secret != SMART_DRIP_SECRET:
            raise HTTPException(status_code=401, detail="Invalid x-smart-drip-secret")

    if not TEST_GHL_PRIVATE_TOKEN:
        raise HTTPException(status_code=500, detail="Missing TEST_GHL_PRIVATE_TOKEN env var")

    payload: Dict[str, Any] = await request.json()

    # (2) Basic validation
    if payload.get("action") != "phase1_create_contacts_and_campaign":
        raise HTTPException(status_code=400, detail="Invalid action")

    if not payload.get("permission_confirmed"):
        raise HTTPException(status_code=400, detail="Permission not confirmed")

    contact_import = payload.get("contact_import", {})
    contacts = contact_import.get("contacts", [])
    if not isinstance(contacts, list) or len(contacts) == 0:
        raise HTTPException(status_code=400, detail="No contacts provided")

    # Optional custom tag per CSV upload (you requested this)
    custom_tag = (contact_import.get("custom_tag") or "").strip()
    system_tag = "AI Smart Drip"

    headers = {
        "Authorization": f"Bearer {TEST_GHL_PRIVATE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": GHL_VERSION,
    }

    created = 0
    failed = []

    async with httpx.AsyncClient(timeout=20) as client:
        for c in contacts:
            email = (c.get("email") or "").strip()
            if not email:
                continue

            tags = [system_tag]
            if custom_tag:
                tags.append(custom_tag)

            body = {
                "firstName": c.get("first_name") or "",
                "lastName": c.get("last_name") or "",
                "email": email,
                "phone": c.get("phone") or None,
                "address1": c.get("address") or None,
                "city": c.get("city") or None,
                "state": c.get("state") or None,
                "postalCode": c.get("zip") or None,
                "tags": tags,
            }

            resp = await client.post(f"{GHL_BASE}/contacts/", headers=headers, json=body)
            if resp.status_code in (200, 201):
                created += 1
            else:
                failed.append({"email": email, "status": resp.status_code, "body": resp.text[:500]})

    return {"ok": True, "created_contacts": created, "failed": failed}
@app.get("/")
def root():
    return {"ok": True, "service": "smart-drip"}
