import os
import resend
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Initialize Resend
resend.api_key = os.environ.get("RESEND_API_KEY", "")

# Default sender email (must be verified in Resend)
DEFAULT_FROM_EMAIL = "SeniorAdvisor <noreply@senioradvisor.cl>"
FALLBACK_FROM_EMAIL = "SeniorAdvisor <onboarding@resend.dev>"  # Resend's test domain

# Base URL for email links
FRONTEND_BASE_URL = os.environ.get("FRONTEND_URL", "https://senioradvisor.cl")


async def send_email(
    to: str,
    subject: str,
    html: str,
    from_email: Optional[str] = None
) -> bool:
    """Send an email using Resend API"""
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not configured, skipping email")
        return False
    
    try:
        params = {
            "from": from_email or DEFAULT_FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {to}: {response.get('id', 'unknown')}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {str(e)}")
        return False


# ============= EMAIL TEMPLATES =============

def booking_request_email(
    provider_name: str,
    client_name: str,
    service_type: str,
    start_date: str,
    end_date: str,
    pet_names: list,
    notes: str = ""
) -> tuple:
    """Email to provider when they receive a new booking request"""
    subject = f"Nueva solicitud de reserva - {client_name}"
    
    pets_text = ", ".join(pet_names) if pet_names else "No especificada"
    notes_section = f"""
        <div style="background: #FFF3CD; border-radius: 8px; padding: 12px; margin-top: 16px;">
            <strong>Notas del cliente:</strong><br>
            {notes}
        </div>
    """ if notes else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #E6202E; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 12px 12px; }}
            .info-box {{ background: white; border-radius: 8px; padding: 16px; margin: 16px 0; }}
            .button {{ display: inline-block; background: #E6202E; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">Nueva Reserva</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{provider_name}</strong>,</p>
                <p>Tienes una nueva solicitud de reserva:</p>
                
                <div class="info-box">
                    <p><strong>Cliente:</strong> {client_name}</p>
                    <p><strong>Servicio:</strong> {service_type.capitalize()}</p>
                    <p><strong>Fecha:</strong> {start_date} - {end_date}</p>
                    <p><strong>Detalles:</strong> {pets_text}</p>
                </div>
                
                {notes_section}
                
                <p style="text-align: center; margin-top: 24px;">
                    <a href="{FRONTEND_BASE_URL}/provider/dashboard" class="button">
                        Ver Reserva
                    </a>
                </p>
                
                <p style="color: #666; font-size: 14px; margin-top: 24px;">
                    Recuerda confirmar o rechazar la reserva lo antes posible.
                </p>
            </div>
            <div class="footer">
                <p>Este email fue enviado por SeniorAdvisor</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def booking_confirmed_email(
    client_name: str,
    provider_name: str,
    service_type: str,
    start_date: str,
    end_date: str,
    provider_notes: str = ""
) -> tuple:
    """Email to client when their booking is confirmed"""
    subject = f"¡Reserva confirmada! - {provider_name}"
    
    notes_section = f"""
        <div style="background: #D4EDDA; border-radius: 8px; padding: 12px; margin-top: 16px;">
            <strong>Mensaje del proveedor:</strong><br>
            {provider_notes}
        </div>
    """ if provider_notes else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28A745; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 12px 12px; }}
            .info-box {{ background: white; border-radius: 8px; padding: 16px; margin: 16px 0; }}
            .button {{ display: inline-block; background: #E6202E; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">¡Reserva Confirmada!</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{client_name}</strong>,</p>
                <p>Tu reserva ha sido confirmada:</p>
                
                <div class="info-box">
                    <p><strong>Servicio:</strong> {provider_name}</p>
                    <p><strong>Servicio:</strong> {service_type.capitalize()}</p>
                    <p><strong>Fecha:</strong> {start_date} - {end_date}</p>
                </div>
                
                {notes_section}
                
                <p style="text-align: center; margin-top: 24px;">
                    <a href="{FRONTEND_BASE_URL}/mis-reservas" class="button">
                        Ver Mis Reservas
                    </a>
                </p>
            </div>
            <div class="footer">
                <p>Este email fue enviado por SeniorAdvisor</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def booking_rejected_email(
    client_name: str,
    provider_name: str,
    service_type: str,
    provider_notes: str = ""
) -> tuple:
    """Email to client when their booking is rejected"""
    subject = f"Reserva no disponible - {provider_name}"
    
    notes_section = f"""
        <div style="background: #FFF3CD; border-radius: 8px; padding: 12px; margin-top: 16px;">
            <strong>Mensaje del proveedor:</strong><br>
            {provider_notes}
        </div>
    """ if provider_notes else ""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #6C757D; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 12px 12px; }}
            .info-box {{ background: white; border-radius: 8px; padding: 16px; margin: 16px 0; }}
            .button {{ display: inline-block; background: #E6202E; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">Reserva No Disponible</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{client_name}</strong>,</p>
                <p>Lamentablemente, <strong>{provider_name}</strong> no puede aceptar tu reserva de <strong>{service_type}</strong> en este momento.</p>
                
                {notes_section}
                
                <p>No te preocupes, hay muchos otros servicios disponibles:</p>
                
                <p style="text-align: center; margin-top: 24px;">
                    <a href="{FRONTEND_BASE_URL}/search" class="button">
                        Buscar Otros Servicios
                    </a>
                </p>
            </div>
            <div class="footer">
                <p>Este email fue enviado por SeniorAdvisor</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def new_message_email(
    recipient_name: str,
    sender_name: str,
    message_preview: str
) -> tuple:
    """Email notification for new chat message"""
    subject = f"Nuevo mensaje de {sender_name}"
    
    # Truncate message preview
    preview = message_preview[:200] + "..." if len(message_preview) > 200 else message_preview
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #E6202E; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 12px 12px; }}
            .message-box {{ background: white; border-left: 4px solid #E6202E; border-radius: 4px; padding: 16px; margin: 16px 0; font-style: italic; color: #555; }}
            .button {{ display: inline-block; background: #E6202E; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">Nuevo Mensaje</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{recipient_name}</strong>,</p>
                <p><strong>{sender_name}</strong> te ha enviado un mensaje:</p>
                
                <div class="message-box">
                    "{preview}"
                </div>
                
                <p style="text-align: center; margin-top: 24px;">
                    <a href="{FRONTEND_BASE_URL}/chat" class="button">
                        Responder
                    </a>
                </p>
            </div>
            <div class="footer">
                <p>Este email fue enviado por SeniorAdvisor</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html


def care_request_contact_email(
    client_name: str,
    client_email: str,
    provider_name: str,
    service_type: str,
    pet_name: str,
    description: str
) -> tuple:
    """Email to client when a provider contacts them about their care request"""
    subject = f"¡Un servicio quiere contactarte! - {provider_name}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28A745; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 12px 12px; }}
            .info-box {{ background: white; border-radius: 8px; padding: 16px; margin: 16px 0; }}
            .button {{ display: inline-block; background: #E6202E; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">¡Buenas Noticias!</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{client_name}</strong>,</p>
                <p>El servicio <strong>{provider_name}</strong> está interesado en tu solicitud de servicio para <strong>{pet_name}</strong>.</p>
                
                <div class="info-box">
                    <p><strong>Tu solicitud:</strong> {service_type.capitalize()}</p>
                    <p><strong>Descripción:</strong> {description[:100]}...</p>
                </div>
                
                <p>Revisa sus mensajes y coordina los detalles:</p>
                
                <p style="text-align: center; margin-top: 24px;">
                    <a href="{FRONTEND_BASE_URL}/chat" class="button">
                        Ver Mensajes
                    </a>
                </p>
            </div>
            <div class="footer">
                <p>Este email fue enviado por SeniorAdvisor</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, html



def new_proposal_email(
    client_name: str,
    provider_name: str,
    price: int,
    message: str,
    pet_name: str,
    service_type: str
) -> tuple:
    """Email to client when they receive a new proposal for their care request"""
    subject = f"Nueva propuesta de {provider_name} - ${price:,}".replace(",", ".")

    preview = message[:200] + "..." if len(message) > 200 else message
    price_fmt = f"{price:,}".replace(",", ".")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #E6202E; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center; }}
            .content {{ background: #f8f9fa; padding: 24px; border-radius: 0 0 12px 12px; }}
            .info-box {{ background: white; border-radius: 8px; padding: 16px; margin: 16px 0; }}
            .price {{ font-size: 28px; font-weight: bold; color: #E6202E; }}
            .message-box {{ background: white; border-left: 4px solid #E6202E; border-radius: 4px; padding: 16px; margin: 16px 0; font-style: italic; color: #555; }}
            .button {{ display: inline-block; background: #E6202E; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">Nueva Propuesta</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{client_name}</strong>,</p>
                <p>El servicio <strong>{provider_name}</strong> te envio una propuesta para <strong>{pet_name}</strong>:</p>

                <div class="info-box">
                    <p><strong>Servicio:</strong> {service_type.capitalize()}</p>
                    <p class="price">${price_fmt} CLP</p>
                </div>

                <div class="message-box">
                    "{preview}"
                </div>

                <p style="text-align: center; margin-top: 24px;">
                    <a href="{FRONTEND_BASE_URL}/dashboard" class="button">
                        Ver Propuesta
                    </a>
                </p>

                <p style="color: #666; font-size: 14px; margin-top: 16px;">
                    Puedes aceptar o rechazar esta propuesta desde tu panel de control.
                </p>
            </div>
            <div class="footer">
                <p>Este email fue enviado por SeniorAdvisor</p>
            </div>
        </div>
    </body>
    </html>
    """

    return subject, html