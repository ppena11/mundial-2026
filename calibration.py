"""
calibration.py — calibración de probabilidades 1X2 (W/D/L).

"El mejor del mundo no se gana con predicciones confiadas, se gana con calibración."

Implementa VECTOR SCALING multinomial (sin dependencias pesadas, solo scipy): aprende
   p'_k ∝ exp(a_k · log p_k + b_k)
sobre las probabilidades crudas del modelo Dixon-Coles, minimizando la log-loss multiclase
con regularización L2 HACIA LA IDENTIDAD (a=1, b=0) para no sobreajustar con pocos datos.
Generaliza el escalado por temperatura (a compartido) y el de Platt.

fit_vector_scaling(probs, outcomes) -> {a:[3], b:[3]}
apply_calibrator(cal, probs)        -> probs calibradas (renormalizadas)

Funciones puras y deterministas; pruebas en test_calibration.py.
"""
import json, math, os
import numpy as np
from scipy.optimize import minimize

_HERE = os.path.dirname(os.path.abspath(__file__))
CAL_FILE = os.path.join(_HERE, "calibration.json")


def _softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_vector_scaling(probs, outcomes, l2=1e-2):
    """Ajusta la calibración. probs: (N,3) [p1,pX,p2]; outcomes: (N,) en {0=local,1=empate,2=visita}.

    l2 regulariza hacia la identidad (a=1,b=0): con pocos datos, apenas toca las probabilidades.
    Devuelve {a:[a1,aX,a2], b:[b1,bX,b2]}.
    """
    P = np.clip(np.asarray(probs, float), 1e-12, 1.0)
    L = np.log(P)
    y = np.asarray(outcomes, int)
    N = len(y)
    if N == 0:
        return {"a": [1.0, 1.0, 1.0], "b": [0.0, 0.0, 0.0]}

    def negll(theta):
        a = theta[:3]; b = theta[3:]
        Q = _softmax(L * a + b)
        ll = -np.mean(np.log(Q[np.arange(N), y] + 1e-12))
        ll += l2 * (np.sum((a - 1.0) ** 2) + np.sum(b ** 2))
        return ll

    res = minimize(negll, np.array([1, 1, 1, 0, 0, 0], float), method="L-BFGS-B")
    return {"a": res.x[:3].tolist(), "b": res.x[3:].tolist()}


def apply_calibrator(cal, probs):
    """Aplica la calibración a unas probabilidades (1D [p1,pX,p2] o 2D (N,3))."""
    if not cal:
        return probs
    P = np.clip(np.asarray(probs, float), 1e-12, 1.0)
    one = (P.ndim == 1)
    if one:
        P = P.reshape(1, -1)
    Q = _softmax(np.log(P) * np.array(cal["a"]) + np.array(cal["b"]))
    return Q[0].tolist() if one else Q


def save(cal, path=CAL_FILE):
    json.dump(cal, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def load(path=CAL_FILE):
    """Carga la calibración guardada (o None si no existe → el modelo usa probs crudas)."""
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return None


# ---------- métricas de evaluación ----------
def log_loss(probs, outcome):
    """Log-loss de una predicción (probs=[p1,pX,p2], outcome en {0,1,2})."""
    p = max(1e-12, min(1.0, probs[outcome]))
    return -math.log(p)

def brier(probs, outcome):
    """Brier multiclase de una predicción."""
    t = [0.0, 0.0, 0.0]; t[outcome] = 1.0
    return sum((probs[k] - t[k]) ** 2 for k in range(3))
