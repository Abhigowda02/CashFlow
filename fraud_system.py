"""
Fraud detection + mock payment system (single file, hackathon ready)

Install:  pip install fastapi uvicorn scikit-learn numpy pydantic
Run:      uvicorn fraud_system:app --reload
Demo UI:  http://127.0.0.1:8000/
API docs: http://127.0.0.1:8000/docs

Integration (from your own code):
    from fraud_system import check_fraud, process_payment
    result = check_fraud({...payment dict...})   # -> {score, decision, reasons}
    receipt = process_payment({...payment dict...})  # fraud check + mock charge

Or call over HTTP:  POST /pay   (recommended: your checkout calls this)
"""
import time
import uuid
import math
import random
from collections import defaultdict
from typing import Optional

import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
REVIEW_THRESHOLD = 30   # score >= 30 -> manual review
BLOCK_THRESHOLD = 60    # score >= 60 -> block
RULE_WEIGHT, ML_WEIGHT = 0.7, 0.3
DISPOSABLE_DOMAINS = {"mailinator.com", "tempmail.com", "10minutemail.com",
                      "guerrillamail.com", "yopmail.com", "trashmail.com"}
HIGH_RISK_COUNTRIES = {"KP", "IR", "SY"}  # demo list only

# --------------------------------------------------------------------------
# Data model + in-memory storage (swap for a DB in a real app)
# --------------------------------------------------------------------------
class Payment(BaseModel):
    user_id: str
    amount: float
    currency: str = "USD"
    card_number: str = "4242424242424242"
    email: str = "user@example.com"
    ip_country: str = "US"
    billing_country: str = "US"
    device_id: str = "device-1"
    account_age_hours: float = 1000.0


HISTORY = defaultdict(list)   # user_id -> list of past payment records
LOG = []                      # all processed payments (for the dashboard)

# --------------------------------------------------------------------------
# ML: Isolation Forest trained on synthetic "normal" transactions
# --------------------------------------------------------------------------
def _features(p: dict, txns_last_hour: int, hour: int) -> list:
    return [
        math.log1p(p["amount"]),
        hour,
        min(p["account_age_hours"], 24 * 365),
        txns_last_hour,
        1.0 if p["ip_country"] != p["billing_country"] else 0.0,
    ]


def _train_model() -> IsolationForest:
    rng = np.random.default_rng(42)
    n = 4000
    X = np.column_stack([
        np.log1p(rng.lognormal(mean=math.log(60), sigma=0.8, size=n)),
        np.clip(rng.normal(14, 4, n), 0, 23),
        rng.uniform(24, 8000, n),
        rng.poisson(0.3, n),
        rng.binomial(1, 0.03, n),
    ])
    return IsolationForest(n_estimators=100, contamination=0.02,
                           random_state=42).fit(X)


MODEL = _train_model()


def _ml_score(p: dict, txns_last_hour: int) -> float:
    hour = time.localtime().tm_hour
    s = MODEL.score_samples([_features(p, txns_last_hour, hour)])[0]
    # score_samples is ~ -0.35 (normal) to -0.7 (anomalous) -> map to 0..100
    return float(np.clip((-s - 0.40) / 0.30, 0, 1) * 100)

# --------------------------------------------------------------------------
# Rules engine
# --------------------------------------------------------------------------
def _rule_score(p: dict, now: float):
    reasons, score = [], 0
    hist = HISTORY[p["user_id"]]
    last_min = [h for h in hist if now - h["ts"] < 60]
    last_hour = [h for h in hist if now - h["ts"] < 3600]
    last_10min_cards = {h["card"] for h in hist if now - h["ts"] < 600}
    last_10min_cards.add(p["card_number"])

    if len(last_min) >= 3:
        score += 40; reasons.append(f"Velocity: {len(last_min)} payments in the last minute")
    elif len(last_hour) >= 6:
        score += 25; reasons.append(f"Velocity: {len(last_hour)} payments in the last hour")

    if len(hist) >= 3:
        avg = sum(h["amount"] for h in hist) / len(hist)
        if p["amount"] > 5 * avg and p["amount"] > 100:
            score += 25; reasons.append(f"Amount {p['amount']:.0f} is >5x user average ({avg:.0f})")

    if p["amount"] >= 5000:
        score += 30; reasons.append("Very high amount (>= 5000)")
    elif p["amount"] >= 1000:
        score += 15; reasons.append("High amount (>= 1000)")

    if p["ip_country"] != p["billing_country"]:
        score += 25; reasons.append(f"IP country {p['ip_country']} != billing country {p['billing_country']}")

    if p["ip_country"] in HIGH_RISK_COUNTRIES:
        score += 30; reasons.append(f"High-risk IP country {p['ip_country']}")

    if p["account_age_hours"] < 24 and p["amount"] > 200:
        score += 25; reasons.append("New account (<24h) with large payment")

    domain = p["email"].split("@")[-1].lower()
    if domain in DISPOSABLE_DOMAINS:
        score += 25; reasons.append(f"Disposable email domain ({domain})")

    if len(last_10min_cards) >= 3:
        score += 35; reasons.append(f"{len(last_10min_cards)} different cards used in 10 minutes (card testing)")

    if p["amount"] <= 2 and len(last_hour) >= 2:
        score += 20; reasons.append("Repeated tiny payments (card testing pattern)")

    return min(score, 100), reasons, len(last_hour)

# --------------------------------------------------------------------------
# Public fraud API
# --------------------------------------------------------------------------
def check_fraud(payment: dict) -> dict:
    """Returns {score, rule_score, ml_score, decision, reasons}."""
    p = Payment(**payment).model_dump()
    now = time.time()
    rule, reasons, last_hour = _rule_score(p, now)
    ml = _ml_score(p, last_hour)
    if ml > 60:
        reasons.append(f"ML anomaly detector flagged unusual pattern ({ml:.0f}/100)")
    score = round(RULE_WEIGHT * rule + ML_WEIGHT * ml, 1)
    score = max(score, rule if rule >= 80 else 0)  # strong rule hits can't be diluted
    if score >= BLOCK_THRESHOLD:
        decision = "block"
    elif score >= REVIEW_THRESHOLD:
        decision = "review"
    else:
        decision = "approve"
    return {"score": score, "rule_score": rule, "ml_score": round(ml, 1),
            "decision": decision, "reasons": reasons or ["No risk signals"]}

# --------------------------------------------------------------------------
# Mock payment processor (fake Stripe)
# --------------------------------------------------------------------------
def _mock_charge(p: dict) -> dict:
    """Pretend to talk to a bank. Test cards behave like Stripe's."""
    card = p["card_number"].replace(" ", "")
    if card == "4000000000000002":
        return {"ok": False, "error": "card_declined"}
    if card == "4000000000009995":
        return {"ok": False, "error": "insufficient_funds"}
    return {"ok": True, "charge_id": "ch_" + uuid.uuid4().hex[:14]}


def process_payment(payment: dict) -> dict:
    """Fraud check FIRST, then (only if allowed) the mock charge."""
    p = Payment(**payment).model_dump()
    fraud = check_fraud(p)
    record = {"id": "pay_" + uuid.uuid4().hex[:10], "ts": time.time(), **p,
              "fraud": fraud, "status": None, "charge_id": None}

    if fraud["decision"] == "block":
        record["status"] = "blocked_fraud"
    elif fraud["decision"] == "review":
        record["status"] = "pending_review"
    else:
        charge = _mock_charge(p)
        record["status"] = "succeeded" if charge["ok"] else charge["error"]
        record["charge_id"] = charge.get("charge_id")

    HISTORY[p["user_id"]].append({"ts": record["ts"], "amount": p["amount"],
                                  "card": p["card_number"], "device": p["device_id"]})
    LOG.append(record)
    return record

# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------
app = FastAPI(title="Fraud Detection + Mock Payments")


@app.post("/check")
def api_check(payment: Payment):
    """Fraud check only (no charge)."""
    return check_fraud(payment.model_dump())


@app.post("/pay")
def api_pay(payment: Payment):
    """Full flow: fraud check -> mock charge. Call this from your checkout."""
    return process_payment(payment.model_dump())


@app.post("/review/{payment_id}/{action}")
def api_review(payment_id: str, action: str):
    """Manual review: action = approve | reject."""
    for r in LOG:
        if r["id"] == payment_id and r["status"] == "pending_review":
            if action == "approve":
                charge = _mock_charge(r)
                r["status"] = "succeeded" if charge["ok"] else charge["error"]
                r["charge_id"] = charge.get("charge_id")
            else:
                r["status"] = "rejected_by_reviewer"
            return r
    return {"error": "not found or not pending"}


@app.get("/transactions")
def api_transactions():
    return list(reversed(LOG))[:100]


@app.post("/reset")
def api_reset():
    HISTORY.clear(); LOG.clear()
    return {"ok": True}

# --------------------------------------------------------------------------
# Demo UI
# --------------------------------------------------------------------------
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fraud Demo</title>
<style>
body{font-family:system-ui,sans-serif;max-width:900px;margin:20px auto;padding:0 12px;color:#222}
button{padding:8px 12px;margin:3px;border:0;border-radius:6px;background:#2563eb;color:#fff;cursor:pointer}
button.r{background:#dc2626}button.g{background:#16a34a}button.o{background:#d97706}
input{padding:6px;margin:3px;width:150px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:13px}
td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left;vertical-align:top}
.approve,.succeeded{color:#16a34a}.review,.pending_review{color:#d97706}
.block,.blocked_fraud{color:#dc2626}
</style></head><body>
<h2>Mock Checkout + Fraud Check</h2>
<div>
<input id="user" value="alice" placeholder="user"><input id="amount" type="number" value="49">
<input id="card" value="4242424242424242"><input id="email" value="alice@gmail.com">
<input id="ip" value="US" placeholder="IP country"><input id="bill" value="US" placeholder="billing country">
<input id="age" type="number" value="1000" placeholder="account age (h)">
<button onclick="pay()">Pay</button>
</div>
<div>Simulate:
<button class="g" onclick="sc('normal')">Normal</button>
<button class="o" onclick="sc('abroad')">Country mismatch</button>
<button class="r" onclick="sc('velocity')">Velocity attack</button>
<button class="r" onclick="sc('newbig')">New acct + big + temp email</button>
<button class="r" onclick="sc('cards')">Card testing</button>
<button onclick="fetch('/reset',{method:'POST'}).then(load)">Reset</button></div>
<div id="out"></div>
<table><thead><tr><th>Time</th><th>User</th><th>Amount</th><th>Score</th><th>Decision</th><th>Status</th><th>Reasons</th><th></th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
const v=id=>document.getElementById(id).value;
async function send(b){const r=await fetch('/pay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return r.json()}
function body(){return{user_id:v('user'),amount:+v('amount'),card_number:v('card'),email:v('email'),ip_country:v('ip'),billing_country:v('bill'),account_age_hours:+v('age')}}
async function pay(){await send(body());load()}
async function sc(n){
 const b={user_id:'u_'+n+Math.floor(Math.random()*999),amount:40,card_number:'4242424242424242',email:'x@gmail.com',ip_country:'US',billing_country:'US',account_age_hours:2000};
 if(n=='abroad'){b.ip_country='RU';b.amount=300}
 if(n=='newbig'){b.account_age_hours=2;b.amount=1500;b.email='bot@mailinator.com'}
 if(n=='velocity'){for(let i=0;i<5;i++)await send(b)}
 if(n=='cards'){for(let i=0;i<4;i++){b.amount=1;b.card_number='4000'+(1000+i)+'00001111';await send({...b})}}
 else await send(b);
 load()}
async function act(id,a){await fetch('/review/'+id+'/'+a,{method:'POST'});load()}
async function load(){const d=await (await fetch('/transactions')).json();
 document.getElementById('rows').innerHTML=d.map(t=>`<tr><td>${new Date(t.ts*1000).toLocaleTimeString()}</td><td>${t.user_id}</td><td>${t.amount}</td>
 <td>${t.fraud.score}</td><td class="${t.fraud.decision}">${t.fraud.decision}</td><td class="${t.status}">${t.status}</td>
 <td>${t.fraud.reasons.join('<br>')}</td>
 <td>${t.status=='pending_review'?`<button class="g" onclick="act('${t.id}','approve')">OK</button><button class="r" onclick="act('${t.id}','reject')">No</button>`:''}</td></tr>`).join('')}
load();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
