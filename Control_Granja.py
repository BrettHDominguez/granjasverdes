import streamlit as st
import qrcode
from PIL import Image
import io
from datetime import datetime, date, timedelta
import pandas as pd
from sqlalchemy import create_engine, Column, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from pyzbar.pyzbar import decode as qr_decode
import matplotlib.pyplot as plt

# ---------- CONFIGURACIÓN INICIAL ----------
st.set_page_config(
    page_title="Control de Granjas VERDES",
    page_icon="🐷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- BASE DE DATOS ----------
DB_PATH = "sqlite:///granja_premium.db"
engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Animal(Base):
    __tablename__ = 'animales'
    id = Column(String, primary_key=True)
    tipo = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    fecha_nacimiento = Column(DateTime, nullable=False)
    peso_inicial = Column(Float, nullable=False)
    padre = Column(String, nullable=True)
    madre = Column(String, nullable=True)
    origen = Column(String, nullable=False)
    plan_alimentacion = Column(String, nullable=False)
    estado_actual = Column(String, nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    pesos = relationship('Peso', back_populates='animal', cascade='all, delete-orphan')
    tratamientos = relationship('Tratamiento', back_populates='animal', cascade='all, delete-orphan')

class Peso(Base):
    __tablename__ = 'pesos'
    id = Column(String, ForeignKey('animales.id'), primary_key=True)
    fecha = Column(DateTime, primary_key=True)
    peso = Column(Float, nullable=False)
    animal = relationship('Animal', back_populates='pesos')

class Tratamiento(Base):
    __tablename__ = 'tratamientos'
    id = Column(String, primary_key=True)
    animal_id = Column(String, ForeignKey('animales.id'))
    tipo = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    fecha_aplicacion = Column(DateTime, nullable=False)
    fecha_proxima = Column(DateTime)
    dosis = Column(String)
    observaciones = Column(String)
    animal = relationship('Animal', back_populates='tratamientos')

Base.metadata.create_all(bind=engine)

# ---------- UTILIDADES ----------
@st.cache_resource
def get_session():
    return SessionLocal()


def calcular_plan(tipo, dias, peso=None):
    planes = {
        "Cerdo": {
            (0, 42): "Preiniciación: 200–300g, 20–22% proteína. Vit A/D/E, desparasitación inicial",
            (43, 84): "Iniciación: 500–800g, 18–20% proteína. Refuerzo vitamínico 30d",
            (85, 140): "Crecimiento: 1–2kg, 16–18% proteína. Desparasitación 90d",
            (141, float('inf')): "Engorde: 2.5–3.5kg, 14–16% proteína. Suplementos minerales"
        },
        "Pollo": {
            (0, 7): "Preiniciación: 15–20g. Complejo B, control temp",
            (8, 21): "Iniciación: 50–100g. Vacunación básica",
            (22, 35): "Crecimiento: 120–150g. Revisión plumaje",
            (36, float('inf')): "Engorde: 160–180g. Suplementos digestivos"
        },
        "Borrego": {
            (0, 14): "Lactancia: leche materna. Vit D3",
            (15, 28): "Preiniciación: 20–22% proteína, 2L agua. Desparasitación ligera",
            (29, 56): "Iniciación: 18–20% proteína. Refuerzo vitamínico",
            (57, 112): "Crecimiento: 16–18% proteína. Desparasitación 90d",
            (113, float('inf')): "Engorde: 14–16% proteína. Control corporal"
        }
    }
    for (min_d, max_d), plan in planes[tipo].items():
        if min_d <= dias <= max_d:
            return plan
    return "Plan no disponible"


def generar_qr(info: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=1, box_size=6, border=4)
    qr.add_data(info)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

# ---------- PÁGINAS ----------

def pagina_inicio():
    st.title("🏠 Panel de Control - Granja Premium")
    session = get_session()
    total_animales = session.query(Animal).count()
    ultimo_registro = session.query(Animal).order_by(Animal.fecha_registro.desc()).first()
    pesos = session.query(Peso).all()
    peso_promedio = sum(p.peso for p in pesos) / len(pesos) if pesos else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Animales", total_animales)
    col2.metric("Último Registro", ultimo_registro.id if ultimo_registro else 'N/A')
    col3.metric("Peso Promedio", f"{peso_promedio:.1f} kg")
    st.divider()
    st.subheader("Resumen por Tipo")
    tipos = session.query(Animal.tipo, func.count(Animal.id)).group_by(Animal.tipo).all()
    df_tipos = pd.DataFrame(tipos, columns=["Tipo", "Cantidad"])
    c1, c2 = st.columns([1, 2])
    c1.dataframe(df_tipos, height=200)
    fig, ax = plt.subplots()
    ax.bar(df_tipos["Tipo"], df_tipos["Cantidad"])
    c2.pyplot(fig)


def registro_animales():
    st.title("📝 Registro de Nuevo Animal")
    with st.expander("Instrucciones para el registro", expanded=True):
        st.write(
            "- **ID Único** debe comenzar con C, P o B segun el tipo. "
            "Ej: C25H, P10M, B05F."
        )
    with st.form("form_registro", clear_on_submit=True):
        tipo = st.selectbox("Tipo de Animal", ["Cerdo", "Pollo", "Borrego"])
        prefix = {'Cerdo':'C','Pollo':'P','Borrego':'B'}[tipo]
        id_animal = st.text_input(f"ID Único (Debe iniciar con {prefix})")
        nombre = st.text_input("Nombre del Animal")
        fecha_nac = st.date_input("Fecha de Nacimiento")
        peso_ini = st.number_input("Peso Inicial (kg)", min_value=0.0)
        padre = st.text_input("ID Padre (opcional)")
        madre = st.text_input("ID Madre (opcional)")
        origen = st.radio("Origen", ["Criado en Granja","Comprado"])
        estado = st.selectbox("Estado Actual", ["Vivo","Vendido","Sacrificado"])
        if st.form_submit_button("Registrar Animal"):
            session = get_session()
            if not id_animal.startswith(prefix):
                st.error(f"ID inválido. Debe iniciar con {prefix}.")
                return
            if session.query(Animal).filter_by(id=id_animal).first():
                st.warning("ID ya existe.")
                return
            dias = (date.today()-fecha_nac).days
            plan = calcular_plan(tipo,dias,peso_ini)
            nuevo = Animal(id=id_animal,tipo=tipo,nombre=nombre,fecha_nacimiento=fecha_nac,
                           peso_inicial=peso_ini,padre=padre or None,madre=madre or None,
                           origen=origen,plan_alimentacion=plan,estado_actual=estado)
            session.add(nuevo)
            session.commit()
            st.success("Registro exitoso.")
            info=f"ID:{id_animal}|Tipo:{tipo}|Nombre:{nombre}|Nacimiento:{fecha_nac}"
            buf=generar_qr(info)
            col1,col2=st.columns([1,2])
            col1.image(Image.open(buf),caption="QR")
            col2.download_button("Descargar QR",buf,file_name=f"qr_{id_animal}.png",mime="image/png")


def registrar_peso():
    st.title("⚖️ Registro de Pesos")
    session=get_session()
    animales=session.query(Animal).all()
    if not animales:
        st.warning("No hay animales.")
        return
    with st.form("form_peso"):
        metodo=st.radio("Identificación",["QR","Manual"],horizontal=True)
        id_sel=None
        if metodo=="QR":
            qr_file=st.camera_input("Escanea QR")
            if qr_file:
                img=Image.open(qr_file)
                try:
                    decoded=qr_decode(img)
                    id_sel=decoded[0].data.decode().split("|")[0].replace("ID:","")
                    st.success(f"ID: {id_sel}")
                except:
                    st.error("QR no válido.")
        if not id_sel:
            id_sel=st.selectbox("Selecciona Animal",[a.id for a in animales])
        peso=st.number_input("Peso (kg)",min_value=0.0)
        fecha_med=st.date_input("Fecha",value=date.today())
        if st.form_submit_button("Guardar")):
            now=datetime.combine(fecha_med,datetime.now().time())
            rec=Peso(id=id_sel,fecha=now,peso=peso)
            session.add(rec)
            session.commit()
            st.success("Peso guardado.")


def analisis_peso():
    st.title("📊 Análisis de Pesos")
    session=get_session()
    ids=[a.id for a in session.query(Animal).all()]
    if not ids:
        st.warning("Sin datos.")
        return
    sel=st.selectbox("Animal",ids)
    regs=session.query(Peso).filter(Peso.id==sel).order_by(Peso.fecha).all()
    if not regs:
        st.info("Sin registros.")
        return
    df=pd.DataFrame([(r.fecha.date(),r.peso) for r in regs],columns=["Fecha","Peso"]).set_index("Fecha")
    st.line_chart(df)
    st.dataframe(df)


def alimentacion():
    st.title("🍽️ Plan de Alimentación")
    session=get_session()
    animales=session.query(Animal).all()
    if not animales:
        st.warning("No hay animales.")
        return
    sel=st.selectbox("Animal",[a.id for a in animales])
    dia=st.date_input("Fecha",value=date.today())
    if st.button("Calcular")):
        a=session.query(Animal).filter_by(id=sel).first()
        dias=(dia-a.fecha_nacimiento.date()).days
        plan=calcular_plan(a.tipo,dias,a.peso_inicial)
        st.markdown(f"**{plan}**")


def main():
    st.sidebar.title("Menú")
    opt=st.sidebar.radio("",["Inicio","Registro","Pesos","Análisis","Alimentación","Tratamientos","Alertas"])
    if opt=="Inicio":pagina_inicio()
    if opt=="Registro":registro_animales()
    if opt=="Pesos":registrar_peso()
    if opt=="Análisis":analisis_peso()
    if opt=="Alimentación":alimentacion()
    # Tratamientos y alertas se mantienen igual del código original

if __name__=="__main__":
    main()
