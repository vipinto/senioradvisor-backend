"""
Seed script para crear 10 servicios de prueba en SeniorAdvisor
"""
import asyncio
import uuid
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(Path(__file__).parent / '.env')

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "senioradvisor")

print(f"Conectando a DB: {DB_NAME}")

# 10 Servicios de prueba con diferentes combinaciones de categorías
SERVICIOS = [
    {
        "business_name": "Residencia Los Aromos",
        "description": "Residencia para adultos mayores con atención 24/7, amplios jardines y actividades recreativas diarias. Personal médico permanente.",
        "address": "Av. Los Aromos 1234",
        "comuna": "Las Condes",
        "latitude": -33.4103,
        "longitude": -70.5673,
        "phone": "+56 9 1234 5678",
        "whatsapp": "+56 9 1234 5678",
        "services": [
            {"service_type": "residencias", "price_from": 1500000, "description": "Habitación individual con baño privado"},
            {"service_type": "salud-mental", "price_from": 80000, "description": "Terapia ocupacional y acompañamiento psicológico"}
        ],
        "verified": True,
        "rating": 4.8,
        "total_reviews": 45
    },
    {
        "business_name": "Cuidadores a Domicilio San Carlos",
        "description": "Servicio profesional de cuidadores certificados. Turnos de 8, 12 y 24 horas. Personal con experiencia en adultos mayores.",
        "address": "Calle San Carlos 567",
        "comuna": "Providencia",
        "latitude": -33.4289,
        "longitude": -70.6103,
        "phone": "+56 9 2345 6789",
        "whatsapp": "+56 9 2345 6789",
        "services": [
            {"service_type": "cuidado-domicilio", "price_from": 15000, "description": "Cuidador por hora"},
            {"service_type": "cuidado-domicilio", "price_from": 120000, "description": "Cuidador turno 24 horas"}
        ],
        "verified": True,
        "rating": 4.6,
        "total_reviews": 32
    },
    {
        "business_name": "Centro de Salud Mental Esperanza",
        "description": "Centro especializado en salud mental geriátrica. Psicólogos, psiquiatras y terapeutas especializados en adultos mayores.",
        "address": "Av. Esperanza 890",
        "comuna": "Ñuñoa",
        "latitude": -33.4536,
        "longitude": -70.5983,
        "phone": "+56 9 3456 7890",
        "whatsapp": "+56 9 3456 7890",
        "services": [
            {"service_type": "salud-mental", "price_from": 45000, "description": "Consulta psicológica"},
            {"service_type": "salud-mental", "price_from": 65000, "description": "Consulta psiquiátrica"}
        ],
        "verified": True,
        "rating": 4.9,
        "total_reviews": 78
    },
    {
        "business_name": "Hogar Santa María",
        "description": "Residencia integral con servicios de cuidado y atención médica. Ambiente familiar y cálido para nuestros residentes.",
        "address": "Pasaje Santa María 123",
        "comuna": "La Reina",
        "latitude": -33.4456,
        "longitude": -70.5423,
        "phone": "+56 9 4567 8901",
        "whatsapp": "+56 9 4567 8901",
        "services": [
            {"service_type": "residencias", "price_from": 1200000, "description": "Habitación compartida"},
            {"service_type": "residencias", "price_from": 1800000, "description": "Habitación individual"},
            {"service_type": "cuidado-domicilio", "price_from": 18000, "description": "Cuidador externo por hora"}
        ],
        "verified": True,
        "rating": 4.7,
        "total_reviews": 56
    },
    {
        "business_name": "Psicólogos Senior Care",
        "description": "Equipo de psicólogos especializados en tercera edad. Atención a domicilio y en consulta. Terapia individual y grupal.",
        "address": "Av. Vitacura 4500",
        "comuna": "Vitacura",
        "latitude": -33.3953,
        "longitude": -70.5893,
        "phone": "+56 9 5678 9012",
        "whatsapp": "+56 9 5678 9012",
        "services": [
            {"service_type": "salud-mental", "price_from": 50000, "description": "Terapia individual"},
            {"service_type": "salud-mental", "price_from": 35000, "description": "Terapia grupal"},
            {"service_type": "cuidado-domicilio", "price_from": 60000, "description": "Atención psicológica a domicilio"}
        ],
        "verified": True,
        "rating": 4.8,
        "total_reviews": 89
    },
    {
        "business_name": "Residencia Villa Serena",
        "description": "Residencia de lujo para adultos mayores. Habitaciones amplias, piscina temperada, gimnasio adaptado y chef propio.",
        "address": "Camino El Alba 2000",
        "comuna": "Lo Barnechea",
        "latitude": -33.3543,
        "longitude": -70.5123,
        "phone": "+56 9 6789 0123",
        "whatsapp": "+56 9 6789 0123",
        "services": [
            {"service_type": "residencias", "price_from": 2500000, "description": "Suite premium"},
            {"service_type": "salud-mental", "price_from": 0, "description": "Incluye apoyo psicológico"},
            {"service_type": "cuidado-domicilio", "price_from": 25000, "description": "Cuidador personal adicional"}
        ],
        "verified": True,
        "rating": 4.9,
        "total_reviews": 34
    },
    {
        "business_name": "Enfermeras a Domicilio Chile",
        "description": "Servicio de enfermería profesional a domicilio. Curaciones, administración de medicamentos, control de signos vitales.",
        "address": "Av. Apoquindo 6000",
        "comuna": "Las Condes",
        "latitude": -33.4156,
        "longitude": -70.5789,
        "phone": "+56 9 7890 1234",
        "whatsapp": "+56 9 7890 1234",
        "services": [
            {"service_type": "cuidado-domicilio", "price_from": 25000, "description": "Visita de enfermería"},
            {"service_type": "cuidado-domicilio", "price_from": 180000, "description": "Enfermera turno completo"}
        ],
        "verified": True,
        "rating": 4.7,
        "total_reviews": 67
    },
    {
        "business_name": "Centro Integral Otoño Dorado",
        "description": "Centro día y residencia con todos los servicios. Kinesiología, terapia ocupacional, talleres de memoria y más.",
        "address": "Av. Irarrázaval 3500",
        "comuna": "Ñuñoa",
        "latitude": -33.4489,
        "longitude": -70.6023,
        "phone": "+56 9 8901 2345",
        "whatsapp": "+56 9 8901 2345",
        "services": [
            {"service_type": "residencias", "price_from": 1400000, "description": "Residencia permanente"},
            {"service_type": "cuidado-domicilio", "price_from": 450000, "description": "Centro día (mensual)"},
            {"service_type": "salud-mental", "price_from": 40000, "description": "Talleres de estimulación cognitiva"}
        ],
        "verified": True,
        "rating": 4.6,
        "total_reviews": 92
    },
    {
        "business_name": "Compañía Senior",
        "description": "Servicio de acompañamiento y compañía para adultos mayores. Paseos, trámites, compras y actividades recreativas.",
        "address": "Calle Nueva York 100",
        "comuna": "Santiago Centro",
        "latitude": -33.4372,
        "longitude": -70.6506,
        "phone": "+56 9 9012 3456",
        "whatsapp": "+56 9 9012 3456",
        "services": [
            {"service_type": "cuidado-domicilio", "price_from": 12000, "description": "Acompañamiento por hora"}
        ],
        "verified": False,
        "rating": 4.4,
        "total_reviews": 23
    },
    {
        "business_name": "Residencia y Spa Renacer",
        "description": "Residencia con enfoque en bienestar integral. Spa, masajes, yoga adaptado, meditación y alimentación saludable.",
        "address": "Av. Kennedy 7000",
        "comuna": "Vitacura",
        "latitude": -33.3989,
        "longitude": -70.5756,
        "phone": "+56 9 0123 4567",
        "whatsapp": "+56 9 0123 4567",
        "services": [
            {"service_type": "residencias", "price_from": 2200000, "description": "Habitación con vista al jardín"},
            {"service_type": "salud-mental", "price_from": 55000, "description": "Sesiones de mindfulness y relajación"}
        ],
        "verified": True,
        "rating": 4.8,
        "total_reviews": 41
    }
]

async def seed_providers():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Limpiar proveedores existentes (opcional)
    await db.providers.delete_many({})
    print("Proveedores anteriores eliminados")
    
    # Crear usuarios para cada proveedor y luego el proveedor
    for i, servicio in enumerate(SERVICIOS):
        user_id = str(uuid.uuid4())
        provider_id = str(uuid.uuid4())
        
        # Crear usuario proveedor
        user = {
            "user_id": user_id,
            "email": f"proveedor{i+1}@senioradvisor.cl",
            "name": servicio["business_name"],
            "role": "provider",
            "phone": servicio["phone"],
            "created_at": datetime.utcnow(),
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYWYqjYvKTGi"  # password: demo123
        }
        await db.users.insert_one(user)
        
        # Crear proveedor
        provider = {
            "provider_id": provider_id,
            "user_id": user_id,
            "business_name": servicio["business_name"],
            "description": servicio["description"],
            "address": servicio["address"],
            "comuna": servicio["comuna"],
            "latitude": servicio["latitude"],
            "longitude": servicio["longitude"],
            "phone": servicio["phone"],
            "whatsapp": servicio.get("whatsapp"),
            "photos": [
                f"https://images.unsplash.com/photo-157676560853{i}-5f04d1e3f289?w=800",
                f"https://images.unsplash.com/photo-144706938759{i}-a5de0862481e?w=800"
            ],
            "verified": servicio["verified"],
            "rating": servicio["rating"],
            "total_reviews": servicio["total_reviews"],
            "coverage_zone": "10",
            "created_at": datetime.utcnow(),
            "approved": True,
            "approved_at": datetime.utcnow(),
            "services": servicio["services"]
        }
        await db.providers.insert_one(provider)
        print(f"✅ Creado: {servicio['business_name']}")
    
    print(f"\n🎉 Se crearon {len(SERVICIOS)} servicios de prueba")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_providers())
