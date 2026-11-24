import math
import re


def interpretar_numero(valor, campo: str = "valor", minimo: float | None = None, maximo: float | None = None, opcional: bool = False) -> float | None:
    if(valor is None or (isinstance(valor, str) and valor.strip() == "")):
        if(opcional):
            return None
        raise ValueError(f"Falta {campo}")
    if(isinstance(valor, bool)):
        raise ValueError(f"{campo} no es un número")
    if(isinstance(valor, (int, float))):
        numero = float(valor)
    else:
        texto = str(valor).strip().replace(" ", "").replace(" ", "")
        if("," in texto and "." in texto):
            texto = texto.replace(".", "").replace(",", ".")
        elif("," in texto):
            texto = texto.replace(",", ".")
        try:
            numero = float(texto)
        except ValueError:
            raise ValueError(f"{campo} no es un número válido: {valor}")
    if(math.isnan(numero) or math.isinf(numero)):
        raise ValueError(f"{campo} no es un número válido")
    if(minimo is not None and numero < minimo):
        raise ValueError(f"{campo} debe ser como mínimo {formatear(minimo)}")
    if(maximo is not None and numero > maximo):
        raise ValueError(f"{campo} debe ser como máximo {formatear(maximo)}")
    return numero


def interpretar_entero(valor, campo: str = "valor", minimo: int | None = None, maximo: int | None = None, opcional: bool = False) -> int | None:
    if(isinstance(valor, str) and re.fullmatch(r"\d{1,3}(\.\d{3})+", valor.strip())):
        valor = valor.strip().replace(".", "")
    numero = interpretar_numero(valor, campo, minimo, maximo, opcional)
    if(numero is None):
        return None
    if(abs(numero - round(numero)) > 1e-9):
        raise ValueError(f"{campo} debe ser un número entero")
    return int(round(numero))


def formatear(numero: float | None, decimales: int = 1) -> str:
    if(numero is None):
        return "—"
    texto = f"{numero:,.{decimales}f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    if(decimales > 0 and texto.endswith("," + "0" * decimales)):
        texto = texto[: -(decimales + 1)]
    return texto


def redondear(numero: float | None, decimales: int = 1) -> float | None:
    if(numero is None):
        return None
    return round(numero + 0.0, decimales)
