import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import base64
import os
import hmac
import time
from urllib.parse import quote
import datetime

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
                    linear-gradient(var(--bg-overlay), var(--bg-overlay)),
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
        st.warning(f"No se encontró la imagen de fondo '{image_file}'.")

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
def get_secret(key, default_value=""):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass 
    val_env = os.getenv(key)
    if val_env:
        return val_env
    return default_value

DATABASE_URL_CONFIG = get_secret("DATABASE_URL", "")
ADMIN_PASSWORD_CONFIG = get_secret("ADMIN_PASSWORD", "")

if "temp_admin_password" not in st.session_state:
    st.session_state["temp_admin_password"] = ADMIN_PASSWORD_CONFIG

# --- CONEXIÓN DB ---
@st.cache_resource
def init_connection(url):
    if not url:
        return None
    try:
        return create_engine(url)
    except Exception as e:
        return None

engine = init_connection(DATABASE_URL_CONFIG)

def update_db_schema():
    if engine is None:
        return
    try:
        with engine.connect() as conn:
            # Tabla principal
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rsvp_dafne (
                    id SERIAL PRIMARY KEY,
                    family_name TEXT UNIQUE NOT NULL,
                    attendance TEXT NOT NULL CHECK (attendance IN ('SI', 'NO')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            # Agregar columnas si no existen
            conn.execute(text("ALTER TABLE rsvp_dafne ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("ALTER TABLE rsvp_dafne ADD COLUMN IF NOT EXISTS message TEXT;"))
            
            # Tabla de visitas
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS visits (
                    id INT PRIMARY KEY,
                    count INT DEFAULT 0
                )
            """))
            conn.execute(text("INSERT INTO visits (id, count) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;"))
            conn.commit()
    except Exception as e:
        pass

if not DATABASE_URL_CONFIG:
    st.error("❌ Ocurrió un error de conexión. Faltan las credenciales de la base de datos.")
else:
    update_db_schema()

# Incrementar contador de visitas
@st.cache_resource
def increment_visit():
    if engine is not None:
        try:
            with engine.connect() as conn:
                conn.execute(text("UPDATE visits SET count = count + 1 WHERE id = 1"))
                conn.commit()
        except:
            pass
    return True

increment_visit()

# --- LÓGICA APP ---
is_admin = st.query_params.get("admin") == "1"

if is_admin:
    st.title("🛠️ Panel Admin - Cumple Dafne")
    
    admin_pass = st.session_state["temp_admin_password"]

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
            
        with st.expander("🔑 Cambiar contraseña temporal (Solo esta sesión)"):
            new_pass = st.text_input("Nueva contraseña", type="password")
            if st.button("Actualizar contraseña"):
                if new_pass:
                    st.session_state["temp_admin_password"] = new_pass
                    st.success("Contraseña actualizada para esta sesión.")
                else:
                    st.error("La contraseña no puede estar vacía.")
        
        st.write("---")
        
        if engine is None:
            st.warning("⚠️ El panel está inactivo porque no hay conexión a la base de datos.")
            st.stop()
            
        try:
            with engine.connect() as conn:
                df = pd.read_sql("SELECT * FROM rsvp_dafne ORDER BY updated_at DESC", conn)
                visits_res = conn.execute(text("SELECT count FROM visits WHERE id = 1")).fetchone()
                total_visits = visits_res[0] if visits_res else 0
            
            total_resp = len(df)
            total_si = len(df[df['attendance'] == 'SI'])
            total_no = len(df[df['attendance'] == 'NO'])
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Visitas Totales", total_visits)
            col2.metric("Total Respuestas", total_resp)
            col3.metric("Total SI", total_si)
            col4.metric("Total NO", total_no)
            
            st.write("---")
            
            # Gráfico de líneas (últimos 14 días)
            st.subheader("📈 Actividad de respuestas")
            if not df.empty:
                df['date'] = pd.to_datetime(df['updated_at']).dt.date
                daily_counts = df.groupby('date').size().reset_index(name='count')
                st.line_chart(daily_counts.set_index('date'))
            
            # Filtros
            st.subheader("📋 Lista de invitados")
            filtro = st.radio("Filtrar por:", ["Todos", "Solo SI", "Solo NO"], horizontal=True)
            
            df_filtered = df
            if filtro == "Solo SI":
                df_filtered = df[df['attendance'] == 'SI']
            elif filtro == "Solo NO":
                df_filtered = df[df['attendance'] == 'NO']
                
            st.dataframe(df_filtered[['id', 'family_name', 'attendance', 'updated_at', 'message']], use_container_width=True)
            
            # Mensajes expandibles
            with st.expander("💌 Ver mensajes para Dafne"):
                df_msg = df[df['message'].notna() & (df['message'] != '')]
                if df_msg.empty:
                    st.write("Aún no hay mensajes.")
                else:
                    for _, row in df_msg.iterrows():
                        st.info(f"**{row['family_name']}**: {row['message']}")
            
            # WhatsApp Recordatorio Generico
            st.write("---")
            st.subheader("📱 WhatsApp - Enviar Recordatorio")
            st.write("Copiá este enlace y envialo a quienes aún no han respondido.")
            wsp_link = "https://wa.me/?text=" + quote("¡Hola! Te recuerdo que el 6 de junio festejamos los 2 añitos de Dafne. Por favor confirmame tu asistencia en este link: https://cumple-dafne-2.streamlit.app")
            st.markdown(f'<a href="{wsp_link}" target="_blank" style="background-color:#25D366; color:white; padding:10px 15px; border-radius:10px; text-decoration:none; font-weight:bold;">Generar Mensaje Genérico</a>', unsafe_allow_html=True)
            
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

    def generate_ics() -> bytes:
        today = datetime.date.today()
        event_date = datetime.date(2026, 6, 6)
        if today > event_date:
            event_date = datetime.date(2027, 6, 6)
        year = event_date.year
        now_utc = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CumpleDafne//ES
BEGIN:VEVENT
UID:cumple-dafne-{year}@invitacion
DTSTAMP:{now_utc}
DTSTART;TZID=America/Argentina/Buenos_Aires:{year}0606T100000
DTEND;TZID=America/Argentina/Buenos_Aires:{year}0606T130000
SUMMARY:Cumpleaños de Dafne (2 años)
LOCATION:Salón Hakuna Matata, Av. Marconi 49, Resistencia
DESCRIPTION:Te esperamos para festejar los 2 años de Dafne
END:VEVENT
END:VCALENDAR""".encode("utf-8")

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
        return f"""
<div style="text-align: center;">
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
function updateCountdown() {{
    const targetDate = new Date("2026-06-06T10:00:00-03:00").getTime();
    const now = new Date().getTime();
    const distance = targetDate - now;

    const container = document.getElementById('countdown-container');
    if(!container) return;

    if (distance < 0) {{
        container.innerHTML = '<div class="cd-finished">🎉</div>';
        return;
    }}

    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);

    container.innerHTML = `
        <div class="countdown-wrapper">
            <div class="cd-box"><span class="cd-num">${{days}}</span><span class="cd-lbl">D</span></div>
            <div class="cd-box"><span class="cd-num">${{hours.toString().padStart(2, '0')}}</span><span class="cd-lbl">H</span></div>
            <div class="cd-box"><span class="cd-num">${{minutes.toString().padStart(2, '0')}}</span><span class="cd-lbl">M</span></div>
            <div class="cd-box"><span class="cd-num">${{seconds.toString().padStart(2, '0')}}</span><span class="cd-lbl">S</span></div>
        </div>
    `;
}}
setInterval(updateCountdown, 1000);
updateCountdown();
</script>

</div>
"""
    st.markdown(render_hero(), unsafe_allow_html=True)

    with st.form("rsvp_form"):
        family_name = st.text_input("Nombre de familia (Ej: Familia García)")
        opciones_radio = ["Sí, vamos a ir", "No vamos a poder ir"]
        seleccion = st.radio(
            "¿Asisten?",
            opciones_radio,
            index=0,
            label_visibility="visible",
            key="rsvp_attendance",
        )
        
        user_message = st.text_area("💬 Mensaje para Dafne (opcional)", max_chars=140)
        
        submitted = st.form_submit_button("Enviar confirmación ⭐")

        if submitted:
            attendance = "SI" if seleccion == opciones_radio[0] else "NO"
            cleaned_name = family_name.strip()
            cleaned_msg = user_message.strip()
            
            if not cleaned_name:
                st.warning("⚠️ El nombre de familia no puede estar vacío.")
            else:
                if engine is None:
                    st.error("🫣 ¡Ups! Algo salió mal. Por favor, intentalo de nuevo o escribinos al WhatsApp del contacto.")
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
                                    sub_msg = "¡Te esperamos el 6 de junio!" if attendance == "SI" else "¡Qué pena! Te extrañaremos."
                                    return f"""
                                    <div class="success-card">
                                        <div class="success-icon">
                                            <svg viewBox="0 0 24 24">
                                                <path class="path" d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                                                <polyline class="path" points="22 4 12 14.01 9 11.01"></polyline>
                                            </svg>
                                        </div>
                                        <div class="success-title">{msg}</div>
                                        <div class="success-text">{sub_msg}</div>
                                    </div>
                                    """
                                
                                if result:
                                    # UPSERT (Actualizar)
                                    conn.execute(text("""
                                        UPDATE rsvp_dafne 
                                        SET attendance = :attendance, message = :message, updated_at = CURRENT_TIMESTAMP
                                        WHERE family_name = :name
                                    """), {"name": cleaned_name, "attendance": attendance, "message": cleaned_msg})
                                    conn.commit()
                                    st.markdown(render_success(True), unsafe_allow_html=True)
                                else:
                                    # INSERTAR NUEVO
                                    conn.execute(text("""
                                        INSERT INTO rsvp_dafne (family_name, attendance, message)
                                        VALUES (:name, :attendance, :message)
                                    """), {"name": cleaned_name, "attendance": attendance, "message": cleaned_msg})
                                    conn.commit()
                                    st.markdown(render_success(False), unsafe_allow_html=True)
                                    if attendance == "SI":
                                        st.balloons()
                        except Exception as e:
                            st.error("🫣 ¡Ups! Algo salió mal. Por favor, intentalo de nuevo o escribinos al WhatsApp del contacto.")

    DESTINO = "Av. Marconi 49, Resistencia, Chaco, Argentina"
    maps_url = f"https://www.google.com/maps/dir/?api=1&destination={quote(DESTINO)}"
    ics_b64 = base64.b64encode(generate_ics()).decode("ascii")
    ics_data_uri = f"data:text/calendar;base64,{ics_b64}"

    st.markdown(f"""
<div class="secondary-actions">
    <a href="{maps_url}" target="_blank" rel="noopener noreferrer" class="ghost-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 21s-7-7-7-12a7 7 0 1114 0c0 5-7 12-7 12z"/>
            <circle cx="12" cy="9" r="2.5"/>
        </svg>
        Cómo llegar
    </a>
    <a href="{ics_data_uri}" download="dafne-cumple.ics" class="ghost-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
        Agregar al calendario
    </a>
</div>
""", unsafe_allow_html=True)

    # --- FOOTER ---
    st.markdown(f"""
<div class="footer-custom">
Powered by Marian Losas &nbsp;·&nbsp;
<a href="https://wa.me/543624591406" target="_blank">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="#25D366" style="display:inline-block;vertical-align:middle;flex-shrink:0;"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
426: 3624591406
</a>
</div>
""", unsafe_allow_html=True)
