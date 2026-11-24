import { useEffect, useState } from "react";
import { api } from "../api";
import { CampoTexto, Cargando, GraficaLinea, Selector, useApp, useDatos } from "../componentes";
import { fechaCorta, fechaIso, numero, textoNumeroEntrada, uuid } from "../utilidades";

const ETIQUETAS_DIARIO: any = {
    sueno_horas: "Sueño (horas)",
    calidad_sueno: "Calidad del sueño (1–5)",
    hambre: "Hambre (1–5)",
    energia: "Energía (1–5)",
    estres: "Estrés (1–5)",
    dolor: "Dolor o molestias (0–10)",
    digestion: "Digestión (1–5)",
    agua_ml: "Agua (ml)",
    pasos: "Pasos",
    cardio_min: "Cardio (min)",
    molestias: "Dónde/qué molestia",
    notas: "Notas",
};

function Diario(): any {
    const { registrar, avisar } = useApp();
    const [fecha, setFecha] = useState<string>(fechaIso(new Date()));
    const { datos, error, recargar } = useDatos(`/api/diario/${fecha}`);
    const [valores, setValores] = useState<any>({});
    const [nuevoCampo, setNuevoCampo] = useState<any>({ etiqueta: "", tipo: "escala", unidad: "", minimo: "", maximo: "" });
    useEffect(() => {
        if(datos){
            const iniciales: any = {};
            for(const [clave, valor] of Object.entries(datos.entrada.datos)){
                iniciales[clave] = typeof valor == "number" ? textoNumeroEntrada(valor as number) : valor;
            }
            setValores(iniciales);
        }
    }, [datos]);
    if(!datos){
        return <Cargando error={error} />;
    }
    const guardar = async (): Promise<void> => {
        try {
            await registrar("diario.guardar", { fecha: fecha, datos: valores, version_base: datos.entrada.version });
            avisar("Diario guardado");
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const crearCampo = async (): Promise<void> => {
        try {
            await api.post("/api/campos-personalizados", nuevoCampo);
            setNuevoCampo({ etiqueta: "", tipo: "escala", unidad: "", minimo: "", maximo: "" });
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const campos: any[] = datos.campos.concat(datos.personalizados.map((c: any) => ({ ...c, personalizado: true })));
    return (
        <section className="tarjeta">
            <h2>Diario</h2>
            <p className="suave">Todo opcional. Son notas para ti: la app no los convierte en diagnósticos. {datos.agua_referencia ? `Agua: ${datos.agua_referencia}. ` : ""}{datos.nota_agua}</p>
            <CampoTexto etiqueta="Fecha" tipo="date" valor={fecha} alCambiar={setFecha} />
            <div className="rejilla-2" style={{ marginTop: 8 }}>
                {campos.map((c: any) => {
                    const etiqueta: string = c.personalizado ? `${c.etiqueta}${c.unidad ? ` (${c.unidad})` : ""}` : ETIQUETAS_DIARIO[c.clave] || c.clave;
                    if(c.tipo == "texto"){
                        return <label key={c.clave} style={{ gridColumn: "1 / -1" }}>{etiqueta}<textarea value={valores[c.clave] ?? ""} onChange={(e: any) => setValores({ ...valores, [c.clave]: e.target.value })} /></label>;
                    }
                    if(c.tipo == "si_no"){
                        return <label key={c.clave} className="casilla"><input type="checkbox" checked={!!valores[c.clave]} onChange={(e: any) => setValores({ ...valores, [c.clave]: e.target.checked })} />{etiqueta}</label>;
                    }
                    return <CampoTexto key={c.clave} etiqueta={etiqueta} modo="decimal" valor={valores[c.clave] ?? ""} alCambiar={(v: string) => setValores({ ...valores, [c.clave]: v })} />;
                })}
            </div>
            <button className="primario" style={{ marginTop: 10 }} onClick={guardar}>Guardar día</button>
            <details style={{ marginTop: 10 }}>
                <summary>Añadir un campo propio</summary>
                <div className="rejilla-2">
                    <CampoTexto etiqueta="Nombre" valor={nuevoCampo.etiqueta} alCambiar={(v: string) => setNuevoCampo({ ...nuevoCampo, etiqueta: v })} />
                    <Selector etiqueta="Tipo" valor={nuevoCampo.tipo} alCambiar={(v: string) => setNuevoCampo({ ...nuevoCampo, tipo: v })} opciones={[{ valor: "escala", texto: "Escala 1–5" }, { valor: "numero", texto: "Número" }, { valor: "entero", texto: "Número entero" }, { valor: "si_no", texto: "Sí / no" }, { valor: "texto", texto: "Texto" }]} />
                    <CampoTexto etiqueta="Unidad" valor={nuevoCampo.unidad} alCambiar={(v: string) => setNuevoCampo({ ...nuevoCampo, unidad: v })} />
                    <CampoTexto etiqueta="Mínimo" modo="decimal" valor={nuevoCampo.minimo} alCambiar={(v: string) => setNuevoCampo({ ...nuevoCampo, minimo: v })} />
                    <CampoTexto etiqueta="Máximo" modo="decimal" valor={nuevoCampo.maximo} alCambiar={(v: string) => setNuevoCampo({ ...nuevoCampo, maximo: v })} />
                </div>
                <button onClick={crearCampo} style={{ marginTop: 8 }}>Crear campo</button>
            </details>
        </section>
    );
}

async function reducirImagen(archivo: File): Promise<Blob> {
    try {
        const mapa: ImageBitmap = await createImageBitmap(archivo);
        const escala: number = Math.min(1, 1600 / Math.max(mapa.width, mapa.height));
        const lienzo: HTMLCanvasElement = document.createElement("canvas");
        lienzo.width = Math.round(mapa.width * escala);
        lienzo.height = Math.round(mapa.height * escala);
        const contexto: CanvasRenderingContext2D | null = lienzo.getContext("2d");
        if(!contexto){
            return archivo;
        }
        contexto.drawImage(mapa, 0, 0, lienzo.width, lienzo.height);
        const reducida: Blob | null = await new Promise((resolver: any) => lienzo.toBlob(resolver, "image/jpeg", 0.82));
        return reducida && reducida.size < archivo.size ? reducida : archivo;
    } catch (error) {
        return archivo;
    }
}

function Fotos(): any {
    const { avisar } = useApp();
    const { datos, recargar } = useDatos("/api/fotos");
    const [urls, setUrls] = useState<any>({});
    const subir = async (original: File): Promise<void> => {
        const archivo: Blob = await reducirImagen(original);
        const formulario: FormData = new FormData();
        formulario.append("fecha", fechaIso(new Date()));
        formulario.append("archivo", archivo, archivo === original ? original.name : "foto.jpg");
        try {
            await api.post("/api/fotos", formulario);
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const ver = async (id: number): Promise<void> => {
        const respuesta: Response = await fetch(`/api/fotos/${id}/archivo`, { credentials: "same-origin" });
        if(respuesta.ok){
            setUrls({ ...urls, [id]: URL.createObjectURL(await respuesta.blob()) });
        }
    };
    return (
        <section className="tarjeta">
            <h2>Fotos privadas</h2>
            <p className="suave">{datos ? datos.nota : ""}</p>
            <label className="boton">Añadir foto<input type="file" accept="image/*" style={{ display: "none" }} onChange={(e: any) => e.target.files[0] && subir(e.target.files[0])} /></label>
            <ul className="lista">
                {(datos ? datos.fotos : []).map((f: any) => (
                    <li key={f.id}>
                        <div className="fila separada">
                            <span>{f.fecha}</span>
                            <span className="fila">
                                {!urls[f.id] ? <button className="pequeno" onClick={() => ver(f.id)}>Ver</button> : null}
                                <button className="pequeno peligro" onClick={async () => { if(window.confirm("¿Borrar esta foto?")){ await api.borrar(`/api/fotos/${f.id}`); recargar(); } }}>Borrar</button>
                            </span>
                        </div>
                        {urls[f.id] ? <img src={urls[f.id]} alt={`Foto de progreso del ${f.fecha}`} style={{ maxWidth: "100%", borderRadius: 10, marginTop: 6 }} /> : null}
                    </li>
                ))}
            </ul>
        </section>
    );
}

function Revision(): any {
    const { avisar } = useApp();
    const { datos } = useDatos("/api/objetivos/revision");
    if(!datos){
        return null;
    }
    const p: any = datos.propuesta;
    const aceptar = async (): Promise<void> => {
        try {
            await api.post("/api/objetivos", { kcal: p.kcal_propuesta, origen: "propuesta_aceptada", nota: p.mensaje });
            avisar("Nuevo objetivo vigente desde hoy. El historial no cambia. Ajusta las raciones del menú desde Menú.");
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <section className="tarjeta">
            <h2>Revisión del objetivo</h2>
            <div className={`aviso ${p.accion == "detener" ? "rojo" : ""}`}>{p.mensaje}</div>
            {p.referencia ? <p className="suave">{p.referencia}</p> : null}
            {p.requiere_aceptacion ? <button className="primario" onClick={aceptar}>Aceptar {p.delta_kcal > 0 ? "+" : ""}{p.delta_kcal} kcal/día</button> : null}
        </section>
    );
}

export default function Progreso(): any {
    const { registrar, avisar, estadoSync, perfil } = useApp();
    const ruta: string = window.location.hash;
    const peso: any = useDatos("/api/progreso/peso");
    const resumen: any = useDatos("/api/progreso/resumen-semanal");
    const ejercicios: any = useDatos("/api/gym/ejercicios");
    const [ejercicio, setEjercicio] = useState<string>("");
    const cargas: any = useDatos(ejercicio ? `/api/gym/progreso/${ejercicio}` : null);
    const [medida, setMedida] = useState<any>({ tipo: "peso", valor: "", fecha: fechaIso(new Date()), condiciones: "manana" });
    const medidas: any = useDatos(`/api/mediciones`);

    const guardarMedida = async (): Promise<void> => {
        try {
            await registrar("medicion.crear", { id_cliente: uuid(), ...medida });
            setMedida({ ...medida, valor: "" });
            avisar("Medida guardada");
            peso.recargar();
            medidas.recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    if(ruta.startsWith("#/progreso/diario")){
        return (
            <div>
                <div className="cabecera"><h1>Diario</h1><a className="boton" href="#/progreso">Volver</a></div>
                <Diario />
            </div>
        );
    }

    const p: any = peso.datos;
    const r: any = resumen.datos;
    return (
        <div>
            <div className="cabecera">
                <h1>Progreso</h1>
                {estadoSync}
            </div>
            <section className="tarjeta">
                <h2>Registrar medida</h2>
                <div className="rejilla-2">
                    <Selector etiqueta="Medida" valor={medida.tipo} alCambiar={(v: string) => setMedida({ ...medida, tipo: v })} opciones={[{ valor: "peso", texto: "Peso (kg)" }, { valor: "cintura", texto: "Cintura (cm)" }, { valor: "cadera", texto: "Cadera (cm)" }, { valor: "pecho", texto: "Pecho (cm)" }, { valor: "brazo", texto: "Brazo (cm)" }, { valor: "muslo", texto: "Muslo (cm)" }]} />
                    <CampoTexto etiqueta="Valor" modo="decimal" valor={medida.valor} ejemplo="111,8" alCambiar={(v: string) => setMedida({ ...medida, valor: v })} />
                    <CampoTexto etiqueta="Fecha" tipo="date" valor={medida.fecha} alCambiar={(v: string) => setMedida({ ...medida, fecha: v })} />
                    <Selector etiqueta="Condiciones (opcional)" valor={medida.condiciones} alCambiar={(v: string) => setMedida({ ...medida, condiciones: v })} vacio="Sin indicar" opciones={[{ valor: "manana", texto: "Por la mañana" }, { valor: "otra_hora", texto: "Otra hora" }]} />
                </div>
                <button className="primario" style={{ marginTop: 8 }} disabled={!medida.valor} onClick={guardarMedida}>Guardar</button>
                <p className="suave">Pesarse por la mañana en condiciones parecidas ayuda a comparar, pero no es obligatorio.</p>
            </section>
            <section className="tarjeta">
                <h2>Peso</h2>
                {!p ? <Cargando error={peso.error} /> : (
                    <>
                        <GraficaLinea descripcion="Peso: puntos registrados y media semanal" puntos={p.puntos} medias={p.semanas.filter((s: any) => s.valida).map((s: any) => ({ fecha: s.lunes, valor: s.media }))} lineas={p.modo == "ganar" ? p.hitos.map((h: any) => h.kg) : []} />
                        <p className="suave">Puntos: tus pesajes. Línea: media semanal (solo con 3 o más pesajes).</p>
                        <table className="tabla">
                            <thead><tr><th>Semana</th><th className="num">Pesajes</th><th className="num">Media</th></tr></thead>
                            <tbody>{p.semanas.slice(-6).reverse().map((s: any) => <tr key={s.lunes}><td>{fechaCorta(s.lunes)}</td><td className="num">{s.medidas}</td><td className="num">{s.media == null ? "faltan datos" : `${numero(s.media, 1)} kg`}</td></tr>)}</tbody>
                        </table>
                        {p.cambios.length ? <p>Último cambio semanal: {numero(p.cambios[p.cambios.length - 1].kg, 2)} kg ({numero(p.cambios[p.cambios.length - 1].pct_semanal, 2)} %).</p> : null}
                        {p.modo == "ganar" && p.hitos.length ? (
                            <div>
                                {p.hitos.map((h: any) => (
                                    <div key={h.kg} style={{ marginBottom: 8 }}>
                                        <div className="fila separada"><span>Hito {numero(h.kg)} kg</span><span className="suave">{h.avance == null ? "faltan datos" : `${Math.round(h.avance * 100)} %`}</span></div>
                                        <div className="barra-progreso" aria-hidden="true"><div style={{ width: `${Math.round((h.avance || 0) * 100)}%` }} /></div>
                                    </div>
                                ))}
                                <p className="suave">Referencia orientativa: subir unos 0,15–0,30 kg por semana. Subir de peso es el objetivo, no un mal resultado; no toda la subida es músculo.</p>
                                {p.referencia_plan_kg && p.puntos.length == 0 ? <p className="suave">Peso de referencia del plan: {numero(p.referencia_plan_kg, 1)} kg. {p.referencia_plan_origen}</p> : null}
                            </div>
                        ) : null}
                        {p.modo == "perder" && perfil && perfil.meta_revision_kg ? <p className="suave">Primera revisión opcional en torno a {numero(perfil.meta_revision_kg, 1)} kg, sin fecha ni promesa. Al principio el peso puede variar por el agua.</p> : null}
                        <p className="suave">{p.nota}</p>
                    </>
                )}
            </section>
            <Revision />
            <section className="tarjeta">
                <h2>Esta semana</h2>
                {!r ? <Cargando error={resumen.error} /> : (
                    <ul className="lista">
                        <li>Peso: {r.peso.media == null ? `${r.peso.medidas} pesajes (hacen falta 3 para la media)` : `${numero(r.peso.media, 1)} kg de media (${r.peso.medidas} pesajes)`}</li>
                        <li>Comidas: {r.comidas.registradas} registradas de {r.comidas.planificadas} ({r.comidas.segun_plan} como estaban previstas; {r.comidas.sin_registro} sin registro, no cuentan como cero)</li>
                        <li>Entrenos: {r.entrenos.realizados} completos{r.entrenos.parciales ? `, ${r.entrenos.parciales} parciales` : ""}</li>
                        <li>Pasos: {r.pasos.media == null ? "sin datos" : `${numero(r.pasos.media)} de media en ${r.pasos.dias} días`}</li>
                        <li>Sueño: {r.sueno_horas.media == null ? "sin datos" : `${numero(r.sueno_horas.media, 1)} h de media`}</li>
                    </ul>
                )}
                <a href="#/progreso/diario" className="boton" style={{ marginTop: 8 }}>Abrir diario</a>
            </section>
            <section className="tarjeta">
                <h2>Medidas</h2>
                <ul className="lista">
                    {(medidas.datos ? medidas.datos.mediciones.filter((m: any) => m.tipo != "peso").slice(0, 10) : []).map((m: any) => <li key={m.id}>{m.fecha}: {m.tipo} {numero(m.valor, 1)} {m.unidad}</li>)}
                </ul>
                {medidas.datos && medidas.datos.mediciones.filter((m: any) => m.tipo != "peso").length == 0 ? <p className="suave">Sin medidas de cintura u otras todavía.</p> : null}
            </section>
            <section className="tarjeta">
                <h2>Cargas</h2>
                <Selector etiqueta="Ejercicio" valor={ejercicio} alCambiar={setEjercicio} vacio="Elige un ejercicio" opciones={(ejercicios.datos ? ejercicios.datos.ejercicios : []).map((e: any) => ({ valor: String(e.id), texto: e.nombre }))} />
                {cargas.datos ? (cargas.datos.puntos.length == 0 ? <p className="suave">Sin series registradas.</p> : (
                    <>
                        <GraficaLinea descripcion="Carga máxima por sesión" puntos={cargas.datos.puntos.map((x: any) => ({ fecha: x.fecha, valor: x.peso_kg }))} medias={cargas.datos.puntos.map((x: any) => ({ fecha: x.fecha, valor: x.peso_kg }))} />
                        <ul className="lista">{cargas.datos.puntos.slice(-5).reverse().map((x: any) => <li key={x.fecha}>{x.fecha}: {numero(x.peso_kg, 2)} kg × {x.repeticiones} ({x.series} series)</li>)}</ul>
                    </>
                )) : null}
            </section>
            <Fotos />
        </div>
    );
}
