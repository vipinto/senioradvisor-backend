"""
Mercado Pago Payment Service for SeniorAdvisor
"""
import mercadopago
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class MercadoPagoService:
    """Service for Mercado Pago API interactions"""
    
    def __init__(self):
        access_token = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')
        if not access_token:
            raise ValueError("MERCADOPAGO_ACCESS_TOKEN not configured")
        
        self.sdk = mercadopago.SDK(access_token)
        self.client_id = os.environ.get('MERCADOPAGO_CLIENT_ID')
    
    def create_payment_preference(
        self,
        subscription_id: str,
        plan_name: str,
        amount: float,
        payer_email: str,
        back_url: str,
        notification_url: str
    ) -> Dict[str, Any]:
        """
        Create a payment preference for subscription.
        Returns the preference data including init_point for checkout.
        """
        try:
            preference_data = {
                "external_reference": subscription_id,
                "items": [
                    {
                        "id": subscription_id,
                        "title": f"SeniorAdvisor - {plan_name}",
                        "description": f"Suscripción {plan_name} - Plan para proveedores de servicios",
                        "quantity": 1,
                        "currency_id": "CLP",
                        "unit_price": amount
                    }
                ],
                "payer": {
                    "email": payer_email
                },
                "back_urls": {
                    "success": f"{back_url}/payment/success",
                    "failure": f"{back_url}/payment/failure",
                    "pending": f"{back_url}/payment/pending"
                },
                "auto_return": "approved",
                "notification_url": notification_url,
                "statement_descriptor": "SENIORADVISOR"
            }
            
            result = self.sdk.preference().create(preference_data)
            
            if result["status"] != 201:
                logger.error(f"Failed to create preference: {result}")
                raise Exception(f"Mercado Pago error: {result.get('response')}")
            
            preference = result["response"]
            logger.info(f"Preference created: {preference['id']}")
            
            return {
                "preference_id": preference["id"],
                "init_point": preference["init_point"],
                "sandbox_init_point": preference.get("sandbox_init_point"),
                "external_reference": subscription_id
            }
            
        except Exception as e:
            logger.error(f"Error creating preference: {str(e)}")
            raise

    def get_payment(self, payment_id: int) -> Dict[str, Any]:
        """
        Retrieve payment details from Mercado Pago API.
        Used to verify payment status when webhook is received.
        """
        try:
            result = self.sdk.payment().get(payment_id)
            
            if result["status"] != 200:
                logger.error(f"Failed to get payment: {result}")
                raise Exception(f"Mercado Pago error: {result.get('response')}")
            
            return result["response"]
            
        except Exception as e:
            logger.error(f"Error retrieving payment: {str(e)}")
            raise

    def search_payments(self, external_reference: str) -> Dict[str, Any]:
        """
        Search payments by external reference.
        """
        try:
            filters = {
                "external_reference": external_reference
            }
            result = self.sdk.payment().search(filters)
            
            if result["status"] != 200:
                logger.error(f"Failed to search payments: {result}")
                return {"results": []}
            
            return result["response"]
            
        except Exception as e:
            logger.error(f"Error searching payments: {str(e)}")
            return {"results": []}


def get_mercadopago_service() -> MercadoPagoService:
    """Factory function to get MercadoPago service instance"""
    return MercadoPagoService()
