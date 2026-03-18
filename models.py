from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    CLIENT = "client"
    PROVIDER = "provider"
    ADMIN = "admin"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    PENDING = "pending"

class ServiceType(str, Enum):
    RESIDENCIAS = "residencias"
    CUIDADO_DOMICILIO = "cuidado-domicilio"
    SALUD_MENTAL = "salud-mental"

class RequestStatus(str, Enum):
    NEW = "new"
    CHATTING = "chatting"
    CLOSED = "closed"
    ARCHIVED = "archived"

class PetSize(str, Enum):
    SMALL = "pequeno"
    MEDIUM = "mediano"
    LARGE = "grande"

# User Models
class User(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    role: UserRole = UserRole.CLIENT
    phone: Optional[str] = None
    created_at: datetime

class UserSession(BaseModel):
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime

# Pet Models
class Pet(BaseModel):
    pet_id: str
    user_id: str
    name: str
    species: str  # perro, gato
    breed: Optional[str] = None
    size: PetSize
    age: Optional[int] = None
    sex: Optional[str] = None
    photo: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

class PetCreate(BaseModel):
    name: str
    species: str = "perro"
    breed: Optional[str] = None
    size: str = "mediano"
    age: Optional[int] = None
    sex: Optional[str] = None
    photo: Optional[str] = None
    notes: Optional[str] = None

# Provider Models
class Provider(BaseModel):
    provider_id: str
    user_id: str
    business_name: str
    description: Optional[str] = None
    address: str
    comuna: str  # comuna/ciudad
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: str
    whatsapp: Optional[str] = None
    photos: List[str] = Field(default_factory=list)
    verified: bool = False
    rating: float = 0.0
    total_reviews: int = 0
    coverage_zone: Optional[str] = None  # radio en km
    created_at: datetime
    approved: bool = False
    approved_at: Optional[datetime] = None

class ServiceInput(BaseModel):
    service_type: str  # paseo, petsitter, alojamiento
    price_from: Optional[float] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    pet_sizes: List[str] = Field(default_factory=list)


class ProviderCreate(BaseModel):
    business_name: str
    description: Optional[str] = None
    address: str
    comuna: str
    phone: str
    whatsapp: Optional[str] = None
    photos: List[str] = Field(default_factory=list)
    coverage_zone: Optional[str] = None
    services_offered: List[ServiceInput] = Field(default_factory=list)
    always_active: bool = True
    available_dates: List[str] = Field(default_factory=list)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # Verification documents
    id_front_photo: Optional[str] = None
    id_back_photo: Optional[str] = None
    selfie_photo: Optional[str] = None
    background_certificate: Optional[str] = None


class ProviderUpdate(BaseModel):
    business_name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    comuna: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    photos: Optional[List[str]] = None
    coverage_zone: Optional[str] = None
    always_active: Optional[bool] = None
    available_dates: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    service_comunas: Optional[List[str]] = None
    walking_zones: Optional[List[str]] = None
    coverage_radius_km: Optional[int] = None

# Service Models
class Service(BaseModel):
    service_id: str
    provider_id: str
    service_type: ServiceType
    price_from: Optional[float] = None  # precio referencial "desde"
    description: Optional[str] = None
    rules: Optional[str] = None
    availability: Optional[str] = None
    pet_sizes: List[PetSize] = Field(default_factory=list)
    created_at: datetime

class ServiceCreate(BaseModel):
    service_type: ServiceType
    price_from: Optional[float] = None
    description: Optional[str] = None
    rules: Optional[str] = None
    availability: Optional[str] = None
    pet_sizes: List[PetSize] = Field(default_factory=list)

# Subscription Models
class SubscriptionPlan(BaseModel):
    plan_id: str
    name: str
    duration_months: int  # 1, 3, 12
    price_clp: int
    mercadopago_plan_id: Optional[str] = None

class Subscription(BaseModel):
    subscription_id: str
    user_id: str
    plan_id: str
    status: SubscriptionStatus
    mercadopago_subscription_id: Optional[str] = None
    start_date: datetime
    end_date: datetime
    auto_renew: bool = True
    created_at: datetime

class SubscriptionCreate(BaseModel):
    plan_id: str
    card_token: str

# Review Models
class Review(BaseModel):
    review_id: str
    provider_id: str
    user_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    moderated: bool = False
    approved: bool = True
    created_at: datetime

class ReviewCriteria(BaseModel):
    personal: int = Field(ge=1, le=5, description="Trato y cuidado del personal")
    instalaciones: int = Field(ge=1, le=5, description="Calidad de las instalaciones")
    visitas: int = Field(ge=1, le=5, description="Tiempo para visitas")
    comida: int = Field(ge=1, le=5, description="Comida y nutrición")
    actividades: int = Field(ge=1, le=5, description="Actividades y bienestar")

class ReviewCreate(BaseModel):
    provider_id: str
    rating: float = Field(ge=1, le=5)  # Promedio calculado
    criteria: Optional[ReviewCriteria] = None  # Los 5 criterios individuales
    comment: Optional[str] = None
    photos: Optional[List[str]] = []


class ClientReviewCreate(BaseModel):
    client_user_id: str
    rating: int = Field(ge=1, le=5)
    punctuality: Optional[int] = Field(default=None, ge=1, le=5)
    pet_behavior: Optional[int] = Field(default=None, ge=1, le=5)
    communication: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = None

# Favorite Models
class Favorite(BaseModel):
    favorite_id: str
    user_id: str
    provider_id: str
    created_at: datetime

# Chat Models
class ChatMessage(BaseModel):
    message_id: str
    conversation_id: str
    sender_id: str
    receiver_id: str
    message: str
    read: bool = False
    created_at: datetime

class ChatMessageCreate(BaseModel):
    receiver_id: str
    message: str

# Request Models
class Request(BaseModel):
    request_id: str
    user_id: str
    provider_id: str
    service_type: ServiceType
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    pet_info: Optional[str] = None
    status: RequestStatus = RequestStatus.NEW
    notes: Optional[str] = None
    created_at: datetime

class RequestCreate(BaseModel):
    provider_id: str
    service_type: ServiceType
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    pet_info: Optional[str] = None
    notes: Optional[str] = None

# Search/Filter Models
class ProviderSearchFilters(BaseModel):
    comuna: Optional[str] = None
    service_type: Optional[ServiceType] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    pet_size: Optional[PetSize] = None
    verified_only: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[float] = None
