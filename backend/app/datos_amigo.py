FUENTE_DOCUMENTO = "plan_gimnasio_nutricion_web.md (pendiente de confirmar por el usuario)"

PERFIL_AMIGO = {
    "nombre": "Amigo de Funes",
    "edad_referencia": 19,
    "sexo_formula": "masculino",
    "altura_cm": 174.0,
    "peso_referencia_kg": 55.0,
    "peso_referencia_origen": "Referencia del documento del plan. No es una medición con fecha: confírmala o registra tu peso actual.",
    "hitos_kg": [60.0, 65.0],
    "modo_objetivo": "ganar",
    "objetivo_descripcion": "Ganar peso y masa muscular, especialmente pecho, espalda, hombros y brazos, conservando el trabajo de piernas y el rendimiento en fútbol sala.",
    "experiencia": "principiante",
    "alimentos_excluidos": [],
    "comensales": 1,
    "zona_horaria": "Europe/Madrid",
    "presupuesto_semanal": None,
    "presupuesto_confirmado": False,
    "plan_aceptado": False,
    "agua_referencia": "2–2,5 L/día como referencia inicial, ajustable por ejercicio, calor y sudor",
    "horarios": {},
    "pendientes_confirmar": [
        {"campo": "nombre", "pregunta": "Tu nombre"},
        {"campo": "inicio_plan", "pregunta": "Fecha en la que empiezas el plan"},
        {"campo": "datos_documento", "pregunta": "Confirma edad (19), sexo para la fórmula (masculino), altura (174 cm) y peso de referencia (55 kg), o corrígelos"},
        {"campo": "alergias", "pregunta": "Alergias o intolerancias alimentarias"},
        {"campo": "alimentos_excluidos", "pregunta": "Alimentos que no te gustan"},
        {"campo": "molestias_actuales", "pregunta": "¿Tienes alguna molestia o lesión actualmente?"},
        {"campo": "horarios", "pregunta": "Horarios de comidas, gimnasio y fútbol"},
        {"campo": "actividad_cotidiana", "pregunta": "Actividad diaria fuera del deporte (trabajo, estudios, pasos)"},
        {"campo": "presupuesto_semanal", "pregunta": "Presupuesto semanal de alimentación"},
    ],
}

OBJETIVO_AMIGO = {
    "kcal": 2900,
    "proteina_g": 110,
    "hidratos_g": 400,
    "grasas_g": 95,
    "fibra_g": 30,
    "nota": "Objetivos iniciales orientativos del documento. Los macros suman unas 2.895 kcal (110×4 + 400×4 + 95×9); la diferencia con 2.900 es redondeo. No son necesidades medidas ni un superávit confirmado.",
}

ALIMENTOS_AMIGO = [
    {"codigo": "leche_entera", "nombre": "Leche entera", "base": "100ml", "kcal": 65, "proteina": 3.1, "hidratos": 4.7, "grasas": 3.6, "estado_peso": "tal_cual", "seccion": "Lácteos y huevos", "alergenos": ["leche"], "densidad": 1.03},
    {"codigo": "crema_cacahuete", "nombre": "Crema de cacahuete 100 %", "base": "100g", "kcal": 590, "proteina": 25, "hidratos": 12, "grasas": 50, "estado_peso": "tal_cual", "seccion": "Aceites y frutos secos", "alergenos": ["cacahuete"]},
    {"codigo": "pan_blanco", "nombre": "Pan blanco (barra)", "base": "100g", "kcal": 260, "proteina": 8.5, "hidratos": 51, "grasas": 1.5, "estado_peso": "tal_cual", "seccion": "Panadería", "alergenos": ["gluten (trigo)"]},
    {"codigo": "pasta", "nombre": "Pasta (macarrones)", "base": "100g", "kcal": 357, "proteina": 12, "hidratos": 72, "grasas": 1.5, "estado_peso": "seco", "seccion": "Despensa seca", "alergenos": ["gluten (trigo)"]},
    {"codigo": "naranja", "nombre": "Naranja sin piel", "base": "100g", "kcal": 47, "proteina": 0.9, "hidratos": 9.4, "grasas": 0.1, "estado_peso": "comestible", "seccion": "Fruta y verdura", "factor_compra": 1.35, "nota_factor": "Estimación: la parte comestible es aproximadamente el 75 % del peso con piel"},
]

PRODUCTOS_AMIGO = [
    {"codigo": "p_leche_entera", "alimento": "leche_entera", "nombre": "Leche entera brik 1 L", "capacidad": 1, "unidad": "l", "capacidad_util": 1000},
    {"codigo": "p_crema_cacahuete", "alimento": "crema_cacahuete", "nombre": "Crema de cacahuete bote 350 g", "capacidad": 350, "unidad": "g", "capacidad_util": 350},
    {"codigo": "p_pan_blanco", "alimento": "pan_blanco", "nombre": "Barra de pan aprox. 250 g", "capacidad": 250, "unidad": "g", "capacidad_util": 250, "nota": "Congela en trozos lo que no vayas a comer en 1–2 días."},
    {"codigo": "p_pasta", "alimento": "pasta", "nombre": "Macarrones 1 kg", "capacidad": 1, "unidad": "kg", "capacidad_util": 1000},
    {"codigo": "p_naranja", "alimento": "naranja", "nombre": "Naranjas a granel (redondeo a 100 g)", "capacidad": 100, "unidad": "g", "capacidad_util": 100},
]

RECETAS_AMIGO = [
    {
        "codigo": "am_desayuno_avena",
        "nombre": "Avena con leche entera, plátano y crema de cacahuete",
        "momento_tipico": "desayuno",
        "tiempo_min": 5,
        "ingredientes": [("avena", 80, "g"), ("leche_entera", 300, "ml"), ("platano", 120, "g"), ("crema_cacahuete", 15, "g")],
        "pasos": ["Calienta la avena con la leche 2 minutos o déjala remojada desde la noche anterior.", "Añade el plátano en rodajas y la crema de cacahuete por encima."],
        "conservacion": "Remojada en nevera aguanta hasta el día siguiente.",
        "sustituciones": ["Crema de cacahuete → 15 g de frutos secos (recalcula)", "Plátano → otra fruta (recalcula)"],
    },
    {
        "codigo": "am_desayuno_tostadas",
        "nombre": "Tostadas con tomate y huevos revueltos, con leche",
        "momento_tipico": "desayuno",
        "tiempo_min": 10,
        "ingredientes": [("pan_blanco", 100, "g"), ("tomate", 80, "g"), ("aceite_oliva", 10, "g"), ("huevo", 120, "g"), ("leche_entera", 250, "ml")],
        "pasos": ["Tuesta el pan y úntalo con el tomate rallado y la mitad del aceite.", "Haz los huevos revueltos con el resto del aceite hasta que estén cuajados.", "Acompaña con el vaso de leche."],
        "conservacion": "Preparar en el momento.",
        "sustituciones": ["Huevos → 60 g de atún o pavo (recalcula)"],
    },
    {
        "codigo": "am_merienda_tostadas",
        "nombre": "Tostadas con crema de cacahuete y plátano, con leche",
        "momento_tipico": "merienda",
        "tiempo_min": 5,
        "ingredientes": [("pan_blanco", 80, "g"), ("crema_cacahuete", 20, "g"), ("platano", 120, "g"), ("leche_entera", 200, "ml")],
        "pasos": ["Unta el pan con la crema de cacahuete y añade el plátano en rodajas.", "Acompaña con la leche."],
        "conservacion": "Para llevar, monta el bocadillo en el momento o la noche antes en la nevera.",
        "sustituciones": ["Esta merienda puede sustituirse por el batido energético (no tomar los dos sin decidirlo)."],
    },
    {
        "codigo": "am_batido",
        "nombre": "Batido energético",
        "momento_tipico": "merienda",
        "tiempo_min": 5,
        "ingredientes": [("leche_entera", 300, "ml"), ("platano", 120, "g"), ("avena", 60, "g"), ("crema_cacahuete", 25, "g")],
        "pasos": ["Pon todos los ingredientes en la batidora y bate hasta que no queden grumos.", "Pesa la parte comestible del plátano: un plátano mediano ronda los 120 g sin piel."],
        "conservacion": "Mejor recién hecho. En nevera, tapado, hasta 24 h; agita antes de beber.",
        "sustituciones": ["Sustituye a una merienda o se añade de forma consciente; no se suma por defecto al menú.", "Crema de cacahuete → frutos secos (recalcula y revisa alérgenos)."],
        "notas": "Referencia del documento: unas 680 kcal. La app lo recalcula con los pesos y valores de los ingredientes.",
    },
    {
        "codigo": "am_arroz_pollo",
        "nombre": "Arroz con pollo y verduras, con naranja",
        "momento_tipico": "comida",
        "tiempo_min": 35,
        "modo_preparacion": "lote",
        "max_nevera_dias": 1,
        "ingredientes": [("arroz", 130, "g"), ("pollo", 130, "g"), ("pimiento", 50, "g"), ("cebolla", 50, "g"), ("zanahoria", 50, "g"), ("aceite_oliva", 15, "g"), ("naranja", 150, "g")],
        "pasos": ["Sofríe la cebolla, el pimiento y la zanahoria con el aceite.", "Añade el pollo troceado y dóralo hasta que no quede rosado por dentro.", "Añade el arroz, el doble de agua y sal, y cuece 15–18 minutos.", "De postre, la naranja."],
        "conservacion": "Arroz cocido: enfríalo rápido y en nevera como máximo 24 h, o congélalo por raciones.",
        "sustituciones": ["Pollo → pavo (recalcula)", "Arroz → pasta (recalcula)"],
    },
    {
        "codigo": "am_macarrones_atun",
        "nombre": "Macarrones con tomate y atún, con naranja",
        "momento_tipico": "comida",
        "tiempo_min": 20,
        "modo_preparacion": "lote",
        "ingredientes": [("pasta", 140, "g"), ("tomate_triturado", 150, "g"), ("atun_natural", 80, "g"), ("cebolla", 50, "g"), ("aceite_oliva", 15, "g"), ("naranja", 150, "g")],
        "pasos": ["Cuece la pasta según el paquete.", "Sofríe la cebolla con el aceite, añade el tomate triturado y deja 10 minutos.", "Mezcla con la pasta y el atún escurrido.", "De postre, la naranja."],
        "conservacion": "Refrigera pronto y consume en 2 días, o congela la salsa por raciones.",
        "sustituciones": ["Atún → pollo cocinado (recalcula)"],
    },
    {
        "codigo": "am_lentejas_arroz",
        "nombre": "Lentejas con arroz, patata y verduras",
        "momento_tipico": "comida",
        "tiempo_min": 35,
        "modo_preparacion": "lote",
        "ingredientes": [("lentejas_cocidas", 300, "g"), ("arroz", 60, "g"), ("patata", 150, "g"), ("zanahoria", 80, "g"), ("cebolla", 50, "g"), ("aceite_oliva", 12, "g")],
        "pasos": ["Sofríe la cebolla y la zanahoria con el aceite.", "Añade la patata en trozos, el arroz y agua para cubrir; cuece 18 minutos.", "Añade las lentejas cocidas lavadas y cuece 5 minutos más. Guiso con trozos, sin triturar."],
        "conservacion": "Refrigera pronto y consume en 2 días, o congela por raciones.",
        "sustituciones": ["Lentejas → garbanzos cocidos (recalcula)"],
    },
    {
        "codigo": "am_tortilla",
        "nombre": "Tortilla de patata con pan",
        "momento_tipico": "cena",
        "tiempo_min": 30,
        "ingredientes": [("huevo", 180, "g"), ("patata", 250, "g"), ("cebolla", 50, "g"), ("aceite_oliva", 15, "g"), ("pan_blanco", 80, "g")],
        "pasos": ["Cocina la patata en láminas y la cebolla en sartén tapada con parte del aceite 15 minutos (o en el microondas).", "Bate los huevos, mezcla y cuaja con el resto del aceite hasta que esté hecha por dentro.", "Acompaña con el pan."],
        "conservacion": "En nevera, tapada, hasta 2 días.",
        "sustituciones": ["Pan → 60 g de arroz en seco cocido (recalcula)"],
    },
    {
        "codigo": "am_pollo_patatas",
        "nombre": "Pollo a la plancha con patatas al horno y ensalada",
        "momento_tipico": "cena",
        "tiempo_min": 40,
        "ingredientes": [("pollo", 150, "g"), ("patata", 300, "g"), ("lechuga", 80, "g"), ("tomate", 100, "g"), ("aceite_oliva", 15, "g"), ("pan_blanco", 60, "g")],
        "pasos": ["Hornea la patata en gajos con parte del aceite a 200 °C unos 30 minutos.", "Haz el pollo a la plancha hasta que no quede rosado por dentro.", "Ensalada de lechuga y tomate con el resto del aceite. Pan aparte."],
        "conservacion": "Refrigera las sobras pronto y consúmelas en 2 días.",
        "sustituciones": ["Pollo → merluza (recalcula)"],
    },
    {
        "codigo": "am_garbanzos_huevo",
        "nombre": "Garbanzos salteados con huevo y arroz",
        "momento_tipico": "cena",
        "tiempo_min": 25,
        "ingredientes": [("garbanzos_cocidos", 250, "g"), ("huevo", 120, "g"), ("pimiento", 50, "g"), ("cebolla", 50, "g"), ("arroz", 60, "g"), ("aceite_oliva", 12, "g")],
        "pasos": ["Cuece el arroz.", "Saltea la cebolla y el pimiento con el aceite, añade los garbanzos escurridos y dora 5 minutos.", "Añade los huevos batidos y remueve hasta que cuajen. Sirve con el arroz."],
        "conservacion": "Arroz cocido: nevera máximo 24 h. El salteado, 2 días.",
        "sustituciones": ["Garbanzos → lentejas cocidas (recalcula)"],
    },
    {
        "codigo": "am_snack",
        "nombre": "Snack opcional: fruta y frutos secos",
        "momento_tipico": "extra",
        "tiempo_min": 1,
        "ingredientes": [("manzana", 150, "g"), ("frutos_secos", 25, "g")],
        "pasos": ["Tómalo si tienes hambre o un día de mucha actividad. No suma al plan hasta que lo registres."],
        "conservacion": "—",
        "sustituciones": ["Manzana → plátano o naranja (recalcula)"],
    },
]

MENU_AMIGO = [
    ("am_desayuno_avena", "am_arroz_pollo", "am_pollo_patatas"),
    ("am_desayuno_tostadas", "am_macarrones_atun", "am_tortilla"),
    ("am_desayuno_avena", "am_lentejas_arroz", "am_garbanzos_huevo"),
    ("am_desayuno_tostadas", "am_arroz_pollo", "am_pollo_patatas"),
    ("am_desayuno_avena", "am_macarrones_atun", "am_tortilla"),
    ("am_desayuno_tostadas", "am_lentejas_arroz", "am_garbanzos_huevo"),
    ("am_desayuno_avena", "am_arroz_pollo", "am_tortilla"),
]

NOMBRES_SESION_AMIGO = {
    "torso_a": "Torso A",
    "piernas": "Piernas moderadas y abdomen",
    "torso_b": "Torso B ligero",
    "torso_c": "Torso C",
}

DISTRIBUCION_AMIGO = {
    "0": [{"tipo": "gimnasio", "sesion": "torso_a"}],
    "1": [{"tipo": "gimnasio", "sesion": "piernas"}],
    "2": [{"tipo": "gimnasio", "sesion": "torso_b"}, {"tipo": "futbol", "titulo": "Fútbol sala"}],
    "3": [{"tipo": "gimnasio", "sesion": "torso_c"}],
    "4": [{"tipo": "futbol", "titulo": "Fútbol sala"}, {"tipo": "recuperacion", "titulo": "Recuperación suave (opcional)", "opcional": True}],
    "5": [],
    "6": [],
}

ADAPTACION_AMIGO = {
    "semanas": 2,
    "semanas_si_parada_larga": 2,
    "series_min": 1,
    "series_max": 2,
    "rir_adaptacion": "2–3",
    "rir_trabajo": "2–3",
    "texto": "Adaptación inicial (semanas 1–2): 1–2 series por ejercicio, progresando según tolerancia y dejando 2–3 repeticiones en reserva.",
    "texto_trabajo": "Progresa según tolerancia, generalmente con 2–3 repeticiones en reserva.",
}

RUTINA_AMIGO = None

ADVERTENCIA_AMIGO = None
