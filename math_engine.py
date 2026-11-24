"""Motor matemático de SuperMath: parseo, operaciones simbólicas (SymPy) y puntos de gráfica (NumPy).

Cada operación es un handler h_xxx(d, preview). Con preview=True solo devuelve el
enunciado en LaTeX (sin calcular); si no, devuelve enunciado, resultado, aproximación y gráfica.
"""
import re

import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


class MathError(Exception):
    """Error con mensaje claro para el usuario."""


# ---------------------------------------------------------------- parseo

_NOMBRES = (
    "sin cos tan cot sec csc asin acos atan acot sinh cosh tanh coth asinh acosh atanh "
    "exp log sqrt Abs factorial floor ceiling sign gamma binomial integrate diff limit summation"
).split()

# Espacio de nombres cerrado para parse_expr (sin builtins). Add/Mul/Pow/Integer/... los
# necesita el propio parser de SymPy al construir la expresión.
_GLOBALS = {"__builtins__": {}}
for _n in _NOMBRES + "Add Mul Pow Integer Float Rational Symbol Matrix pi oo E".split():
    _GLOBALS[_n] = getattr(sp, _n)
_GLOBALS.update(
    ln=sp.log, abs=sp.Abs, sen=sp.sin, tg=sp.tan, arcsin=sp.asin, arccos=sp.acos,
    arctan=sp.atan, e=sp.E, inf=sp.oo, deg=sp.pi / 180,
)

_TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)
_PROHIBIDO = re.compile(r"__|[A-Za-z_\)\]]\s*\.\s*[A-Za-z_]|\bimport\b|[\"'\\]")
_IDENT = re.compile(r"[A-Za-z_]\w*")
_UNICODE = {"π": "pi", "∞": "oo", "√": "sqrt", "·": "*", "×": "*", "÷": "/", "−": "-", "²": "^2", "³": "^3"}

TEX = dict(inv_trig_style="full", ln_notation=True)


def tex(obj):
    s = sp.latex(obj, **TEX)
    # parse_expr(evaluate=False) deja 1/x como Mul(1, 1/x) -> "1 \frac{1}{x}"
    return re.sub(r"(?<![\d.])1 \\frac", r"\\frac", s)


def _normalizar(texto):
    texto = (texto or "").strip()
    for k, v in _UNICODE.items():
        texto = texto.replace(k, v)
    return texto


def parse(texto, evaluate=True):
    texto = _normalizar(texto)
    if not texto:
        raise MathError("Escribe una expresión.")
    if _PROHIBIDO.search(texto):
        raise MathError("La expresión contiene caracteres no permitidos.")
    try:
        return parse_expr(texto, global_dict=dict(_GLOBALS), transformations=_TRANSFORMS, evaluate=evaluate)
    except Exception as ex:
        raise MathError(
            f"No pude interpretar «{texto}». Revisa paréntesis y operadores ({type(ex).__name__})."
        ) from None


def parse_eq(texto, evaluate=True):
    partes = _normalizar(texto).split("=")
    if len(partes) > 2:
        raise MathError("Una ecuación solo puede tener un signo «=».")
    izq, der = partes[0], (partes[1] if len(partes) == 2 else "0")
    return sp.Eq(parse(izq, evaluate), parse(der, evaluate), evaluate=evaluate)


def parse_matrix(texto, evaluate=True):
    v = parse(texto, evaluate)
    try:
        m = sp.Matrix(v) if isinstance(v, (list, tuple)) else v
    except Exception:
        raise MathError("Todas las filas de la matriz deben tener el mismo número de elementos.") from None
    if not isinstance(m, sp.MatrixBase) or m.rows == 0:
        raise MathError("Escribe la matriz por filas, por ejemplo [[1,2],[3,4]].")
    return m


def pair(texto, kind="expr"):
    """Devuelve (versión evaluada, versión sin evaluar para mostrar el enunciado)."""
    f = {"expr": parse, "eq": parse_eq, "matrix": parse_matrix}[kind]
    ev = f(texto, True)
    try:
        sin_ev = f(texto, False)
    except Exception:
        sin_ev = ev
    return ev, sin_ev


def _var(d, e):
    v = d.get("var", "")
    if v:
        if not _IDENT.fullmatch(v):
            raise MathError(f"«{v}» no es un nombre de variable válido.")
        return sp.Symbol(v)
    libres = sorted(e.free_symbols, key=str)
    if sp.Symbol("x") in libres or not libres:
        return sp.Symbol("x")
    return libres[0]


def _simbolos(texto, vacio):
    nombres = [s for s in re.split(r"[,\s]+", texto or "") if s]
    if not nombres:
        raise MathError(vacio)
    for n in nombres:
        if not _IDENT.fullmatch(n):
            raise MathError(f"«{n}» no es un nombre de variable válido.")
    return [sp.Symbol(n) for n in nombres]


def _aprox(o):
    """LaTeX de la aproximación decimal, o None si no aporta nada."""
    try:
        if isinstance(o, sp.MatrixBase):
            if o.free_symbols or all(v.is_Rational for v in o):
                return None
            return tex(o.evalf(6))
        if isinstance(o, sp.Basic) and o.is_number and o.is_real and not o.is_Rational and not o.is_Float:
            return tex(o.evalf(10))
    except Exception:
        pass
    return None


def _salida(problema, resultado, aprox=None, plot=None):
    return {"problem": problema, "result": resultado, "approx": aprox, "plot": plot}


def _lineas(lineas):
    return lineas[0] if len(lineas) == 1 else r"\begin{array}{l}" + r" \\ ".join(lineas) + r"\end{array}"


# ---------------------------------------------------------------- gráficas

def _evaluar(e, syms, mallas):
    f = sp.lambdify(syms, e, modules=["numpy"])
    with np.errstate(all="ignore"):
        y = np.asarray(f(*mallas), dtype=complex)
        y = np.where(np.abs(y.imag) < 1e-9, y.real, np.nan)
        y = np.array(np.broadcast_to(y, mallas[0].shape), dtype=float)
        y[np.abs(y) > 1e6] = np.nan
    return y


def _quitar_polos(y):
    """Rompe la línea donde la función salta de +∞ a -∞ (asíntotas)."""
    with np.errstate(all="ignore"):
        dy = np.abs(np.diff(y))
        ok = np.isfinite(dy)
        if ok.any():
            salto = ok & (np.sign(y[:-1]) * np.sign(y[1:]) < 0) & (dy > 50 * max(np.median(dy[ok]), 1e-12))
            y[1:][salto] = np.nan
    return y


def _limpio(a):
    return [None if not np.isfinite(v) else round(float(v), 6) for v in np.ravel(a)]


def make_plot(items, xr=None, relleno=None):
    """items: [(nombre, expr)]. 1 variable libre -> curva 2D; 2 variables -> superficie 3D."""
    try:
        exprs = [(n, e) for n, e in items if isinstance(e, sp.Basic)]
        if not exprs:
            return None
        syms = sorted(set().union(*[e.free_symbols for _, e in exprs]), key=str)
        if not 1 <= len(syms) <= 2:
            return None
        trig = any(e.has(sp.sin, sp.cos, sp.tan, sp.cot, sp.sec, sp.csc) for _, e in exprs)
        trazos = []
        if len(syms) == 1:
            lo, hi = xr if xr else ((-2 * np.pi, 2 * np.pi) if trig else (-10, 10))
            xs = np.linspace(lo, hi, 801)
            valores = []
            for n, e in exprs:
                try:
                    y = _quitar_polos(_evaluar(e, syms, [xs]))
                except Exception:
                    continue
                trazos.append({"name": n, "x": _limpio(xs), "y": _limpio(y)})
                valores.append(y[np.isfinite(y)])
            if relleno:
                e, a, b = relleno
                xa = np.linspace(a, b, 200)
                ya = _evaluar(e, syms, [xa])
                trazos.append({"name": "área", "x": _limpio(xa), "y": _limpio(ya), "fill": True})
            if not trazos:
                return None
            v = np.concatenate(valores) if valores else np.array([])
            yr = None
            if v.size:
                lo_y, hi_y = np.percentile(v, [2, 98])
                pad = 0.25 * (hi_y - lo_y) or 1.0
                yr = [float(lo_y - pad), float(hi_y + pad)]
            return {"dim": 2, "vars": [str(syms[0])], "yrange": yr, "traces": trazos}
        r = 2 * np.pi if trig else 5
        xs = np.linspace(-r, r, 60)
        X, Y = np.meshgrid(xs, xs)
        for n, e in exprs:
            try:
                Z = _evaluar(e, syms, [X, Y])
            except Exception:
                continue
            trazos.append({"name": n, "z": [_limpio(fila) for fila in Z]})
        if not trazos:
            return None
        return {"dim": 3, "vars": [str(s) for s in syms], "x": _limpio(xs), "y": _limpio(xs), "traces": trazos}
    except Exception:
        return None


# ---------------------------------------------------------------- álgebra y trigonometría

def h_expr(d, preview):
    op = d["op"]
    e, u = pair(d["expr"])
    if not isinstance(e, sp.Basic):
        raise MathError("Escribe una expresión (para matrices usa el módulo de Álgebra Lineal).")
    problema = tex(u)
    if preview:
        return {"problem": problema}
    if op == "evaluar":
        r = e.doit()
    elif op == "simplificar":
        r = sp.simplify(e)
    elif op == "expandir":
        r = sp.expand(sp.expand_trig(e)) if d["module"] == "trig" else sp.expand(e)
    else:
        r = sp.factor(e)
    return _salida(problema, tex(r), _aprox(r), make_plot([("f", r)]))


def h_solve(d, preview):
    eq, equ = pair(d["expr"], "eq")
    if not isinstance(eq, sp.Eq):
        raise MathError("La ecuación es siempre verdadera o siempre falsa: no hay nada que resolver.")
    problema = tex(equ)
    if preview:
        return {"problem": problema}
    x = _var(d, eq)
    if x not in eq.free_symbols:
        raise MathError(f"La ecuación no contiene la variable «{x}».")
    lx = tex(x)
    aprox = None
    if d["module"] == "trig":
        general = sp.solveset(eq, x, sp.S.Reals)
        lineas = [lx + r" \in " + tex(general)]
        if not isinstance(general, sp.FiniteSet):
            principal = sp.solveset(eq, x, sp.Interval.Ropen(0, 2 * sp.pi))
            if isinstance(principal, sp.FiniteSet) and principal:
                lineas.append(r"\text{En } [0, 2\pi):\; " + lx + r" \in " + tex(principal))
                valores = [tex(sp.N(v, 5)) for v in sorted(principal, key=sp.default_sort_key)]
                aprox = lx + r" \approx " + r",\ ".join(valores)
    else:
        sols = sp.solveset(eq, x, sp.S.Complexes)
        if sols == sp.S.EmptySet:
            lineas = [r"\text{Sin solución}"]
        elif isinstance(sols, sp.FiniteSet):
            items = sorted(sols, key=sp.default_sort_key)
            lineas = [f"{lx} = {tex(v)}" for v in items]
            irracionales = [v for v in items if not all(c.is_Rational for c in v.as_real_imag())]
            if irracionales:
                aprox = _lineas([f"{lx} \\approx {tex(sp.N(v, 6))}" for v in irracionales])
        else:
            lineas = [lx + r" \in " + tex(sols)]
    plot = make_plot([("lado izquierdo", eq.lhs), ("lado derecho", eq.rhs)])
    return _salida(problema, _lineas(lineas), aprox, plot)


# ---------------------------------------------------------------- álgebra lineal

def h_system(d, preview):
    filas = [s for s in re.split(r"[\n;]+", d["expr"]) if s.strip()]
    if not filas:
        raise MathError("Escribe al menos una ecuación (una por línea).")
    pares = [pair(s, "eq") for s in filas]
    if not all(isinstance(e, sp.Eq) for e, _ in pares):
        raise MathError("Alguna ecuación es siempre verdadera o falsa; revisa el sistema.")
    problema = r"\begin{cases}" + r" \\ ".join(tex(u) for _, u in pares) + r"\end{cases}"
    if preview:
        return {"problem": problema}
    eqs = [e for e, _ in pares]
    syms = sorted(set().union(*[e.free_symbols for e in eqs]), key=str)
    if not syms:
        raise MathError("El sistema no tiene incógnitas.")
    sols = sp.solve(eqs, syms, dict=True)
    if not sols:
        return _salida(problema, r"\text{Sin solución}")
    filas_tex, filas_aprox = [], []
    for i, s in enumerate(sols, 1):
        pref = rf"\text{{({i})}}\; " if len(sols) > 1 else ""
        filas_tex.append(pref + r",\ ".join(f"{tex(k)} = {tex(v)}" for k, v in s.items()))
        if any(isinstance(v, sp.Basic) and v.is_number and not v.is_Rational for v in s.values()):
            filas_aprox.append(pref + r",\ ".join(f"{tex(k)} \\approx {tex(sp.N(v, 6))}" for k, v in s.items()))
    return _salida(problema, _lineas(filas_tex), _lineas(filas_aprox) if filas_aprox else None)


def h_matrix(d, preview):
    op = d["op"]
    m, mu = pair(d["expr"], "matrix")
    problema = {"determinante": r"\det", "inversa": "", "transpuesta": ""}[op] + tex(mu)
    if op == "inversa":
        problema += r"^{-1}"
    elif op == "transpuesta":
        problema += r"^{T}"
    if preview:
        return {"problem": problema}
    if op == "transpuesta":
        r = m.T
    else:
        if not m.is_square:
            raise MathError(f"La matriz es de {m.rows}×{m.cols}; esta operación requiere una matriz cuadrada.")
        if op == "determinante":
            r = sp.simplify(m.det())
        else:
            if sp.simplify(m.det()) == 0:
                raise MathError("La matriz es singular (determinante 0): no tiene inversa.")
            r = m.inv().applyfunc(sp.simplify)
    return _salida(problema, tex(r), _aprox(r))


# ---------------------------------------------------------------- cálculo diferencial

def h_limit(d, preview):
    e, u = pair(d["expr"])
    x = _var(d, e)
    p, pu = pair(d.get("point") or "0")
    sentido = d.get("dir") or "+-"
    if sentido not in ("+", "-", "+-"):
        raise MathError("El sentido del límite debe ser +, - o ambos.")
    problema = tex(sp.Limit(u, x, pu, sentido))
    if preview:
        return {"problem": problema}
    r = sp.limit(e, x, p, sentido)
    return _salida(problema, tex(r), _aprox(r), make_plot([("f", e)]))


def h_deriv(d, preview):
    e, u = pair(d["expr"])
    x = _var(d, e)
    try:
        n = int(d.get("order") or 1)
    except ValueError:
        raise MathError("El orden de la derivada debe ser un entero.") from None
    if not 1 <= n <= 10:
        raise MathError("El orden de la derivada debe estar entre 1 y 10.")
    problema = tex(sp.Derivative(u, (x, n)))
    if preview:
        return {"problem": problema}
    r = sp.simplify(sp.diff(e, x, n))
    return _salida(problema, tex(r), _aprox(r), make_plot([("f", e), (f"derivada {n}", r)]))


def h_partial(d, preview):
    e, u = pair(d["expr"])
    syms = _simbolos(d.get("vars"), "Indica las variables de derivación, por ejemplo x, y (primero x, luego y).")
    problema = tex(sp.Derivative(u, *syms))
    if preview:
        return {"problem": problema}
    r = sp.simplify(sp.diff(e, *syms))
    return _salida(problema, tex(r), _aprox(r), make_plot([("f", e), ("derivada parcial", r)]))


# ---------------------------------------------------------------- cálculo integral

def _valor_integral(r, problema, plot):
    """Si SymPy no halló forma cerrada, intenta al menos el valor numérico."""
    if isinstance(r, sp.Integral):
        try:
            v = r.evalf(10)
        except Exception:
            raise MathError("No se encontró una forma cerrada ni se pudo aproximar numéricamente.") from None
        if not v.is_number:
            raise MathError("SymPy no encontró una forma cerrada para esta integral.")
        return _salida(problema, tex(r), tex(v), plot)
    return _salida(problema, tex(r), _aprox(r), plot)


def h_indef(d, preview):
    e, u = pair(d["expr"])
    x = _var(d, e)
    problema = tex(sp.Integral(u, x))
    if preview:
        return {"problem": problema}
    r = sp.integrate(e, x)
    if isinstance(r, sp.Integral):
        raise MathError("SymPy no encontró una antiderivada en forma cerrada para esta función.")
    return _salida(problema, tex(r) + " + C", None, make_plot([("f", e), ("F (con C = 0)", r)]))


def h_def(d, preview):
    e, u = pair(d["expr"])
    x = _var(d, e)
    if not d.get("a") or not d.get("b"):
        raise MathError("Indica los límites a y b.")
    a, b = parse(d["a"]), parse(d["b"])
    problema = tex(sp.Integral(u, (x, a, b)))
    if preview:
        return {"problem": problema}
    r = sp.integrate(e, (x, a, b))
    relleno = xr = None
    if a.is_real and b.is_real and a.is_number and b.is_number and a != b:
        lo, hi = sorted([float(a), float(b)])
        pad = max(1.0, (hi - lo) * 0.5)
        xr, relleno = (lo - pad, hi + pad), (e, lo, hi)
    return _valor_integral(r, problema, make_plot([("f", e)], xr, relleno))


def h_multi(d, preview):
    e, u = pair(d["expr"])
    filas = [s for s in re.split(r"[\n;]+", d.get("limits") or "") if s.strip()]
    if not filas:
        raise MathError("Indica al menos una línea de límites con el formato: variable, desde, hasta.")
    lims = []  # de la integral más externa a la más interna
    for fila in filas:
        p = [s.strip() for s in fila.split(",")]
        if len(p) != 3 or not _IDENT.fullmatch(p[0]):
            raise MathError(f"Línea de límites inválida «{fila.strip()}». Usa: variable, desde, hasta (p. ej. x, 0, 1).")
        lims.append((sp.Symbol(p[0]), parse(p[1]), parse(p[2])))
    if len({v for v, _, _ in lims}) != len(lims):
        raise MathError("Cada línea debe integrar una variable distinta.")
    for i, (v, a, b) in enumerate(lims):
        internas = {w for w, _, _ in lims[i:]}  # ella misma y las más internas
        mal = (a.free_symbols | b.free_symbols) & internas
        if mal:
            raise MathError(
                f"Los límites de «{v}» dependen de «{sorted(mal, key=str)[0]}», que se integra antes o a la vez. "
                "Recuerda: la 1ª línea es la integral más externa y la última la más interna."
            )
    # SymPy espera primero la integral más interna (la primera en resolverse)
    problema = tex(sp.Integral(u, *reversed(lims)))
    if preview:
        return {"problem": problema}
    r = sp.integrate(e, *reversed(lims))
    return _valor_integral(r, problema, make_plot([("f", e)]))


OPS = {
    "evaluar": h_expr, "simplificar": h_expr, "expandir": h_expr, "factorizar": h_expr,
    "resolver": h_solve, "sistema": h_system,
    "determinante": h_matrix, "inversa": h_matrix, "transpuesta": h_matrix,
    "limite": h_limit, "derivada": h_deriv, "parcial": h_partial,
    "indefinida": h_indef, "definida": h_def, "multiple": h_multi,
}


def run(d, preview=False):
    d = {k: (v.strip() if isinstance(v, str) else v) for k, v in d.items()}
    d.setdefault("module", "")
    d.setdefault("expr", "")
    handler = OPS.get(d.get("op"))
    if handler is None:
        raise MathError("Operación desconocida.")
    return handler(d, preview)
