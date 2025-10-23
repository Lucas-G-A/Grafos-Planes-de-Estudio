# 🎓 Grafos de Planes de Estudio ITAM

Aplicación web desarrollada en **Streamlit** que permite visualizar los **planes de estudio del ITAM** como grafos interactivos, mostrando las relaciones de **prerrequisitos y correquisitos** entre materias.

🔗 **Demo en línea:** [grafos-planes-de-estudio-itam.streamlit.app](https://grafos-planes-de-estudio-itam.streamlit.app)

---

## 🚀 Lo que hemos hecho
- Construcción completa del **plan de Ciencia de Datos (CDA_B)** en formato JSON, incluyendo prerrequisitos, correquisitos, créditos, estado y semestre.  
- Desarrollo de la **interfaz Streamlit** que permite:
  - Seleccionar un plan desde un menú desplegable.
  - Marcar materias como **“cursando”** o **“completadas”**.
  - Actualizar automáticamente las materias disponibles para inscripción.
  - Mostrar todas las materias **ordenadas por semestre**.
  - Descargar el **JSON actualizado** con el progreso del usuario.  
- **Hosting gratuito** en Streamlit Cloud con sesiones independientes por usuario.

---

## 🧩 Lo que falta
- **Convertir todos los planes de estudio (PDF) a JSON**, manteniendo el formato del plan CDA_B:
  ```json
  "COM-11101": {
    "nombre": "Algoritmos y Programas",
    "creditos": 9,
    "prerreqs": [],
    "coreqs": [],
    "estado": 0,
    "semestre": 1
  }
