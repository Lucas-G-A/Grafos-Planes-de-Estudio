# -*- coding: utf-8 -*-
"""
grafo_json.py
Versión general que carga planes desde JSON (con campo "estado": 0/1/2)
y conserva todas las operaciones básicas del grafo.

Convención de estado:
0 = no iniciada, 1 = cursando, 2 = completada
"""
from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, List, Optional


# -------------------------
#   Modelo de Datos
# -------------------------

class Nodo:
    def __init__(self, nombre: str, clave: str, creditos: int, estado: int = 0, semestre: int | None = None):
        self.nombre = nombre
        self.clave = clave
        self.creditos = creditos
        # Relaciones
        self.siguiente: List[Nodo] = []  # materias que dependen de este nodo
        self.prerr: List[Nodo] = []      # prerrequisitos (objetos Nodo)
        self.ligadas: List[Nodo] = []    # correquisitos (objetos Nodo)
        # Estado: 0 no iniciada, 1 cursando, 2 completada
        self.estado: int = int(estado)
        self.semestre = semestre

    # Helpers de estado
    def set_estado(self, estado: int) -> None:
        if estado not in (0, 1, 2):
            raise ValueError("Estado inválido. Usa 0 (no iniciada), 1 (cursando), 2 (completada).")
        self.estado = int(estado)

    @property
    def completada(self) -> bool:
        return self.estado == 2

    @property
    def en_progreso(self) -> bool:
        return self.estado == 1

    def __repr__(self) -> str:
        return f"{self.nombre} ({self.clave}) | estado={self.estado}"


class Grafo:
    def __init__(self, nombre_plan: str = "plan"):
        self.nombre_plan = nombre_plan
        self.materias: Dict[str, Nodo] = {}  # clave -> Nodo

    # --------- Construcción del grafo ---------
    def agregar_materia(self, nombre: str, clave: str, creditos: int, estado: int = 0, semestre: int | None = None) -> None:
        if clave not in self.materias:
            self.materias[clave] = Nodo(nombre, clave, creditos, estado, semestre)
        else:
            # Actualiza metadata si ya existía
            n = self.materias[clave]
            n.nombre = nombre
            n.creditos = creditos
            n.estado = int(estado)
            n.semestre = semestre

    def _link_prerreq(self, clave: str, clave_prerr: str) -> None:
        if clave not in self.materias or clave_prerr not in self.materias:
            return
        materia = self.materias[clave]
        prerr = self.materias[clave_prerr]
        if prerr not in materia.prerr:
            materia.prerr.append(prerr)
        if materia not in prerr.siguiente:
            prerr.siguiente.append(materia)

    def _link_coreq(self, clave: str, clave_coreq: str) -> None:
        if clave not in self.materias or clave_coreq not in self.materias:
            return
        a = self.materias[clave]
        b = self.materias[clave_coreq]
        if b not in a.ligadas:
            a.ligadas.append(b)
        if a not in b.ligadas:
            b.ligadas.append(a)

    # --------- Carga y guardado JSON ---------
    def from_json_dict(self, materias: Dict[str, dict]) -> None:
        """
        Carga el grafo en dos pasos desde un dict JSON:
        1) Crear todos los nodos
        2) Conectar prerrequisitos y correquisitos
        """
        # Paso 1: crear todos los nodos
        for clave, datos in materias.items():
            self.agregar_materia(
                nombre=datos["nombre"],
                clave=clave,
                creditos=int(datos["creditos"]),
                estado=int(datos.get("estado", 0)),
                semestre=datos.get("semestre")
            )

        # Paso 2: enlazar prerreqs y coreqs
        for clave, datos in materias.items():
            for pr in datos.get("prerreqs", []):
                self._link_prerreq(clave, pr)
            for co in datos.get("coreqs", []):
                self._link_coreq(clave, co)

    def from_json_file(self, path: str | Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            materias = json.load(f)
        self.from_json_dict(materias)

    def to_json_dict(self) -> Dict[str, dict]:
        """
        Exporta el grafo al mismo formato que se espera en el JSON de entrada,
        incluyendo 'estado'.
        """
        out: Dict[str, dict] = {}
        for clave, n in self.materias.items():
            out[clave] = {
                "nombre": n.nombre,
                "creditos": n.creditos,
                "prerreqs": [p.clave for p in n.prerr],
                "coreqs": [c.clave for c in n.ligadas],
                "estado": n.estado,
                "semestre": n.semestre
            }
        return out

    def to_json_file(self, path: str | Path) -> None:
        data = self.to_json_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --------- Lógica de estado y disponibilidad ---------
    def completar_materia(self, clave: str) -> None:
        if clave in self.materias:
            self.materias[clave].set_estado(2)

    def iniciar_materia(self, clave: str) -> None:
        if clave in self.materias:
            self.materias[clave].set_estado(1)

    def reset_materia(self, clave: str) -> None:
        if clave in self.materias:
            self.materias[clave].set_estado(0)

    def disponibles(self) -> List[Nodo]:
        """
        Regresa materias disponibles para inscribirse bajo la regla:
        - No estar completada (estado != 2)
        - Todos sus prerrequisitos deben estar completados (estado == 2)
        - Si tiene correquisitos, todos los correquisitos también deben cumplir sus propios
          prerrequisitos (y no estar completados), para poder tomarse juntos.
        """
        disp: List[Nodo] = []
        for m in self.materias.values():
            if m.estado != 2 and all(p.estado == 2 for p in m.prerr):
                coreqs_listos = all(
                    (c.estado != 2) and all(p.estado == 2 for p in c.prerr)
                    for c in m.ligadas
                )
                if coreqs_listos:
                    disp.append(m)
        return disp

    # Utilidades
    def get(self, clave: str):
        return self.materias.get(clave)

    def __len__(self):
        return len(self.materias)
    
    def grupos_coreq_disponibles(self):
        vistos = set()
        grupos = []

        # Encuentra componentes conexas por correquisitos (ligadas)
        for n in self.materias.values():
            if n in vistos:
                continue
            # BFS/DFS para agrupar correquisitos
            comp = set()
            stack = [n]
            while stack:
                cur = stack.pop()
                if cur in comp:
                    continue
                comp.add(cur)
                for c in cur.ligadas:
                    if c not in comp:
                        stack.append(c)
            vistos |= comp

        # Verifica disponibilidad del grupo:
        # - nadie completado
        # - todos con prerreqs completos
        if all(x.estado != 2 for x in comp) and all(all(p.estado == 2 for p in x.prerr) for x in comp):
            grupos.append(comp)

        return grupos
    
    def _componentes_coreq(self):
        vistos = set()
        comps = []

        for n in self.materias.values():
            if n in vistos:
                continue
        # DFS/BFS sobre 'ligadas'
            comp = set()
            stack = [n]
            while stack:
                cur = stack.pop()
                if cur in comp:
                    continue
                comp.add(cur)
                for c in cur.ligadas:
                    if c not in comp:
                        stack.append(c)
            vistos |= comp
            comps.append(comp)

        return comps


    def grupos_coreq_disponibles(self):
   
        grupos = []
        for comp in self._componentes_coreq():
        # comp puede ser de tamaño 1 (sin coreqs) o >1 (paquete de correquisitos)
            if all(x.estado != 2 for x in comp) and all(all(p.estado == 2 for p in x.prerr) for x in comp):
                grupos.append(sorted(list(comp), key=lambda x: x.clave))
        return grupos

    
    


# -------------------------
#   Carga múltiple (opcional)
# -------------------------

def cargar_planes_desde_directorio(dir_path: str | Path) -> Dict[str, Grafo]:
    """
    Busca todos los archivos .json en un directorio y crea un Grafo por archivo.
    Retorna un dict: nombre_archivo_sin_extension -> Grafo
    """
    dir_path = Path(dir_path)
    planes: Dict[str, Grafo] = {}
    for json_path in dir_path.glob("*.json"):
        nombre = json_path.stem
        g = Grafo(nombre_plan=nombre)
        g.from_json_file(json_path)
        planes[nombre] = g
    return planes


# -------------------------
#   Ejemplo de uso
# -------------------------
if __name__ == "__main__":
    # Ejemplo: cargar un plan específico
    ejemplo_path = Path("/mnt/data/CDA_B.json")  # cambia la ruta si es necesario
    if ejemplo_path.exists():
        g = Grafo(nombre_plan="CDA_B")
        g.from_json_file(ejemplo_path)
        print(f"Plan '{g.nombre_plan}' cargado con {len(g)} materias.")

        # Mostrar materias disponibles al inicio
        print("\nMaterias disponibles al inicio:")
        print(g.disponibles())

        # Marcar una materia como completada para probar
        g.completar_materia("MAT-14100")
        print("\nDespués de completar Cálculo I:")
        print(g.disponibles())

        # Guardar de vuelta a JSON (con 'estado' actualizado)
        salida = Path("/mnt/data/CDA_B_actualizado.json")
        g.to_json_file(salida)
        print(f"\nGuardado con estados actualizados en: {salida}")
