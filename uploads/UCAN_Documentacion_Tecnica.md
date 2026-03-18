# U-CAN - Documentación Técnica Completa
## Plataforma de Servicios para Mascotas

**Fecha:** 10 de Marzo de 2026  
**Versión:** 1.0  
**Preparado para:** Presentación Ejecutiva

---

## 1. INFORMACIÓN GENERAL

### 1.1 Descripción del Proyecto
U-CAN es una plataforma web que conecta dueños de mascotas con cuidadores profesionales. Ofrece servicios de paseo, cuidado diurno (daycare) y alojamiento para perros y gatos.

### 1.2 URLs de Acceso

| Entorno | URL |
|---------|-----|
| **Producción/Preview** | https://image-carousel-13.preview.emergentagent.com |
| **API Backend** | https://image-carousel-13.preview.emergentagent.com/api |

---

## 2. CREDENCIALES DE ACCESO (USUARIOS DE PRUEBA)

### 2.1 Usuarios del Sistema

| Rol | Email | Contraseña | Descripción |
|-----|-------|------------|-------------|
| **Admin** | admin@test.com | password123 | Panel de administración |
| **Cuidador** | cuidador@test.com | cuidador123 | Perfil de cuidador completo |
| **Cliente Premium** | cliente@test.com | cliente123 | Cliente con suscripción activa |
| **Cliente Free** | test_client_ui@test.com | test123456 | Cliente sin suscripción |

### 2.2 Notas sobre Usuarios
- El usuario `cliente@test.com` tiene **doble rol** (Cliente + Cuidador)
- Al iniciar sesión con doble rol, se muestra pantalla de selección de perfil

---

## 3. CLAVES DE APIs Y SERVICIOS EXTERNOS

### 3.1 Base de Datos - MongoDB Atlas

| Parámetro | Valor |
|-----------|-------|
| **Proveedor** | MongoDB Atlas |
| **URL de Conexión** | mongodb+srv://victorplopez_db_user:5kOVoKNkHyatKP1k@u-can.qx6mtua.mongodb.net/?appName=u-can |
| **Usuario DB** | victorplopez_db_user |
| **Contraseña DB** | 5kOVoKNkHyatKP1k |
| **Nombre de Base de Datos** | ucan |
| **Cluster** | u-can.qx6mtua.mongodb.net |

### 3.2 Google Cloud Platform

| Servicio | Clave/ID |
|----------|----------|
| **Google Maps API Key** | AIzaSyCQlV-tmctVCQYM-xkFbbwtuvWyWvuriXI |
| **Google OAuth Client ID** | 67293500515-6ptgaosf14l20382gqb0dvjogjcncfms.apps.googleusercontent.com |
| **Google OAuth Client Secret** | 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 |

**Servicios habilitados:**
- Google Maps JavaScript API (para mapas interactivos)
- Google Places API (para búsqueda de direcciones)
- Google OAuth 2.0 (para login social)

### 3.3 MercadoPago (Pagos)

| Parámetro | Valor |
|-----------|-------|
| **Access Token** | APP_USR-4085391020482940-020415-b56a1ecc7271e1da7375156f6bf2aae4-2716055106 |
| **Client ID** | APP_USR-ad3427ed-c78e-402c-89bf-2eb46747a6a3 |
| **Ambiente** | Producción (Chile) |

**Uso:** Procesamiento de pagos para suscripciones Premium

### 3.4 Resend (Emails Transaccionales)

| Parámetro | Valor |
|-----------|-------|
| **API Key** | re_JHUk2HvN_fWiCkTrHiY52K9hvyPn7htP9 |
| **Email Remitente** | no-reply@u-can.cl |

**Uso:** Envío de emails de confirmación, notificaciones, recuperación de contraseña

### 3.5 JWT (Autenticación)

| Parámetro | Valor |
|-----------|-------|
| **Secret Key** | ucan_jwt_s3cr3t_k3y_2026_pr0d |
| **Algoritmo** | HS256 |
| **Expiración** | 7 días |

---

## 4. ARQUITECTURA TÉCNICA

### 4.1 Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| **Frontend** | React 18, TailwindCSS, Shadcn UI |
| **Backend** | Python 3.11, FastAPI |
| **Base de Datos** | MongoDB Atlas |
| **Autenticación** | JWT + Google OAuth |
| **Pagos** | MercadoPago |
| **Emails** | Resend |
| **Mapas** | Google Maps API |
| **Chat en tiempo real** | Socket.IO |

### 4.2 Estructura del Proyecto

```
/app
├── frontend/                 # Aplicación React
│   ├── src/
│   │   ├── components/      # Componentes reutilizables
│   │   ├── pages/           # Páginas de la aplicación
│   │   └── lib/             # Utilidades y API client
│   └── .env                 # Variables de entorno frontend
│
├── backend/                  # API FastAPI
│   ├── routes/              # Endpoints de la API
│   ├── models.py            # Modelos de datos
│   ├── auth.py              # Lógica de autenticación
│   ├── server.py            # Servidor principal
│   ├── uploads/             # Archivos subidos
│   └── .env                 # Variables de entorno backend
│
└── memory/                   # Documentación del proyecto
    └── PRD.md               # Requisitos del producto
```

---

## 5. ENDPOINTS PRINCIPALES DE LA API

### 5.1 Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | /api/auth/register | Registro de usuario |
| POST | /api/auth/login | Inicio de sesión |
| GET | /api/auth/me | Obtener usuario actual |
| POST | /api/auth/select-role | Seleccionar rol (multi-rol) |
| POST | /api/auth/google | Login con Google |

### 5.2 Proveedores/Cuidadores

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | /api/providers | Buscar cuidadores |
| GET | /api/providers/{id} | Perfil de cuidador |
| GET | /api/providers/my-profile | Mi perfil (cuidador) |
| PUT | /api/providers/my-profile | Actualizar perfil |
| POST | /api/providers/my-profile/photo | Subir foto de perfil |
| POST | /api/providers/gallery/upload | Subir foto a galería |

### 5.3 Solicitudes y Reservas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | /api/contact-requests | Enviar solicitud de contacto |
| GET | /api/contact-requests/received | Solicitudes recibidas |
| POST | /api/bookings | Crear reserva |
| GET | /api/bookings/my | Mis reservas |

### 5.4 Suscripciones

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | /api/subscription/my | Mi suscripción |
| POST | /api/subscription/create | Crear suscripción |
| GET | /api/subscription/plans | Planes disponibles |

---

## 6. MODELO DE NEGOCIO

### 6.1 Planes de Suscripción

| Plan | Precio | Beneficios |
|------|--------|------------|
| **Cliente Premium** | $9.990 CLP/mes | Contacto directo con cuidadores, ver datos de contacto |
| **Cuidador Premium** | $7.500 CLP/mes | Perfil destacado, acceso a SOS Emergencia |

### 6.2 Flujo de Privacidad
1. Cliente busca cuidadores (datos de contacto ocultos)
2. Cliente Premium envía solicitud de contacto
3. Cuidador acepta la solicitud
4. Se revelan datos de contacto y se habilita chat

---

## 7. FUNCIONALIDADES IMPLEMENTADAS

### 7.1 Para Clientes
- [x] Búsqueda de cuidadores por zona y servicio
- [x] Visualización de perfiles de cuidadores
- [x] Sistema de favoritos
- [x] Chat con cuidadores conectados
- [x] Gestión de mascotas
- [x] Historial de servicios
- [x] Solicitudes de contacto (Premium)

### 7.2 Para Cuidadores
- [x] Panel de gestión con estadísticas
- [x] Perfil público completo
- [x] Galería de fotos
- [x] Configuración de servicios y precios
- [x] Zonas de servicio
- [x] Calendario de disponibilidad
- [x] "Más Datos" (información personal)
- [x] Sistema de verificación de perfil completo

### 7.3 Sistema Multi-Rol
- [x] Un usuario puede ser Cliente y Cuidador
- [x] Pantalla de selección de rol al login
- [x] Dashboards separados por rol

---

## 8. COLECCIONES DE BASE DE DATOS

| Colección | Descripción |
|-----------|-------------|
| users | Usuarios del sistema |
| providers | Perfiles de cuidadores |
| services | Servicios ofrecidos por cuidadores |
| pets | Mascotas de los clientes |
| subscriptions | Suscripciones activas |
| contact_requests | Solicitudes de contacto |
| connections | Conexiones cliente-cuidador |
| bookings | Reservas de servicios |
| reviews | Reseñas y calificaciones |
| chat_messages | Mensajes del chat |
| favorites | Cuidadores favoritos |

---

## 9. SEGURIDAD

### 9.1 Medidas Implementadas
- Autenticación JWT con expiración
- Contraseñas hasheadas con bcrypt
- CORS configurado
- Validación de datos con Pydantic
- Sanitización de inputs
- Rate limiting en endpoints críticos

### 9.2 Privacidad de Datos
- Datos sensibles de cuidadores ocultos por defecto
- Solo visibles tras aceptación de solicitud de contacto
- Cumplimiento con políticas de privacidad

---

## 10. CONTACTO Y SOPORTE

**Plataforma de Desarrollo:** Emergent Agent  
**Repositorio:** Gestionado internamente  

---

*Documento generado automáticamente el 10 de Marzo de 2026*
