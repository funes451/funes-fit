import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ZONA_POR_DEFECTO = "Europe/Madrid"
NOMBRES_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
NOMBRES_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def zona(nombre: str | None = None) -> ZoneInfo:
    return ZoneInfo(nombre or ZONA_POR_DEFECTO)


def ahora_local(nombre_zona: str | None = None, ahora: datetime | None = None) -> datetime:
    instante = ahora or datetime.now(timezone.utc)
    if(instante.tzinfo is None):
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(zona(nombre_zona))


def hoy_local(nombre_zona: str | None = None, ahora: datetime | None = None) -> date:
    return ahora_local(nombre_zona, ahora).date()


def lunes_de(fecha: date) -> date:
    return fecha - timedelta(days=fecha.weekday())


def dias_semana(lunes: date) -> list[date]:
    return [lunes + timedelta(days=i) for i in range(7)]


def texto_fecha(fecha: date) -> str:
    return f"{NOMBRES_DIAS[fecha.weekday()]} {fecha.day} de {NOMBRES_MESES[fecha.month - 1]} de {fecha.year}"


def interpretar_fecha(valor) -> date:
    if(isinstance(valor, datetime)):
        return valor.date()
    if(isinstance(valor, date)):
        return valor
    if(valor is None):
        raise ValueError("Falta la fecha")
    texto = str(valor).strip()
    coincidencia = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", texto)
    if(coincidencia):
        return date(int(coincidencia.group(1)), int(coincidencia.group(2)), int(coincidencia.group(3)))
    coincidencia = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", texto)
    if(coincidencia):
        return date(int(coincidencia.group(3)), int(coincidencia.group(2)), int(coincidencia.group(1)))
    raise ValueError(f"Fecha no válida: {texto}. Usa dd/mm/aaaa o aaaa-mm-dd")


def interpretar_hora(valor) -> str:
    texto = str(valor or "").strip()
    coincidencia = re.fullmatch(r"(\d{1,2})[:.h](\d{2})", texto)
    if(not coincidencia):
        raise ValueError(f"Hora no válida: {texto}. Usa hh:mm")
    horas = int(coincidencia.group(1))
    minutos = int(coincidencia.group(2))
    if(horas > 23 or minutos > 59):
        raise ValueError(f"Hora fuera de rango: {texto}")
    return f"{horas:02d}:{minutos:02d}"


def hora_a_minutos(hora: str) -> int:
    partes = hora.split(":")
    return int(partes[0]) * 60 + int(partes[1])


def en_franja_silencio(minutos: int, inicio: str, fin: str) -> bool:
    minutos_inicio = hora_a_minutos(inicio)
    minutos_fin = hora_a_minutos(fin)
    if(minutos_inicio == minutos_fin):
        return False
    if(minutos_inicio < minutos_fin):
        return minutos_inicio <= minutos < minutos_fin
    return minutos >= minutos_inicio or minutos < minutos_fin


def instante_local_a_utc(fecha: date, hora: str, nombre_zona: str | None = None) -> datetime:
    partes = hora.split(":")
    local = datetime.combine(fecha, time(int(partes[0]), int(partes[1])), tzinfo=zona(nombre_zona))
    return local.astimezone(timezone.utc)
