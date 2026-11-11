ENTREGA SUMATIVA 03 - DAIYA LAUNCHER
TI3043 Ingeniería de Software · Vicente Espinoza y Francisco Tagle

CONTENIDO
  Informe_Sumativa03_Daiya_Launcher.docx   Informe (Word)
  daiya-launcher/                          Código fuente del prototipo
      daiya/         aplicación (core, datos, servicios, ui, util)
      tests/         pruebas automatizadas (pytest)
      herramientas/  datos de prueba, benchmark, capturas y preparación de la demo
      reportes/      resultados de pruebas, cobertura, métricas y capturas
      README.md      instrucciones completas

CÓMO EJECUTAR (requiere Python 3.12 o superior)
  1. Abrir una terminal en la carpeta daiya-launcher
  2. pip install -r requirements.txt
  3. python main.py

CÓMO EJECUTAR LAS PRUEBAS
  pip install -r requirements-dev.txt
  pytest --cov=daiya## Licencia

Este proyecto se distribuye bajo la licencia Apache 2.0.
