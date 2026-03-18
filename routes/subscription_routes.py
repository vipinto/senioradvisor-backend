from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import os
import uuid
import logging

from database import db
from models import SubscriptionCreate
from auth import get_current_user
from mercadopago_service import get_mercadopago_service

router = APIRouter()
logger = logging.getLogger(__name__)


class CreatePaymentRequest(BaseModel):
    plan_id: str


@router.get("/subscription/plans")
async def get_subscription_plans(role: str = None):
    """Get available subscription plans from database, optionally filtered by role"""
    query = {"active": True}
    if role:
        query["role"] = role
    plans = await db.subscription_plans.find(
        query,
        {"_id": 0}
    ).sort("price_clp", 1).to_list(20)
    return plans


@router.post("/subscription/create-payment")
async def create_subscription_payment(payment_request: CreatePaymentRequest, request: Request):
    """Create Mercado Pago payment preference for subscription"""
    user = await get_current_user(request, db)

    existing = await db.subscriptions.find_one(
        {"user_id": user["user_id"], "status": "active"}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes una suscripción activa")

    plan = await db.subscription_plans.find_one(
        {"plan_id": payment_request.plan_id, "active": True},
        {"_id": 0}
    )
    if not plan:
        raise HTTPException(status_code=400, detail="Plan no válido")

    subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
    subscription = {
        "subscription_id": subscription_id,
        "user_id": user["user_id"],
        "plan_id": payment_request.plan_id,
        "status": "pending",
        "mercadopago_payment_id": None,
        "start_date": None,
        "end_date": None,
        "auto_renew": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.subscriptions.insert_one(subscription)

    try:
        mp_service = get_mercadopago_service()

        frontend_url = os.environ.get('CORS_ORIGINS', 'https://senioradvisor.cl').split(',')[0]
        if frontend_url == '*':
            frontend_url = 'https://senioradvisor.cl'

        backend_url = str(request.base_url).rstrip('/')
        notification_url = f"{backend_url}/api/webhooks/mercadopago"

        preference = mp_service.create_payment_preference(
            subscription_id=subscription_id,
            plan_name=plan["name"],
            amount=float(plan["price_clp"]),
            payer_email=user.get("email", "user@example.com"),
            back_url=frontend_url,
            notification_url=notification_url
        )

        await db.subscriptions.update_one(
            {"subscription_id": subscription_id},
            {"$set": {"mercadopago_preference_id": preference["preference_id"]}}
        )

        return {
            "subscription_id": subscription_id,
            "preference_id": preference["preference_id"],
            "checkout_url": preference["init_point"],
            "sandbox_url": preference.get("sandbox_init_point")
        }

    except Exception as e:
        logger.error(f"Error creating Mercado Pago preference: {str(e)}")
        await db.subscriptions.delete_one({"subscription_id": subscription_id})
        raise HTTPException(status_code=500, detail="Error al crear el pago")


@router.post("/webhooks/mercadopago")
async def handle_mercadopago_webhook(request: Request):
    """Handle Mercado Pago webhook notifications"""
    try:
        payload = await request.json()
        logger.info(f"Mercado Pago webhook received: {payload}")

        notification_type = payload.get("type")
        data = payload.get("data", {})

        if notification_type == "payment":
            payment_id = data.get("id")
            if payment_id:
                await process_payment_notification(payment_id)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return {"status": "error", "message": str(e)}


async def process_payment_notification(payment_id: int):
    """Process payment notification and update subscription status"""
    try:
        mp_service = get_mercadopago_service()
        payment = mp_service.get_payment(payment_id)

        status = payment.get("status")
        external_reference = payment.get("external_reference")

        if not external_reference:
            logger.warning(f"Payment {payment_id} has no external_reference")
            return

        subscription = await db.subscriptions.find_one(
            {"subscription_id": external_reference}
        )
        if not subscription:
            logger.warning(f"Subscription not found: {external_reference}")
            return

        plan_doc = await db.subscription_plans.find_one(
            {"plan_id": subscription.get("plan_id")}, {"_id": 0}
        )
        duration_months = plan_doc["duration_months"] if plan_doc else 1

        if status == "approved":
            start_date = datetime.now(timezone.utc)
            end_date = start_date + timedelta(days=30 * duration_months)

            await db.subscriptions.update_one(
                {"subscription_id": external_reference},
                {"$set": {
                    "status": "active",
                    "mercadopago_payment_id": payment_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            logger.info(f"Subscription {external_reference} activated!")

        elif status in ["rejected", "cancelled"]:
            await db.subscriptions.update_one(
                {"subscription_id": external_reference},
                {"$set": {
                    "status": "cancelled",
                    "mercadopago_payment_id": payment_id,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            logger.info(f"Subscription {external_reference} cancelled")

        elif status == "pending":
            await db.subscriptions.update_one(
                {"subscription_id": external_reference},
                {"$set": {
                    "status": "pending",
                    "mercadopago_payment_id": payment_id,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

    except Exception as e:
        logger.error(f"Error processing payment {payment_id}: {str(e)}")


@router.get("/subscription/verify/{subscription_id}")
async def verify_subscription_payment(subscription_id: str, request: Request):
    """Verify subscription payment status"""
    user = await get_current_user(request, db)

    subscription = await db.subscriptions.find_one(
        {"subscription_id": subscription_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    if subscription.get("status") == "pending":
        try:
            mp_service = get_mercadopago_service()
            payments = mp_service.search_payments(subscription_id)

            for payment_data in payments.get("results", []):
                if payment_data.get("status") == "approved":
                    await process_payment_notification(payment_data.get("id"))
                    subscription = await db.subscriptions.find_one(
                        {"subscription_id": subscription_id},
                        {"_id": 0}
                    )
                    break
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")

    return subscription


@router.post("/subscription/create")
async def create_subscription(subscription_data: SubscriptionCreate, request: Request):
    """Create subscription (legacy endpoint)"""
    user = await get_current_user(request, db)

    existing = await db.subscriptions.find_one(
        {"user_id": user["user_id"], "status": "active"}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes una suscripción activa")

    plan = await db.subscription_plans.find_one(
        {"plan_id": subscription_data.plan_id, "active": True}, {"_id": 0}
    )
    if not plan:
        raise HTTPException(status_code=400, detail="Plan no válido")

    subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=30 * plan["duration_months"])

    subscription = {
        "subscription_id": subscription_id,
        "user_id": user["user_id"],
        "plan_id": subscription_data.plan_id,
        "status": "active",
        "mercadopago_subscription_id": None,
        "start_date": start_date,
        "end_date": end_date,
        "auto_renew": True,
        "created_at": datetime.now(timezone.utc)
    }
    await db.subscriptions.insert_one(subscription)
    subscription.pop("_id", None)
    return subscription


@router.get("/subscription/my")
async def get_my_subscription(request: Request):
    """Get current user's subscription"""
    user = await get_current_user(request, db)

    subscription = await db.subscriptions.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0}
    )
    if not subscription:
        return {"has_subscription": False}

    is_active = subscription.get("status") == "active"
    return {
        "has_subscription": is_active,
        **subscription
    }


@router.get("/subscription/invoices")
async def get_subscription_invoices(request: Request):
    """Get subscription payment history / invoices for current user"""
    user = await get_current_user(request, db)

    subscriptions = await db.subscriptions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    invoices = []
    for sub in subscriptions:
        plan = await db.subscription_plans.find_one(
            {"plan_id": sub.get("plan_id")},
            {"_id": 0, "name": 1, "price_clp": 1, "duration_months": 1}
        )
        invoice = {
            "subscription_id": sub.get("subscription_id"),
            "plan_name": plan["name"] if plan else "Plan SeniorAdvisor",
            "amount": plan["price_clp"] if plan else 9990,
            "status": sub.get("status", "unknown"),
            "start_date": sub.get("start_date").isoformat() if sub.get("start_date") else None,
            "end_date": sub.get("end_date").isoformat() if sub.get("end_date") else None,
            "created_at": sub.get("created_at").isoformat() if sub.get("created_at") else None,
            "payment_id": sub.get("mercadopago_payment_id"),
        }
        invoices.append(invoice)

    return invoices
