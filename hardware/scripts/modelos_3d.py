"""Envolventes STEP de los componentes sin modelo 3D en las bibliotecas de KiCad.

  freecadcmd hardware/scripts/modelos_3d.py        (FreeCAD 1.x)

Sirven para exportar el conjunto a STEP y comprobar interferencias con la
carcasa (mechanical/freecad_carcasa.py). Son cajas con las cotas exteriores,
no modelos detallados. Origen en el origen de la huella y z = 0 en la cara de
la placa, como espera KiCad.

| Modelo | Cotas (mm) | Fuente |
|---|---|---|
| BGT60TR13C | 6,5 x 5,0 x 0,9 | hoja de datos (PG-VF2BGA-40-1) |
| MGM260P | 12,9 x 15,0 x 2,2 | 12,9 x 15,0 según la huella; altura aproximada, verificar con la hoja de datos |
| GT-USB-7051x | 9,0 x 3,3 x 7,0 | contorno de la huella; altura aproximada (receptáculo vertical), verificar |
| SiT8008 PQFN 2,5 x 2,0 | 2,5 x 2,0 x 0,85 | hoja de datos (máximo) |
"""
import os

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "hardware", "scripts")
OUT = os.path.join(os.path.dirname(HERE), "lib", "radar60.3dshapes")
V = App.Vector

MODELS = {
    # nombre: (x0, y0, x1, y1, altura) en coordenadas de la huella (y hacia abajo en KiCad -> se invierte)
    "BGT60TR13C_PG-VF2BGA-40-1": (-3.25, -2.5, 3.25, 2.5, 0.9),
    "MGM260P_12.9x15mm": (-6.45, -7.5, 6.45, 7.5, 2.2),
    "USB_C_Receptacle_G-Switch_GT-USB-7051x": (-4.5, -1.63, 4.5, 1.63, 7.0),
    "Oscillator_SMD_SiT_PQFN-4Pin_2.5x2.0mm": (-1.25, -1.0, 1.25, 1.0, 0.85),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    doc = App.newDocument("modelos")
    for name, (x0, y0, x1, y1, h) in MODELS.items():
        # KiCad: y de la huella hacia abajo; en el modelo 3D, y hacia arriba
        box = Part.makeBox(x1 - x0, y1 - y0, h, V(x0, -y1, 0))
        obj = doc.addObject("Part::Feature", name.replace(".", "_").replace("-", "_"))
        obj.Shape = box
        Part.export([obj], os.path.join(OUT, name + ".step"))
        print("modelo", name)


main()
