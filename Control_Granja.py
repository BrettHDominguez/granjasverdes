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

# ---------- PAGINAS ----------
def pagina_inicio():
    st.title("🏠 Panel de Control - Granja Premium")
    session = get_session()
    total = session.query(Animal).count()
    ultimo = session.query(Animal).order_by(Animal.fecha_registro.desc()).first()
    pesos = session.query(Peso).all()
    promedio = sum(p.peso for p in pesos) / len(pesos) if pesos else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Animales", total)
    c2.metric("Último Registro", ultimo.id if ultimo else 'N/A')
    c3.metric("Peso Promedio", f"{promedio:.1f} kg")
    st.divider()
    st.subheader("Resumen por Tipo")
    tipos = session.query(Animal.tipo, func.count(Animal.id)).group_by(Animal.tipo).all()
    df = pd.DataFrame(tipos, columns=["Tipo", "Cantidad"])
    col1, col2 = st.columns([1,2])
    col1.dataframe(df, height=200)
    fig, ax = plt.subplots()
    ax.bar(df['Tipo'], df['Cantidad'])
    col2.pyplot(fig)


def registro_animales():
    st.title("📝 Registro de Nuevo Animal")
    with st.expander("Instrucciones de Registro", expanded=True):
        st.write("ID único debe iniciar con C/P/B según Cerdo/Pollo/Borrego")
    with st.form("registro"): 
        tipo = st.selectbox("Tipo", ["Cerdo","Pollo","Borrego"])
        prefix = {'Cerdo':'C','Pollo':'P','Borrego':'B'}[tipo]
        id_a = st.text_input("ID (" + prefix + "...)")
        nombre = st.text_input("Nombre")
        fn = st.date_input("Fecha Nac.")
        peso_i = st.number_input("Peso Inicial (kg)", min_value=0.0)
        padre = st.text_input("Padre (ID)")
        madre = st.text_input("Madre (ID)")
        origen = st.radio("Origen", ["Criado","Comprado"])
        estado = st.selectbox("Estado", ["Vivo","Vendido","Sacrificado"])
        enviar = st.form_submit_button("Registrar")
    if enviar:
        if not id_a.startswith(prefix): st.error("ID inválido"); return
        sess = get_session()
        if sess.query(Animal).get(id_a): st.warning("ID existe"); return
        dias = (date.today()-fn).days
        plan = calcular_plan(tipo, dias, peso_i)
        ani = Animal(id=id_a,tipo=tipo,nombre=nombre,fecha_nacimiento=fn,
                     peso_inicial=peso_i,padre=padre or None,madre=madre or None,
                     origen=origen,plan_alimentacion=plan,estado_actual=estado)
        sess.add(ani); sess.commit()
        st.success("Animal registrado")
        info = f"ID:{id_a}|Tipo:{tipo}|Nom:{nombre}|Nac:{fn}"
        buf = generar_qr(info)
        c1,c2 = st.columns([1,2]); c1.image(Image.open(buf)); c2.download_button("Descargar QR",buf,file_name=f"qr_{id_a}.png")


def registrar_peso():
    st.title("⚖️ Registrar Peso")
    sess = get_session(); ants = sess.query(Animal).all()
    if not ants: st.warning("No animales"); return
    with st.form("peso"): 
        metodo = st.radio("Método",["QR","Manual"],horizontal=True)
        sel = None
        if metodo=="QR":
            f = st.camera_input("Escanear QR")
            if f:
                try: sel = qr_decode(Image.open(f))[0].data.decode().split("|")[0].replace("ID:","")
                except: st.error("QR err"); return
        if not sel: sel = st.selectbox("Animal",[a.id for a in ants])
        kg = st.number_input("Peso (kg)",min_value=0.0)
        dt = st.date_input("Fecha",value=date.today())
        go = st.form_submit_button("Guardar")
    if go:
        now = datetime.combine(dt,datetime.now().time())
        rec = Peso(id=sel,fecha=now,peso=kg)
        sess.add(rec); sess.commit(); st.success("Peso guardado")
        hist = sess.query(Peso).filter(Peso.id==sel).order_by(Peso.fecha.desc()).limit(5).all()
        dfh = pd.DataFrame([(h.fecha.date(),h.peso) for h in hist],columns=["Fecha","Peso"]).set_index("Fecha")
        st.line_chart(dfh)


def analisis_peso():
    st.title("📊 Análisis Pesos")
    sess=get_session(); ids=[a.id for a in sess.query(Animal).all()]
    if not ids: st.warning("No datos"); return
    sel = st.selectbox("Animal",ids)
    regs = sess.query(Peso).filter(Peso.id==sel).order_by(Peso.fecha).all()
    if not regs: st.info("Sin registros"); return
    df = pd.DataFrame([(r.fecha.date(),r.peso) for r in regs],columns=["Fecha","Peso"]).set_index("Fecha")
    st.line_chart(df); st.dataframe(df)


def alimentacion():
    st.title("🍽️ Plan Alimentación")
    sess=get_session(); ants=sess.query(Animal).all()
    if not ants: st.warning("No animales"); return
    sel=st.selectbox("Animal",[a.id for a in ants])
    dia=st.date_input("Fecha",value=date.today())
    if st.button("Calcular Plan"):
        a=sess.query(Animal).get(sel)
        dias=(dia-a.fecha_nacimiento.date()).days
        st.markdown(f"**{calcular_plan(a.tipo,dias,a.peso_inicial)}**")


def registro_tratamiento():
    st.title("💉 Registro Tratamiento")
    sess=get_session(); ants=sess.query(Animal).filter(Animal.estado_actual=="Vivo").all()
    with st.form("trat"): 
        sel=st.selectbox("Animal",[a.id for a in ants])
        ttipo=st.selectbox("Tipo",["Vacuna","Vitamina"])
        nom=st.text_input("Nombre")
        fa=st.date_input("Fecha"); freq=st.number_input("Frecuencia días",min_value=0)
        dos=st.text_input("Dosis"); obs=st.text_area("Observaciones")
        go=st.form_submit_button("Registrar")
    if go:
        nt=Tratamiento(id=f"T{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        animal_id=sel,tipo=ttipo,nombre=nom,
                        fecha_aplicacion=fa,
                        fecha_proxima=(fa+timedelta(days=freq)) if freq>0 else None,
                        dosis=dos,observaciones=obs)
        sess.add(nt); sess.commit(); st.success("Tratamiento registrado")


def historial_tratamientos():
    st.title("📋 Historial Tratamientos")
    sess=get_session(); trs=sess.query(Tratamiento).all()
    if not trs: st.info("No tratamientos"); return
    df=pd.DataFrame([(t.animal_id,t.tipo,t.nombre,t.fecha_aplicacion.date(),t.fecha_proxima.date() if t.fecha_proxima else None,t.dosis,t.observaciones)
                     for t in trs],columns=["Animal","Tipo","Nombre","Fecha","Próxima","Dosis","Obs"])
    st.dataframe(df)


def alertas_salud():
    st.title("⚠️ Alertas Salud")
    sess=get_session(); vivos=sess.query(Animal).filter(Animal.estado_actual=="Vivo").all(); hoy=date.today()
    dp=[(a.id,a.tipo,a.nombre) for a in vivos if (hoy-a.fecha_nacimiento.date()).days%90<7 and (hoy-a.fecha_nacimiento.date()).days>=14]
    st.subheader("Desparasitación"); st.dataframe(pd.DataFrame(dp,columns=["ID","Tipo","Nombre"])) if dp else st.success("Nada")
    sp=[(a.id,a.tipo,a.nombre) for a in vivos if (hoy-a.fecha_nacimiento.date()).days%30<7]
    st.subheader("Suplementos"); st.dataframe(pd.DataFrame(sp,columns=["ID","Tipo","Nombre"])) if sp else st.success("Nada")


def alertas_tratamientos():
    st.title("🔔 Alertas Tratamientos")
    sess=get_session(); trs=sess.query(Tratamiento).filter(Tratamiento.fecha_proxima!=None).all(); hoy=date.today()
    at=[t for t in trs if 0<=(t.fecha_proxima.date()-hoy).days<=7]
    if at:
        for t in at:
            with st.expander(f"{t.nombre} - {t.animal_id}"):
                st.write(f"Próxima: {t.fecha_proxima.date()} (faltan {(t.fecha_proxima.date()-hoy).days} días)")
                st.write(f"Dosis: {t.dosis}")
                st.write(f"Obs: {t.observaciones}")
    else:
        st.success("No próximos tratamientos")


def main():
    menu=["Inicio","Registro","Pesos","Análisis","Alimentación","Tratamiento","Historial Tratamientos","Alertas Salud","Alertas Tratamientos"]
    opt=st.sidebar.radio("Menú",menu)
    {"Inicio":pagina_inicio,
     "Registro":registro_animales,
     "Pesos":registrar_peso,
     "Análisis":analisis_peso,
     "Alimentación":alimentacion,
     "Tratamiento":registro_tratamiento,
     "Historial Tratamientos":historial_tratamientos,
     "Alertas Salud":alertas_salud,
     "Alertas Tratamientos":alertas_tratamientos}[opt]()

if __name__=="__main__":
    main()
