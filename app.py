"""SuperMath: calculadora simbólica y gráfica local. Ejecutar: python app.py"""
from flask import Flask, jsonify, render_template, request

import math_engine as engine

app = Flask(__name__)


def _responder(preview):
    datos = request.get_json(silent=True) or {}
    try:
        return jsonify(engine.run(datos, preview))
    except engine.MathError as ex:
        return jsonify(error=str(ex)), 400
    except Exception as ex:  # cualquier fallo de SymPy se muestra, sin tumbar el servidor
        return jsonify(error=f"No se pudo calcular: {ex}"), 400


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/calcular")
def calcular():
    return _responder(preview=False)


@app.post("/api/preview")
def preview():
    return _responder(preview=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
