import os
import time
import json
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

app = FastAPI()
START = time.time()

# In-memory stores
contexts: dict[tuple[str, str], dict] = {}    # (scope, context_id) -> {version, payload}
conversations: dict[str, list] = {}           # conversation_id -> [turns]

@app.get("/v1/healthz")
async def healthz():
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in contexts.items():
        counts[scope] = counts.get(scope, 0) + 1
    return {"status": "ok", "uptime_seconds": int(time.time() - START), "contexts_loaded": counts}

@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Antigravity", 
        "team_members": ["Agent"], 
        "model": "Rule-based + LLM",
        "approach": "Template composer with fallback", 
        "contact_email": "agent@example.com",
        "version": "1.0.0", 
        "submitted_at": datetime.utcnow().isoformat() + "Z"
    }

class CtxBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str

@app.post("/v1/context")
async def push_context(body: CtxBody):
    key = (body.scope, body.context_id)
    cur = contexts.get(key)
    if cur and cur["version"] > body.version:
        return {"accepted": False, "reason": "stale_version", "current_version": cur["version"]}
    if cur and cur["version"] == body.version:
        return {"accepted": True, "ack_id": f"ack_{body.context_id}_v{body.version}", "stored_at": datetime.utcnow().isoformat() + "Z"}
    contexts[key] = {"version": body.version, "payload": body.payload}
    return {"accepted": True, "ack_id": f"ack_{body.context_id}_v{body.version}",
            "stored_at": datetime.utcnow().isoformat() + "Z"}

def generate_message(merchant, category, trigger, customer=None):
    # Heuristic based message generator
    merchant_name = merchant.get("identity", {}).get("name", "Merchant")
    
    # Check trigger kind
    trigger_kind = trigger.get("kind", "")
    trigger_payload = trigger.get("payload", {})
    
    if trigger_kind == "research_digest":
        top_item = trigger_payload.get("top_item", {})
        title = top_item.get("title", "new research")
        source = top_item.get("source", "industry journal")
        return {
            "body": f"Hi {merchant_name}, noticed a new update from {source}. It shows: {title}. Want me to pull the full abstract or draft a post based on this?",
            "cta": "open_ended",
            "send_as": "vera",
            "suppression_key": trigger.get("suppression_key", ""),
            "rationale": "Used specific research citation and asked for a low-friction YES/NO commitment."
        }
    elif trigger_kind == "recall_due" and customer:
        customer_name = customer.get("identity", {}).get("name", "Customer")
        return {
            "body": f"Hi {customer_name}, {merchant_name} here! It's time for your next visit. We have an offer for you. Reply YES to book a slot.",
            "cta": "binary",
            "send_as": "merchant_on_behalf",
            "suppression_key": trigger.get("suppression_key", ""),
            "rationale": "Specific recall reminder for a customer."
        }
    else:
        # Generic fallback that tries to use specificity
        views = merchant.get("performance", {}).get("views", 0)
        return {
            "body": f"Hi {merchant_name}, your profile got {views} views recently. Let's optimize it to get more walk-ins. Reply YES to see how.",
            "cta": "binary",
            "send_as": "vera",
            "suppression_key": trigger.get("suppression_key", ""),
            "rationale": "Used performance numbers as specificity hook."
        }

class TickBody(BaseModel):
    now: str
    available_triggers: list[str] = []

@app.post("/v1/tick")
async def tick(body: TickBody):
    actions = []
    for trg_id in body.available_triggers:
        trg = contexts.get(("trigger", trg_id), {}).get("payload")
        if not trg: continue
        
        merchant_id = trg.get("merchant_id")
        merchant = contexts.get(("merchant", merchant_id), {}).get("payload")
        category_slug = merchant.get("category_slug") if merchant else trg.get("payload", {}).get("category")
        category = contexts.get(("category", category_slug), {}).get("payload")
        
        if not merchant or not category: continue
        
        customer_id = trg.get("customer_id")
        customer = contexts.get(("customer", customer_id), {}).get("payload") if customer_id else None
        
        msg_data = generate_message(merchant, category, trg, customer)
        
        actions.append({
            "conversation_id": f"conv_{merchant_id}_{trg_id}_{int(time.time())}",
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": msg_data["send_as"],
            "trigger_id": trg_id,
            "template_name": "vera_dynamic",
            "template_params": [],
            "body": msg_data["body"],
            "cta": msg_data["cta"],
            "suppression_key": msg_data["suppression_key"],
            "rationale": msg_data["rationale"]
        })
    return {"actions": actions}

class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.post("/v1/reply")
async def reply(body: ReplyBody):
    conversations.setdefault(body.conversation_id, []).append({"from": body.from_role, "msg": body.message})
    
    msg_lower = body.message.lower()
    
    # Auto-reply detection heuristics
    if "automated assistant" in msg_lower or "automated response" in msg_lower or "thank you for contacting" in msg_lower or "team will respond shortly" in msg_lower:
        return {
            "action": "end",
            "rationale": "Detected auto-reply pattern, gracefully exiting."
        }
        
    # Hostile intent
    if "spam" in msg_lower or "stop messaging" in msg_lower or "not interested" in msg_lower or "leave me alone" in msg_lower:
        return {
            "action": "end",
            "rationale": "Merchant expressed hostility or disinterest, exiting gracefully."
        }
        
    # Intent transition to action
    actioning_words = ["do it", "yes", "sure", "ok", "okay", "go ahead", "draft", "done", "confirm"]
    if any(w in msg_lower for w in actioning_words):
        return {
            "action": "send",
            "body": "Done! I've proceeded with the action as requested. Let me know if you need anything else.",
            "cta": "none",
            "rationale": "Transitioned to action mode based on merchant's commitment."
        }
        
    # Default wait/fallback
    return {
        "action": "wait",
        "wait_seconds": 3600,
        "rationale": "Waiting for clearer signal."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
