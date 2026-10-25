from functools import lru_cache
from typing import Literal
from datetime import date, datetime, timezone
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from . import clock, ledger, auth, database, customer_behavior, expenses, scenarios, pdf_import
from .routers.invoices import router as invoices_router
from .routers.forecast_view import router as forecast_view_router
from .scenarios import Scenario
from sqlalchemy import update

DelayModel = Literal['empirical', 'survival']


class BalanceUpdate(BaseModel):
    cash_balance: int = Field(ge=0, strict=True)
    cash_updated_on: date | None = None


class InvoiceImport(BaseModel):
    filename: str
    content_base64: str = Field(max_length=7_000_000)
    name: str = Field(min_length=1, max_length=120)
    as_of: date
    opening_cash: int = Field(ge=0, strict=True)
    safety_floor: int = Field(ge=0, strict=True)
    declared_currency: Literal['INR'] | None = None


class PdfPreviewRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=7_000_000)


class PdfInvoiceDraft(BaseModel):
    invoice_id: str = Field(min_length=1, max_length=100)
    customer_id: str = Field(min_length=1, max_length=200)
    customer_name: str = Field(min_length=1, max_length=200)
    segment: Literal['small', 'corporate', 'government']
    amount: int = Field(gt=0, strict=True)
    issue_date: date
    due_date: date
    currency: str = Field(min_length=1, max_length=12)
    received_amount: int = Field(ge=0, strict=True)
    paid_date: date | None = None


class PdfImportRequest(BaseModel):
    invoices: list[PdfInvoiceDraft] = Field(min_length=1, max_length=25)
    confirm_append: bool = Field(strict=True)
    confirm_currency_inr: bool = Field(strict=True)


class Receipt(BaseModel):
    invoice_id: str
    receipt_id: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0, strict=True)
    date: date


class Obligation(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    amount: int = Field(ge=0, strict=True)
    day_of_month: int = Field(ge=1, le=31)
    frequency: Literal['monthly'] = 'monthly'
    category: Literal['salary', 'rent', 'loan', 'tax', 'utilities', 'subscription', 'insurance', 'other'] = 'other'


class SupplierBill(BaseModel):
    id: str = Field(min_length=1)
    supplier: str = Field(min_length=1)
    amount: int = Field(ge=0, strict=True)
    due_date: date
    is_msme: bool = False
    status: Literal['open', 'paid'] = 'open'


class Plan(BaseModel):
    as_of: date | None = None
    obligations: list[Obligation] = Field(max_length=40)
    supplier_bills: list[SupplierBill] = Field(max_length=100)
    monthly_sales: int = Field(ge=0, strict=True)
    terms_days: int = Field(ge=0, le=365)
    monthly_noise_pct: int = Field(ge=0, le=100)


class CustomerContext(BaseModel):
    customer_id: str = Field(min_length=1, max_length=200)
    importance: Literal['standard', 'important', 'strategic']
    repeat_customer: bool = Field(strict=True)
    service_issue: Literal['none', 'open', 'resolving']
    disputed_invoice_ids: list[str] = Field(default_factory=list, max_length=2000)
    notes: str = Field(default='', max_length=1000)


def current_business(business_id):
    saved = ledger.load_business(business_id)
    if saved is not None:
        saved['as_of'] = clock.today_ist().isoformat()
        return saved
    raise HTTPException(409, 'Complete business setup first')


def annotated(forecast, business, requested, business_id):
    forecast.setdefault('meta', {}).update(data_source=business.get('data_source', 'synthetic'),
                                         delay_model_requested=requested,
                                         validation_status='not_validated_on_representative_real_businesses')
    if requested == 'survival':
        forecast['meta']['payment_model'] = customer_behavior.status(customer_behavior.model_result(business, business_id))
        forecast['meta']['model_training_source'] = 'this_business'

    obligations = business.get('obligations') or []
    sales_plan = business.get('sales_plan') or {}
    monthly_sales = float(sales_plan.get('monthly_amount', 0) or 0)
    warnings = list(forecast.get('warnings') or [])

    cash_updated_on = business.get('cash_updated_on') or business.get('as_of')
    stale = clock.is_stale(cash_updated_on, max_days=3)
    if cash_updated_on:
        try:
            c_date = date.fromisoformat(cash_updated_on.split('T')[0])
            if c_date < clock.today_ist():
                stale = True
        except (ValueError, TypeError):
            stale = True
    else:
        stale = True

    forecast['stale'] = stale
    forecast['cash_last_updated'] = cash_updated_on

    if stale and cash_updated_on:
        stale_warning = f"Your balance is from {cash_updated_on}. Update it for an accurate forecast."
        if stale_warning not in warnings:
            warnings.insert(0, stale_warning)

    gap_summary = business.get('_gap_summary')
    if gap_summary:
        forecast['estimated_since_last_update'] = gap_summary

    if not obligations and monthly_sales == 0:
        warning_msg = "No expenses entered: forecast only shows invoice receipts"
        if warning_msg not in warnings:
            warnings.append(warning_msg)
    elif not obligations:
        warning_msg = "No recurring expenses entered: forecast only reflects income"
        if warning_msg not in warnings:
            warnings.append(warning_msg)
    forecast['warnings'] = warnings
    return forecast


def load_engine():
    # Production backend loads forecasting and scenario functions; generate_business is for dev/test fixtures only
    from engine import (
        compare_scenario,
        rank_actions,
        run_forecast,
    )

    return None, run_forecast, compare_scenario, rank_actions



def fixture_response(payload, source="engine"):
    return JSONResponse(content=payload, headers={"X-Source": source})


@asynccontextmanager
async def lifespan(app):
    if os.environ.get('APP_ENV') == 'production':
        if not database.DATABASE_URL.startswith('postgresql+psycopg://'):
            raise RuntimeError('Production requires DATABASE_URL=postgresql+psycopg://...')
        if not auth.SECURE_COOKIE or not auth.ALLOWED_ORIGINS or not all(origin.startswith('https://') for origin in auth.ALLOWED_ORIGINS):
            raise RuntimeError('Production requires COOKIE_SECURE=true and explicit HTTPS ALLOWED_ORIGINS')
    database.engine()
    yield


app = FastAPI(title="CashFlow API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(invoices_router)
app.include_router(forecast_view_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=auth.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Source"],
)


@app.middleware('http')
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


class Onboarding(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    as_of: date
    opening_cash: int = Field(ge=0, strict=True)
    safety_floor: int = Field(ge=0, strict=True)



@app.post('/api/onboarding')
def onboard(payload: Onboarding, user: auth.Account = Depends(auth.require_user)):
    as_of_str = payload.as_of.isoformat()
    business = dict(name=payload.name.strip(), as_of=as_of_str,
        opening_cash=payload.opening_cash, safety_floor=payload.safety_floor,
        cash_balance=payload.opening_cash, cash_updated_on=as_of_str,
        customers=[], invoices=[], supplier_bills=[], obligations=[],
        sales_plan=dict(monthly_amount=0, terms_days=30, monthly_noise_pct=0),
        data_source='owner', currency='INR')
    if not business['name']:
        raise HTTPException(422, 'Business name cannot be blank')
    import json
    with database.transaction() as connection:
        result = connection.execute(update(database.workspaces).where(
            database.workspaces.c.id == user.business_id, database.workspaces.c.onboarded.is_(False))
            .values(payload=json.dumps(business), onboarded=True))
        if result.rowcount != 1:
            raise HTTPException(409, 'Business setup is already complete')
    return dict(saved=True)


@app.get("/api/business")
def get_business(user: auth.Account = Depends(auth.require_user)):
    return fixture_response(current_business(user.business_id), 'engine')


@app.post("/api/business/balance")
def update_balance(payload: BalanceUpdate, user: auth.Account = Depends(auth.require_user)):
    updated_date = payload.cash_updated_on or clock.today_ist()
    updated = ledger.update_cash_balance(user.business_id, payload.cash_balance, updated_date.isoformat())
    return dict(saved=True, cash_balance=updated['cash_balance'], cash_updated_on=updated['cash_updated_on'])


@app.get("/api/forecast")
def get_forecast(delay_model: DelayModel = 'empirical', user: auth.Account = Depends(auth.require_user)):
    business = current_business(user.business_id)
    _, run_forecast, _, _ = load_engine()
    forecast = run_forecast(ledger.forecast_business(business, user.business_id), delay_model=delay_model)
    return fixture_response(annotated(forecast, business, delay_model, user.business_id), 'engine')


@app.post("/api/scenario")
def post_scenario(scenario: Scenario, delay_model: DelayModel = 'empirical', user: auth.Account = Depends(auth.require_user)):
    business = current_business(user.business_id)
    try:
        definition = scenarios.validate_scenario(scenario, business)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    _, _, compare_scenario, _ = load_engine()
    comparison = compare_scenario(ledger.forecast_business(business, user.business_id), definition, delay_model=delay_model)
    return fixture_response({key: annotated(value, business, delay_model, user.business_id) for key, value in comparison.items()}, 'engine')


@app.get('/api/scenarios')
def get_scenarios(user: auth.Account = Depends(auth.require_user)):
    current_business(user.business_id)
    return scenarios.list_saved(user.business_id)


@app.post('/api/scenarios', status_code=201)
def save_scenario(scenario: Scenario, user: auth.Account = Depends(auth.require_user)):
    business = current_business(user.business_id)
    try:
        definition = scenarios.validate_scenario(scenario, business, saving=True)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return scenarios.save(definition, user.business_id)


@app.delete('/api/scenarios/{scenario_id}', status_code=204)
def delete_scenario(scenario_id: str, user: auth.Account = Depends(auth.require_user)):
    current_business(user.business_id)
    if not scenarios.delete_saved(scenario_id, user.business_id):
        raise HTTPException(404, 'Saved scenario not found')


@app.get("/api/actions")
def get_actions(delay_model: DelayModel = 'empirical', user: auth.Account = Depends(auth.require_user)):
    _, _, _, rank_actions = load_engine()
    return fixture_response(rank_actions(ledger.forecast_business(current_business(user.business_id), user.business_id), delay_model=delay_model), 'engine')


@app.get('/api/customers')
def get_customers(user: auth.Account = Depends(auth.require_user)):
    return customer_behavior.profiles(current_business(user.business_id), user.business_id)


@app.post('/api/customer-context')
def set_customer_context(payload: CustomerContext, user: auth.Account = Depends(auth.require_user)):
    context = payload.model_dump(exclude={'customer_id'})
    context['disputed_invoice_ids'] = sorted(set(context['disputed_invoice_ids']))
    context['reviewed_at'] = datetime.now(timezone.utc).isoformat()
    try:
        return ledger.update_customer_context(payload.customer_id, context, user.business_id)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@app.get('/api/collections')
def get_collections(delay_model: DelayModel = 'empirical', acceleration_days: int = Query(15, ge=1, le=60),
                    user: auth.Account = Depends(auth.require_user)):
    from engine.collections import rank_collections
    return rank_collections(ledger.forecast_business(current_business(user.business_id), user.business_id),
                            acceleration_days=acceleration_days, delay_model=delay_model)


@app.post('/api/customers/retrain')
def retrain_customer_model(request: Request, user: auth.Account = Depends(auth.require_user)):
    auth.rate_limit('retrain:'+user.business_id, 5, 300)
    return customer_behavior.profiles(current_business(user.business_id), user.business_id, force=True)


@app.get('/api/ledger')
def get_ledger(user: auth.Account = Depends(auth.require_user)):
    return ledger.ledger_summary(current_business(user.business_id))


@app.get('/api/expenses')
def get_expenses(user: auth.Account = Depends(auth.require_user)):
    return expenses.summary(current_business(user.business_id))


@app.post('/api/import')
def import_data(payload: InvoiceImport, user: auth.Account = Depends(auth.require_user)):
    try:
        business = ledger.import_invoices(payload.filename, payload.content_base64, payload.name,
                                          payload.as_of.isoformat(), payload.opening_cash, payload.safety_floor,
                                          declared_currency=payload.declared_currency)
        ledger.save_business(business, user.business_id)
        return dict(invoice_count=len(business['invoices']), data_source='imported')
    except (ValueError, KeyError, ImportError, OverflowError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post('/api/import/pdf/preview')
def preview_pdf_import(payload: PdfPreviewRequest, user: auth.Account = Depends(auth.require_user)):
    try:
        return pdf_import.preview_pdf(payload.filename, payload.content_base64,
                                     current_business(user.business_id))
    except (ValueError, KeyError, ImportError, OverflowError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post('/api/import/pdf/apply')
def apply_pdf_import(payload: PdfImportRequest, user: auth.Account = Depends(auth.require_user)):
    try:
        business = ledger.append_pdf_invoices(
            [invoice.model_dump() for invoice in payload.invoices],
            confirm_append=payload.confirm_append,
            confirm_currency_inr=payload.confirm_currency_inr,
            business_id=user.business_id,
        )
        return dict(invoice_count=len(payload.invoices), total_invoice_count=len(business["invoices"]),
                    data_source=business.get("data_source"))
    except (ValueError, KeyError, OverflowError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post('/api/receipts')
def add_receipt(payload: Receipt, user: auth.Account = Depends(auth.require_user)):
    try:
        ledger.record_receipt(current_business(user.business_id), payload.invoice_id, payload.amount,
                              payload.date.isoformat(), payload.receipt_id, user.business_id)
        return get_ledger(user)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post('/api/plan')
def update_plan(payload: Plan, user: auth.Account = Depends(auth.require_user)):
    for rows in [payload.obligations, payload.supplier_bills]:
        if len({row.id for row in rows}) != len(rows):
            raise HTTPException(status_code=400, detail='IDs must be unique within each list')
    settings = dict(obligations=[item.model_dump() for item in payload.obligations],
                    supplier_bills=[item.model_dump(mode='json') for item in payload.supplier_bills],
                    sales_plan=dict(monthly_amount=payload.monthly_sales, terms_days=payload.terms_days,
                                    monthly_noise_pct=payload.monthly_noise_pct))
    business = current_business(user.business_id)
    if payload.as_of is not None:
        if payload.as_of.isoformat() < business['as_of']:
            raise HTTPException(status_code=400, detail='Observation date cannot move backwards')
        settings['as_of'] = payload.as_of.isoformat()
    ledger.update_plan(business, settings, user.business_id)
    return dict(saved=True)
