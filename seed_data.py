import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import uuid

load_dotenv(Path(__file__).parent / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

async def clear_collections():
    print("Limpiando colecciones...")
    for col in ['users', 'providers', 'services', 'reviews', 'subscription_plans']:
        await db[col].delete_many({})
    print("Colecciones limpiadas")

async def seed_plans():
    print("Creando planes de suscripcion...")
    plans = [
        {
            "plan_id": "plan_1month",
            "name": "Plan 1 Mes",
            "duration_months": 1,
            "price_clp": 9990,
            "features": [
                "Ver telefono y WhatsApp de proveedores",
                "Chat interno ilimitado",
                "Enviar solicitudes",
                "Contacto directo"
            ],
            "popular": False,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        },
        {
            "plan_id": "plan_3months",
            "name": "Plan 3 Meses",
            "duration_months": 3,
            "price_clp": 24990,
            "features": [
                "Ver telefono y WhatsApp de proveedores",
                "Chat interno ilimitado",
                "Enviar solicitudes",
                "Contacto directo",
                "17% de descuento"
            ],
            "popular": True,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        },
        {
            "plan_id": "plan_12months",
            "name": "Plan 12 Meses",
            "duration_months": 12,
            "price_clp": 79990,
            "features": [
                "Ver telefono y WhatsApp de proveedores",
                "Chat interno ilimitado",
                "Enviar solicitudes",
                "Contacto directo",
                "33% de descuento",
                "Mejor valor"
            ],
            "popular": False,
            "active": True,
            "created_at": datetime.now(timezone.utc)
        }
    ]
    result = await db.subscription_plans.insert_many(plans)
    print(f"{len(result.inserted_ids)} planes creados")

async def seed_providers():
    print("Creando proveedores de ejemplo...")
    providers_data = [
        {
            "provider_id": f"prov_{uuid.uuid4().hex[:12]}",
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "business_name": "Paseadores Felices",
            "description": "Equipo de paseadores profesionales con mas de 5 anos de experiencia. Amamos a los perros.",
            "address": "Av. Providencia 1234",
            "comuna": "Providencia",
            "latitude": -33.4250,
            "longitude": -70.6109,
            "phone": "+56912345678",
            "whatsapp": "56912345678",
            "photos": ["https://images.unsplash.com/photo-1548199973-03cce0bbc87b?w=800&h=600&fit=crop"],
            "verified": True, "rating": 4.8, "total_reviews": 45, "coverage_zone": "5km",
            "created_at": datetime.now(timezone.utc), "approved": True, "approved_at": datetime.now(timezone.utc)
        },
        {
            "provider_id": f"prov_{uuid.uuid4().hex[:12]}",
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "business_name": "Guarderia Canina Las Condes",
            "description": "Guarderia especializada en perros de todos los tamanos. Amplias instalaciones y personal 24h.",
            "address": "Av. Apoquindo 5678",
            "comuna": "Las Condes",
            "latitude": -33.4088,
            "longitude": -70.5752,
            "phone": "+56923456789",
            "whatsapp": "56923456789",
            "photos": ["https://images.pexels.com/photos/6131149/pexels-photo-6131149.jpeg?auto=compress&cs=tinysrgb&w=800"],
            "verified": True, "rating": 4.9, "total_reviews": 78, "coverage_zone": "10km",
            "created_at": datetime.now(timezone.utc), "approved": True, "approved_at": datetime.now(timezone.utc)
        },
        {
            "provider_id": f"prov_{uuid.uuid4().hex[:12]}",
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "business_name": "Hotel Canino Santiago",
            "description": "Hotel boutique para mascotas con habitaciones individuales y atencion personalizada.",
            "address": "Av. Libertador Bernardo O'Higgins 9012",
            "comuna": "Santiago Centro",
            "latitude": -33.4489,
            "longitude": -70.6693,
            "phone": "+56934567890",
            "whatsapp": "56934567890",
            "photos": ["https://images.unsplash.com/photo-1422565096762-bdb997a56a84?w=800&h=600&fit=crop"],
            "verified": True, "rating": 4.7, "total_reviews": 32, "coverage_zone": "15km",
            "created_at": datetime.now(timezone.utc), "approved": True, "approved_at": datetime.now(timezone.utc)
        },
        {
            "provider_id": f"prov_{uuid.uuid4().hex[:12]}",
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "business_name": "Paseadores Nunoa",
            "description": "Servicio de paseo de perros en Nunoa. Paseadores certificados con experiencia.",
            "address": "Av. Irarrazaval 3456",
            "comuna": "Nunoa",
            "latitude": -33.4572,
            "longitude": -70.5973,
            "phone": "+56945678901",
            "whatsapp": "56945678901",
            "photos": ["https://images.unsplash.com/photo-1601758228041-f3b2795255f1?w=800&h=600&fit=crop"],
            "verified": False, "rating": 4.5, "total_reviews": 18, "coverage_zone": "8km",
            "created_at": datetime.now(timezone.utc), "approved": True, "approved_at": datetime.now(timezone.utc)
        },
        {
            "provider_id": f"prov_{uuid.uuid4().hex[:12]}",
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "business_name": "Cuidado Canino Maipu",
            "description": "Guarderia diurna con juegos al aire libre. Instalaciones seguras.",
            "address": "Av. Pajaritos 7890",
            "comuna": "Maipu",
            "latitude": -33.5110,
            "longitude": -70.7561,
            "phone": "+56956789012",
            "whatsapp": "56956789012",
            "photos": ["https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=600&fit=crop"],
            "verified": True, "rating": 4.6, "total_reviews": 25, "coverage_zone": "12km",
            "created_at": datetime.now(timezone.utc), "approved": True, "approved_at": datetime.now(timezone.utc)
        }
    ]
    result = await db.providers.insert_many(providers_data)
    print(f"{len(result.inserted_ids)} proveedores creados")
    return providers_data

async def seed_services(providers_data):
    print("Creando servicios...")
    services_data = [
        {"service_id": f"serv_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[0]["provider_id"],
         "service_type": "paseo", "price_from": 8000, "description": "Paseos de 30 min a 1 hora",
         "rules": "Perro con collar y correa. Vacunas al dia.", "availability": "Lun-Dom, 8-20h",
         "pet_sizes": ["pequeno", "mediano", "grande"], "created_at": datetime.now(timezone.utc)},
        {"service_id": f"serv_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[1]["provider_id"],
         "service_type": "guarderia", "price_from": 15000, "description": "Cuidado diurno con actividades",
         "rules": "Vacunacion requerida. Perros sociables.", "availability": "Lun-Vie, 7-19h",
         "pet_sizes": ["pequeno", "mediano", "grande"], "created_at": datetime.now(timezone.utc)},
        {"service_id": f"serv_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[1]["provider_id"],
         "service_type": "alojamiento", "price_from": 25000, "description": "Alojamiento con supervision 24/7",
         "rules": "Reserva 48h antes. Vacunas al dia.", "availability": "Todos los dias",
         "pet_sizes": ["pequeno", "mediano"], "created_at": datetime.now(timezone.utc)},
        {"service_id": f"serv_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[2]["provider_id"],
         "service_type": "alojamiento", "price_from": 30000, "description": "Habitaciones individuales premium",
         "rules": "Certificado veterinario obligatorio.", "availability": "Todos los dias",
         "pet_sizes": ["pequeno", "mediano", "grande"], "created_at": datetime.now(timezone.utc)},
        {"service_id": f"serv_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[3]["provider_id"],
         "service_type": "paseo", "price_from": 7000, "description": "Paseos personalizados",
         "rules": "Vacuna antirrabica al dia.", "availability": "Lun-Sab, 9-18h",
         "pet_sizes": ["pequeno", "mediano"], "created_at": datetime.now(timezone.utc)},
        {"service_id": f"serv_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[4]["provider_id"],
         "service_type": "guarderia", "price_from": 12000, "description": "Guarderia con juegos al aire libre",
         "rules": "Perros sociables. Vacunas requeridas.", "availability": "Lun-Vie, 8-18h",
         "pet_sizes": ["pequeno", "mediano", "grande"], "created_at": datetime.now(timezone.utc)}
    ]
    result = await db.services.insert_many(services_data)
    print(f"{len(result.inserted_ids)} servicios creados")

async def seed_reviews(providers_data):
    print("Creando resenas...")
    reviews_data = [
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[0]["provider_id"],
         "user_id": f"user_{uuid.uuid4().hex[:12]}", "rating": 5,
         "comment": "Excelente servicio! Mi perro siempre vuelve feliz.", "moderated": True, "approved": True,
         "created_at": datetime.now(timezone.utc) - timedelta(days=15)},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[0]["provider_id"],
         "user_id": f"user_{uuid.uuid4().hex[:12]}", "rating": 5,
         "comment": "Muy profesionales, envian fotos durante el paseo.", "moderated": True, "approved": True,
         "created_at": datetime.now(timezone.utc) - timedelta(days=8)},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[1]["provider_id"],
         "user_id": f"user_{uuid.uuid4().hex[:12]}", "rating": 5,
         "comment": "La mejor guarderia! Instalaciones impecables.", "moderated": True, "approved": True,
         "created_at": datetime.now(timezone.utc) - timedelta(days=20)},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[1]["provider_id"],
         "user_id": f"user_{uuid.uuid4().hex[:12]}", "rating": 5,
         "comment": "Mi perra adora ir! Siempre esta emocionada.", "moderated": True, "approved": True,
         "created_at": datetime.now(timezone.utc) - timedelta(days=5)},
        {"review_id": f"rev_{uuid.uuid4().hex[:12]}", "provider_id": providers_data[2]["provider_id"],
         "user_id": f"user_{uuid.uuid4().hex[:12]}", "rating": 5,
         "comment": "Hotel de lujo para perros. Muy bien cuidado.", "moderated": True, "approved": True,
         "created_at": datetime.now(timezone.utc) - timedelta(days=30)}
    ]
    result = await db.reviews.insert_many(reviews_data)
    print(f"{len(result.inserted_ids)} resenas creadas")

async def main():
    print("=== Seed de datos U-CAN ===\n")
    await clear_collections()
    await seed_plans()
    providers_data = await seed_providers()
    await seed_services(providers_data)
    await seed_reviews(providers_data)
    print("\n=== Seed completado! ===")
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
