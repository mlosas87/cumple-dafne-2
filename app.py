import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import datetime
import base64
import os
import hmac
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dafne cumple 2 años · 6 de junio", page_icon="🎈", layout="centered")

@st.cache_data
def set_background(image_file):
    try:
        with open(image_file, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode()

        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: 
                    radial-gradient(at 20% 10%, rgba(255, 193, 7, 0.18) 0%, transparent 50%),
                    radial-gradient(at 80% 80%, rgba(0, 176, 229, 0.18) 0%, transparent 50%),
                    linear-gradient(rgba(255,255,255,0.55), rgba(255,255,255,0.55)),
                    url("data:image/jpg;base64,{encoded}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        st.warning(f"No se encontró la imagen de fondo '{image_file}'. Por favor agrégala a la carpeta.")

set_background("static/fondo.jpg")

# --- DISEÑO CSS ---
@st.cache_data
def load_css(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

st.markdown(f"<style>{load_css('static/styles.css')}</style>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CONFIGURACIÓN LOCAL Y DEPLOYMENT
# -----------------------------------------------------------------------------
# Opción A (Local - Recomendado):
# Crea un archivo en la ruta exacta .streamlit/secrets.toml dentro de la carpeta del proyecto.
# (NO uses rutas como C:\Users\Marian\.streamlit\secrets.toml)
# Con este contenido:
# DATABASE_URL = "postgresql://usuario:password@host/dbname?sslmode=require"
# ADMIN_PASSWORD = "tu_clave"
#
# Opción B (Servidores / Contenedores):
# Configurar las variables de entorno: DATABASE_URL y ADMIN_PASSWORD.
# -----------------------------------------------------------------------------

def get_secret(key, default_value=""):
    # 1) Intentar leer desde Streamlit Secrets
    try:
        # Esto falla controladamente si no encuentra el archivo .streamlit/secrets.toml
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass 
    
    # 2) Fallback a variables de entorno (útil en otros deploys o en local por consola)
    val_env = os.getenv(key)
    if val_env:
        return val_env
        
    # 3) Fallback directo en código
    return default_value

DATABASE_URL_CONFIG = get_secret("DATABASE_URL", "")
ADMIN_PASSWORD_CONFIG = get_secret("ADMIN_PASSWORD", "")

# --- CONEXIÓN DB ---
@st.cache_resource
def init_connection(url):
    if not url:
        return None
    try:
        return create_engine(url)
    except Exception as e:
        st.warning(f"⚠️ Atención: No se pudo conectar a la base de datos (revisar credenciales).")
        return None

engine = init_connection(DATABASE_URL_CONFIG)

def create_table_if_not_exists():
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rsvp_dafne (
                    id SERIAL PRIMARY KEY,
                    family_name TEXT UNIQUE NOT NULL,
                    attendance TEXT NOT NULL CHECK (attendance IN ('SI', 'NO')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            # Parche de seguridad: si la tabla ya había sido creada sin esta columna, se la agregamos.
            conn.execute(text("""
                ALTER TABLE rsvp_dafne ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            """))
            conn.commit()
    except Exception as e:
        st.warning("⚠️ No se pudo inicializar la tabla en base de datos. Algunos servicios podrían fallar.")

if not DATABASE_URL_CONFIG:
    st.error("Error: falta configurar DATABASE_URL (Neon)")
else:
    create_table_if_not_exists()

# --- LÓGICA APP ---
# Obtener param admin
is_admin = st.query_params.get("admin") == "1"

if is_admin:
    st.title("🛠️ Panel Admin - Cumple Dafne")
    
    admin_pass = ADMIN_PASSWORD_CONFIG

    if "admin_attempts" not in st.session_state:
        st.session_state["admin_attempts"] = 0
    if "admin_lock_until" not in st.session_state:
        st.session_state["admin_lock_until"] = 0
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False

    current_time = time.time()
    if current_time < st.session_state["admin_lock_until"]:
        st.warning("Demasiados intentos. Intentá de nuevo en un rato.")
        st.stop()

    if not st.session_state["admin_authenticated"]:
        password_input = st.text_input("Ingresar contraseña:", type="password")
        if password_input:
            # Uso de hmac para mitigar timing attacks
            if hmac.compare_digest(password_input.encode('utf-8'), admin_pass.encode('utf-8')):
                st.session_state["admin_authenticated"] = True
                st.session_state["admin_attempts"] = 0
                st.rerun()
            else:
                st.session_state["admin_attempts"] += 1
                if st.session_state["admin_attempts"] >= 5:
                    st.session_state["admin_lock_until"] = current_time + 300
                    st.error("Demasiados intentos, panel bloqueado.")
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
    
    if st.session_state["admin_authenticated"]:
        st.success("Acceso concedido")
        if st.button("Cerrar sesión"):
            st.session_state["admin_authenticated"] = False
            st.rerun()
        st.write("---")
        
        if engine is None:
            st.warning("⚠️ El panel está inactivo porque no hay conexión a la base de datos.")
            st.stop()
            
        try:
            with engine.connect() as conn:
                df = pd.read_sql("SELECT * FROM rsvp_dafne ORDER BY updated_at DESC", conn)
            
            total_resp = len(df)
            total_si = len(df[df['attendance'] == 'SI'])
            total_no = len(df[df['attendance'] == 'NO'])
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Respuestas", total_resp)
            col2.metric("Total SI", total_si)
            col3.metric("Total NO", total_no)
            
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name="rsvp_dafne.csv",
                mime="text/csv",
            )
            
            st.write("---")
            st.subheader("Eliminar registro")
            with st.form("delete_form"):
                id_eliminar = st.number_input("ID a eliminar", min_value=0, step=1)
                submit_delete = st.form_submit_button("Eliminar")
                if submit_delete:
                    with engine.connect() as conn:
                        conn.execute(text("DELETE FROM rsvp_dafne WHERE id = :id"), {"id": id_eliminar})
                        conn.commit()
                    st.success(f"Registro {id_eliminar} eliminado. Recarga la página.")
                    
        except Exception as e:
            st.error(f"Error al leer datos: {e}")

else:
    # --- VISTA PÚBLICA (INVITADOS) ---

    # Open Graph + favicon SVG
    st.markdown("""
<meta property="og:title" content="Dafne cumple 2 años">
<meta property="og:description" content="6 de junio · 10 a 13 hs · Salón Hakuna Matata. Confirmá tu asistencia.">
<meta property="og:type" content="website">
<meta property="og:image" content="https://raw.githubusercontent.com/mlosas87/cumple-dafne-2/main/static/fondo.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#00b0e5">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cellipse cx='50' cy='42' rx='28' ry='36' fill='%2300b0e5'/%3E%3Cpath d='M50 78 Q53 86 50 96' stroke='%230090c0' stroke-width='3' fill='none' stroke-linecap='round'/%3E%3Cellipse cx='40' cy='30' rx='8' ry='5' fill='white' opacity='0.25' transform='rotate(-30 40 30)'/%3E%3C/svg%3E">
""", unsafe_allow_html=True)



    def render_hero():
        return """
<div style="text-align: center;">
<div class="decoracion">
    <svg viewBox="0 0 200 50" xmlns="http://www.w3.org/2000/svg">
        <path d="M50 25 L60 20 L55 30 Z" fill="#ffc107"/>
        <circle cx="100" cy="25" r="15" fill="#f15a24"/>
        <path d="M100 40 Q105 50 100 60" stroke="#f15a24" stroke-width="2" fill="none"/>
        <path d="M150 25 L140 20 L145 30 Z" fill="#ffc107"/>
        <path d="M30 15 L35 10 L40 18 Z" fill="#00b0e5"/>
        <path d="M170 15 L165 10 L160 18 Z" fill="#00b0e5"/>
    </svg>
</div>
<div class="title-container">
<h1 class="titulo-dafne">DAFNE</h1>
</div>
<h2 class="subtitulo">cumple 2 años</h2>

<div class="wave-divider">
    <svg viewBox="0 0 100 15" xmlns="http://www.w3.org/2000/svg">
        <path d="M0 7.5 Q12.5 0, 25 7.5 T50 7.5 T75 7.5 T100 7.5" />
    </svg>
</div>

<div class="info-section">
<div class="salon">salón</div>
<div class="salon-nombre">HAKUNA MATATA</div>
<div class="salon-dir">
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
    </svg>
    Av. Marconi 49
</div>

<div class="fecha-box">
<div class="fecha-col">
<span class="num" style="color:var(--accent);">6</span>
<span class="txt">junio</span>
</div>
<div class="fecha-divider"></div>
<div class="fecha-col">
<span class="num" style="color:var(--primary);">10</span>
<span class="txt">a 13 hs.</span>
</div>
</div>

<div id="countdown-container"></div>

<div class="destacado">
CONFIRMAR ASISTENCIA
<span class="destacado-sub">hasta el 30 de mayo</span>
</div>
</div>

<script>
function updateCountdown() {
    const targetDate = new Date("2026-06-06T10:00:00-03:00").getTime();
    const now = new Date().getTime();
    const distance = targetDate - now;

    const container = document.getElementById('countdown-container');
    if(!container) return;

    if (distance < 0) {
        container.innerHTML = '<div class="cd-finished">🎉 ¡Ya fue el cumple!</div>';
        return;
    }

    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);

    container.innerHTML = `
        <div class="countdown-wrapper">
            <div class="cd-box"><span class="cd-num">${days}</span><span class="cd-lbl">Días</span></div>
            <div class="cd-box"><span class="cd-num">${hours.toString().padStart(2, '0')}</span><span class="cd-lbl">Hs</span></div>
            <div class="cd-box"><span class="cd-num">${minutes.toString().padStart(2, '0')}</span><span class="cd-lbl">Min</span></div>
            <div class="cd-box"><span class="cd-num">${seconds.toString().padStart(2, '0')}</span><span class="cd-lbl">Seg</span></div>
        </div>
    `;
}
setInterval(updateCountdown, 1000);
updateCountdown();
</script>

</div>
"""
    st.markdown(render_hero(), unsafe_allow_html=True)



    with st.form("rsvp_form"):
        family_name = st.text_input("Nombre de familia (Ej: Familia García)")
        attendance_label = st.radio("¿Asisten?", ["Sí, asistimos", "No podemos ir"], horizontal=True)
        
        submitted = st.form_submit_button("Enviar confirmación ⭐")

        if submitted:
            attendance = "SI" if attendance_label == "Sí, asistimos" else "NO"
            cleaned_name = family_name.strip()
            if not cleaned_name:
                st.warning("⚠️ El nombre de familia no puede estar vacío.")
            else:
                if engine is None:
                    st.error("❌ Ocurrió un error de conexión. Faltan las credenciales de la base de datos.")
                else:
                    with st.spinner("Guardando tu confirmación..."):
                        try:
                            with engine.connect() as conn:
                                result = conn.execute(
                                    text("SELECT id FROM rsvp_dafne WHERE family_name = :name"), 
                                    {"name": cleaned_name}
                                ).fetchone()
                                
                                def render_success(is_update):
                                    msg = "¡Tu confirmación fue actualizada!" if is_update else "¡Gracias! Confirmación registrada."
                                    return f"""
                                    <div class="success-card">
                                        <div class="success-icon">
                                            <svg viewBox="0 0 24 24">
                                                <path class="path" d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                                                <polyline class="path" points="22 4 12 14.01 9 11.01"></polyline>
                                            </svg>
                                        </div>
                                        <div class="success-title">{msg}</div>
                                        <div class="success-text">¡Te esperamos el 6 de junio!</div>
                                    </div>
                                    """
                                
                                if result:
                                    # UPSERT (Actualizar)
                                    conn.execute(text("""
                                        UPDATE rsvp_dafne 
                                        SET attendance = :attendance, updated_at = CURRENT_TIMESTAMP
                                        WHERE family_name = :name
                                    """), {"name": cleaned_name, "attendance": attendance})
                                    conn.commit()
                                    st.markdown(render_success(True), unsafe_allow_html=True)
                                else:
                                    # INSERTAR NUEVO
                                    conn.execute(text("""
                                        INSERT INTO rsvp_dafne (family_name, attendance)
                                        VALUES (:name, :attendance)
                                    """), {"name": cleaned_name, "attendance": attendance})
                                    conn.commit()
                                    st.markdown(render_success(False), unsafe_allow_html=True)
                                    if attendance == "SI":
                                        st.balloons()
                        except Exception as e:
                            st.error("No se pudo conectar a la base de datos en este momento. Inténtalo más tarde.")

    # --- FOOTER ---
    st.markdown("""
<div class="footer-custom">
Powered by Marian Losas &nbsp;·&nbsp;
<a href="https://wa.me/543624591406" target="_blank">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="#25D366" style="display:inline-block;vertical-align:middle;flex-shrink:0;"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
3624591406
</a>
</div>
""", unsafe_allow_html=True)
