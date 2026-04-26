import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="Cumple Dafne 🎂", layout="centered", initial_sidebar_state="collapsed")

# --- CONFIG & SECRETS ---
DATABASE_URL = "postgresql://neondb_owner:npg_gRuzeMfF4N1B@ep-super-frog-amxd955k-pooler.c-5.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "Dafne02"

# Fix Neon postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- DATABASE SETUP ---
Base = declarative_base()

class RSVPDafne(Base):
    __tablename__ = 'rsvp_dafne'
    id = Column(Integer, primary_key=True, autoincrement=True)
    family_name = Column(String, nullable=False)
    attendance = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

engine = create_engine(DATABASE_URL, pool_recycle=3600)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- CSS STYLING ---
def apply_styles():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #FFC107 0%, #FF5722 50%, #03A9F4 100%);
            background-attachment: fixed;
        }
        .block-container {
            background: rgba(255, 255, 255, 0.95);
            padding: 3rem 2rem !important;
            border-radius: 25px;
            box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 0.2);
            margin-top: 2rem;
            margin-bottom: 2rem;
        }
        h1, h2, h3, p, span, label, div {
            color: #2b2b2b;
            font-family: "Comic Sans MS", "Arial Rounded MT Bold", sans-serif;
        }
        .stButton>button {
            width: 100%;
            background-color: #FF5722;
            color: white !important;
            border-radius: 12px;
            border: none;
            padding: 0.8rem;
            font-weight: bold;
            font-size: 1.2rem;
            transition: all 0.3s;
        }
        .stButton>button:hover {
            background-color: #E64A19;
            transform: scale(1.02);
            color: white !important;
        }
        .stAlert > div {
            background-color: #FFF3CD;
            color: #856404;
            border: 1px solid #FFEEBA;
            border-radius: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

# --- ADMIN PANEL ---
def admin_panel():
    st.markdown("<h1>⚙️ Panel Admin - Dafne RSVP</h1>", unsafe_allow_html=True)
    
    admin_user = st.text_input("Usuario de Administrador")
    admin_pass = st.text_input("Contraseña de Administrador", type="password")
    
    if admin_user != ADMIN_USER or admin_pass != ADMIN_PASSWORD:
        if admin_user or admin_pass:
            st.error("Usuario o contraseña incorrectos")
        return
        
    st.success("Acceso concedido")
    
    db = SessionLocal()
    try:
        data = db.query(RSVPDafne).all()
        
        if not data:
            st.info("No hay respuestas todavía.")
            return
            
        df = pd.DataFrame([{
            "ID": item.id,
            "Familia": item.family_name,
            "Asiste": item.attendance,
            "Fecha/Hora": item.created_at.strftime("%Y-%m-%d %H:%M:%S")
        } for item in data])
        
        total_si = len(df[df["Asiste"] == "SI"])
        total_no = len(df[df["Asiste"] == "NO"])
        total_resp = len(df)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total SI", total_si)
        col2.metric("Total NO", total_no)
        col3.metric("Total Respuestas", total_resp)
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # CSV Download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Excel (CSV)",
            data=csv,
            file_name='rsvp_dafne.csv',
            mime='text/csv',
        )
        
        st.divider()
        st.subheader("🗑 Eliminar registro")
        delete_id = st.number_input("ID numérico a eliminar", min_value=0, step=1)
        if st.button("Eliminar ahora"):
            record = db.query(RSVPDafne).filter(RSVPDafne.id == delete_id).first()
            if record:
                db.delete(record)
                db.commit()
                st.success(f"Registro {delete_id} eliminado exitosamente. Recarga la página.")
            else:
                st.error("ID no encontrado.")
                
    except Exception as e:
        st.error(f"Error de base de datos: {e}")
    finally:
        db.close()

# --- PUBLIC PAGE ---
def public_page():
    apply_styles()
    
    st.markdown("<h1 style='text-align: center;'>🎉 DAFNE cumple 2 años 🎈</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>📍 Salón HAKUNA MATATA</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem;'>Av. Marconi 49</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem;'>🗓 6 de junio | ⏰ 10 a 13 hs</p>", unsafe_allow_html=True)
    st.warning("⚠️ CONFIRMAR ASISTENCIA hasta el 30 de mayo")
    
    st.divider()
    
    with st.form("rsvp_form", clear_on_submit=True):
        family_name = st.text_input("Nombre de familia", placeholder="Ej: Familia García Perez")
        attendance = st.radio("¿Asisten?", ["SI", "NO"], horizontal=True)
        
        submitted = st.form_submit_button("Enviar confirmación")
        
        if submitted:
            if not family_name.strip():
                st.error("❌ Por favor, ingresa el nombre de tu familia.")
            else:
                db = SessionLocal()
                try:
                    new_rsvp = RSVPDafne(
                        family_name=family_name.strip(),
                        attendance=attendance
                    )
                    db.add(new_rsvp)
                    db.commit()
                    st.success(f"¡Gracias {family_name.strip()}! Tu respuesta ({attendance}) fue guardada.")
                    if attendance == "SI":
                        st.balloons()
                except Exception as e:
                    st.error(f"❌ Error al guardar en base de datos: {e}")
                finally:
                    db.close()

# --- APP ROUTER ---
def main():
    # Nueva forma de leer query params en Streamlit >= 1.30:
    if "admin" in st.query_params and st.query_params["admin"] == "1":
        admin_panel()
    else:
        public_page()

if __name__ == "__main__":
    main()