import os

import pandas as pd
from flask import Flask

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


@app.get("/api/informes")
def informes():
    """Devuelve los informes. Menciona yolo y tensorflow sin usarlos."""
    return pd.DataFrame().to_json()
