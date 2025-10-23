import json
from pathlib import Path
import streamlit as st
from grafo_json import Grafo

BASE_DIR = Path(__file__).parent          # carpeta donde está app.py
PLANES_DIR = BASE_DIR / "planes"          # carpeta "planes" dentro del proyecto
PLANES_DIR.mkdir(exist_ok=True)           # la crea si no existe

st.set_page_config(
    page_title="Grafos • Planes de Estudio ITAM",
    page_icon="📚",
    layout="wide"
)
if st.button("Reiniciar sesión (borrar progreso temporal)"):
    for m in st.session_state.grafo.materias.values():
        m.estado = 0
    st.rerun()

@st.cache_data(show_spinner=False)
def listar_planes(dir_path: Path):
    planes = sorted(dir_path.glob("*.json"))
    return [(p.stem, p) for p in planes]

@st.cache_data(show_spinner=True)
def cargar_grafo_desde_json(path: Path) -> Grafo:
    g = Grafo(nombre_plan=path.stem)
    g.from_json_file(path)
    return g

@st.cache_data(show_spinner=False)
def leer_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


st.title("Planes de estudio")

# 1) Dropdown + uploader (igual que antes)
planes_disponibles = listar_planes(PLANES_DIR)
nombres = ["(elige un plan)"] + [n for n, _ in planes_disponibles]
eleccion = st.selectbox("Selecciona un plan:", nombres, index=0)

archivo_subido = st.file_uploader("…o sube tu JSON", type=["json"])

# 2) Determinar la fuente actual (para resetear el estado si cambia)
fuente_actual = None
json_data = None

if archivo_subido is not None:
    try:
        json_data = json.load(archivo_subido)
        fuente_actual = "upload"
    except Exception as e:
        st.error(f"Error leyendo JSON subido: {e}")
elif eleccion != "(elige un plan)":
    nombre, ruta = next((n, p) for n, p in planes_disponibles if n == eleccion)
    json_data = leer_json(ruta)
    fuente_actual = f"dropdown:{nombre}"

# 3) Inicializar/reciclar el grafo en session_state
if "grafo" not in st.session_state:
    st.session_state.grafo = None
if "fuente" not in st.session_state:
    st.session_state.fuente = None

# Si cambió la fuente (nuevo plan o nuevo upload), reconstruye el grafo una sola vez
if fuente_actual is not None and fuente_actual != st.session_state.fuente:
    g = Grafo(nombre_plan=(fuente_actual.split(":", 1)[-1] if ":" in fuente_actual else "subido"))
    g.from_json_dict(json_data)
    st.session_state.grafo = g
    st.session_state.fuente = fuente_actual

g = st.session_state.grafo

if g is not None:
    st.success(f"Plan cargado ({st.session_state.fuente}). Materias: {len(g)}")

    st.subheader("Materias disponibles (con correquisitos en paquete)")
    grupos = g.grupos_coreq_disponibles()

    def _sem_or_inf(m):
        return m.semestre if isinstance(m.semestre, int) else 999

    grupos = sorted(grupos, key=lambda grp: min(_sem_or_inf(m) for m in grp))

    if not grupos:
        st.write("No hay materias disponibles por ahora.")
    else:
        for grp in grupos:
            # 3) Ordenar materias dentro del grupo por semestre y luego por clave
            materias = sorted(grp, key=lambda m: (_sem_or_inf(m), m.clave))

            # 4) Etiquetas: “CLAVE — Nombre (Sx)” mostrando semestre
            etiquetas = [
                f"{m.clave} — {m.nombre} (S{m.semestre})" if m.semestre is not None else f"{m.clave} — {m.nombre}"
                for m in materias
            ]
            st.markdown(" • " + "  |  ".join(etiquetas))

            # 5) Botones (igual que antes)
            paquete_id = "_".join([m.clave for m in materias])
            c1, c2 = st.columns(2)

            esta_cursando = any(m.estado == 1 for m in materias)

            # Mostrar botones con highlight visual
            if esta_cursando:
                c1.markdown("<span style='color:orange; font-weight:bold;'>🟠 Cursando</span>", unsafe_allow_html=True)

            if c1.button("Cursando", key=f"start_{paquete_id}"):
                for m in materias:
                    g.iniciar_materia(m.clave)
                st.rerun()

            if c2.button("Completada", key=f"comp_{paquete_id}"):
                for m in materias:
                    g.completar_materia(m.clave)
                st.rerun()

    st.divider()

    st.subheader("Materias por semestre")
    por_sem = {}
    for m in g.materias.values():
        por_sem.setdefault(m.semestre, []).append(m)

    for s in sorted(por_sem):
        st.write(f"**Semestre {s}**: " + ", ".join(sorted(f"{m.clave}" for m in por_sem[s])))

    # Botón para descargar el JSON ACTUALIZADO (con estados)
    st.subheader("Descargar tu progreso")
    data_json = json.dumps(g.to_json_dict(), ensure_ascii=False, indent=2)
    st.download_button(
        label="Descargar JSON actualizado",
        data=data_json.encode("utf-8"),
        file_name=f"{g.nombre_plan}_actualizado.json",
        mime="application/json"
    )
else:
    st.info("Elige un plan del menú o sube un JSON para cargarlo.")

