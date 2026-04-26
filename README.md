# App de Confirmación de Asistencia - Cumple Dafne

Esta aplicación está creada con Streamlit y PostgreSQL (Neon) para gestionar los RSVP del cumpleaños infantil de Dafne de manera simple y con un diseño colorido. 

## Tecnologías utilizadas
- Python
- Streamlit
- PostgreSQL (Neon)
- SQLAlchemy
- Pandas

## Pasos para Deploy en Streamlit Cloud

### 1. Crear proyecto en Neon PostgreSQL
1. Ingresa a [Neon.tech](https://neon.tech) y crea un nuevo proyecto o base de datos.
2. Copia el **Connection string** (DATABASE_URL), que se verá similar a `postgresql://usuario:password@host/dbname?sslmode=require`.

### 2. Configurar Repositorio
Sube los archivos de este directorio (`app.py`, `requirements.txt`, etc.) a un repositorio de GitHub público o privado. 

### 3. Crear app en Streamlit Cloud
1. Entra a [Streamlit Cloud](https://streamlit.io/cloud) y conecta tu cuenta de GitHub.
2. Crea una nueva aplicación ("New app") seleccionando el repositorio que acabas de subir.
3. Asegúrate que en "Main file path" figure `app.py`.

### 4. Cargar Secrets en Streamlit Cloud
1. Antes de iniciar la app, ve a **"Advanced settings"** -> **"Secrets"**.
2. Debes cargar las variables de entorno tomando como base `.streamlit/secrets.toml.example`. Pega y completa con tus datos reales:
```toml
DATABASE_URL = "tu_connection_string_de_neon_aqui"
ADMIN_PASSWORD = "tu_clave_secreta_aqui"
```

### 5. Deploy
1. Haz clic en **"Deploy"** y espera que Streamlit instale los requerimientos listados en `requirements.txt` y levante la app.

### 6. Links de Uso
- **Link público para invitados:** 
  `https://nombre-app.streamlit.app`
  *(Los invitados verán la tarjeta infantil para confirmar asistencia).*
- **Link privado panel de administración:** 
  `https://nombre-app.streamlit.app/?admin=1` 
  *(Pedirá la contraseña configurada en `ADMIN_PASSWORD` para ver la lista de asistentes consolidados y descargar el CSV).*
