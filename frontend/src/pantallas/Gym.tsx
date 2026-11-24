import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { CampoTexto, Cargando, Modal, useApp, useDatos } from "../componentes";
import { DIAS_CORTOS, NOMBRES_DIAS, entradaNumero, numero, sumarDias, textoFecha, textoNumeroEntrada, uuid } from "../utilidades";

function claveBorrador(usuarioId: number, fecha: string, sesion: string): string {
    return `funesfit-borrador-${usuarioId}-${fecha}-${sesion}`;
}

function leerLocal(clave: string): any {
    try {
        const texto: string | null = localStorage.getItem(clave);
        return texto ? JSON.parse(texto) : null;
    } catch (error) {
        return null;
    }
}

function guardarLocal(clave: string, valor: any): void {
    try {
        if(valor == null){
            localStorage.removeItem(clave);
        }else{
            localStorage.setItem(clave, JSON.stringify(valor));
        }
    } catch (error) {
        console.log(`No se pudo guardar el borrador: ${error}`);
    }
}

function sesionInicial(actividad: any, fecha: string): any {
    const detalle: any = actividad.detalle;
    return {
        id_cliente: uuid(),
        fecha: fecha,
        sesion_codigo: actividad.sesion,
        semana_programa: detalle.semana_programa,
        estado: "en_curso",
        inicio: new Date().toISOString(),
        version_base: 0,
        notas: "",
        ejercicios: detalle.ejercicios.map((e: any) => {
            const ultimo: any = e.ultima ? e.ultima.series.filter((s: any) => s.completada) : [];
            const peso: any = ultimo.length ? ultimo[ultimo.length - 1].peso_kg : null;
            return {
                ejercicio_id: e.ejercicio_id,
                nombre: e.nombre,
                rep_min: e.rep_min,
                rep_max: e.rep_max,
                series_objetivo: e.objetivo.series,
                tecnica_ok: true,
                notas: "",
                series: Array.from({ length: e.objetivo.series }, () => ({ peso_kg: peso, repeticiones: null, completada: false, rir: null, descanso_s: null })),
            };
        }),
    };
}

function Temporizador(props: any): any {
    const [, setTic] = useState<number>(0);
    useEffect(() => {
        const intervalo: number = window.setInterval(() => setTic((t: number) => t + 1), 500);
        const visible = (): void => setTic((t: number) => t + 1);
        document.addEventListener("visibilitychange", visible);
        return () => {
            window.clearInterval(intervalo);
            document.removeEventListener("visibilitychange", visible);
        };
    }, []);
    if(!props.fin){
        return null;
    }
    const restante: number = Math.max(0, Math.round((props.fin - Date.now()) / 1000));
    if(restante == 0 && !props.avisado){
        props.alTerminar();
    }
    const m: number = Math.floor(restante / 60);
    const s: string = String(restante % 60).padStart(2, "0");
    return (
        <div className="temporizador" role="timer" aria-live="off">
            <span>Descanso {restante == 0 ? "terminado" : `${m}:${s}`}</span>
            <span className="fila">
                <button className="pequeno" onClick={() => props.alSumar(30)}>+30 s</button>
                <button className="pequeno" onClick={props.alParar}>Quitar</button>
            </span>
        </div>
    );
}

function EditorSesion(props: any): any {
    const { usuario, registrar, avisar } = useApp();
    const actividad: any = props.actividad;
    const detalle: any = actividad.detalle;
    const clave: string = claveBorrador(usuario.id, props.fecha, actividad.sesion);
    const [sesion, setSesion] = useState<any>(() => leerLocal(clave) || (actividad.sesion_registrada ? { ...actividad.sesion_registrada, version_base: actividad.sesion_registrada.version } : sesionInicial(actividad, props.fecha)));
    const [descanso, setDescanso] = useState<any>(() => leerLocal(`${clave}-descanso`));
    const [alternativas, setAlternativas] = useState<number | null>(null);
    const temporizadorGuardado = useRef<number | null>(null);

    const guardar = (nueva: any, inmediato: boolean = false): void => {
        guardarLocal(clave, nueva);
        if(temporizadorGuardado.current){
            window.clearTimeout(temporizadorGuardado.current);
        }
        const enviar = async (): Promise<void> => {
            try {
                await registrar("sesion.guardar", { ...nueva, rutina_id: props.rutinaId });
            } catch (e: any) {
                avisar(e.message, "rojo");
            }
        };
        if(inmediato){
            enviar();
        }else{
            temporizadorGuardado.current = window.setTimeout(enviar, 1500);
        }
    };

    const cambiar = (f: (s: any) => any): void => {
        setSesion((anterior: any) => {
            const nueva: any = f(JSON.parse(JSON.stringify(anterior)));
            guardar(nueva);
            return nueva;
        });
    };

    const serie = (i: number, j: number, campo: string, valor: any): void => {
        cambiar((s: any) => {
            s.ejercicios[i].series[j][campo] = valor;
            return s;
        });
    };

    const completar = (i: number, j: number): void => {
        const ejercicioDetalle: any = detalle.ejercicios.find((e: any) => e.ejercicio_id == sesion.ejercicios[i].ejercicio_id);
        const segundos: number = ejercicioDetalle && ejercicioDetalle.principal ? 150 : 75;
        cambiar((s: any) => {
            const marcada: boolean = !s.ejercicios[i].series[j].completada;
            s.ejercicios[i].series[j].completada = marcada;
            if(marcada){
                s.ejercicios[i].series[j].descanso_s = segundos;
            }
            return s;
        });
        if(!sesion.ejercicios[i].series[j].completada){
            const nuevo: any = { fin: Date.now() + segundos * 1000, avisado: false };
            setDescanso(nuevo);
            guardarLocal(`${clave}-descanso`, nuevo);
        }
    };

    const finalizar = (estado: string): void => {
        const nueva: any = { ...sesion, estado: estado, fin: new Date().toISOString() };
        setSesion(nueva);
        guardar(nueva, true);
        guardarLocal(clave, null);
        guardarLocal(`${clave}-descanso`, null);
        avisar(estado == "finalizada" ? "Sesión finalizada" : "Sesión guardada como parcial");
        props.alTerminar();
    };

    const mover = (i: number, delta: number): void => {
        cambiar((s: any) => {
            const destino: number = i + delta;
            if(destino < 0 || destino >= s.ejercicios.length){
                return s;
            }
            const [e] = s.ejercicios.splice(i, 1);
            s.ejercicios.splice(destino, 0, e);
            return s;
        });
    };

    const sustituir = (i: number, nombre: string): void => {
        cambiar((s: any) => {
            const original: any = s.ejercicios[i];
            s.ejercicios[i] = { ...original, sustituye_a: original.sustituye_a || original.nombre, nombre: nombre, series: original.series.map((x: any) => ({ ...x, peso_kg: null })) };
            return s;
        });
        setAlternativas(null);
    };

    return (
        <div>
            <Temporizador
                fin={descanso ? descanso.fin : null}
                avisado={descanso ? descanso.avisado : true}
                alTerminar={() => {
                    if(navigator.vibrate){
                        navigator.vibrate([200, 100, 200]);
                    }
                    const nuevo: any = { ...descanso, avisado: true };
                    setDescanso(nuevo);
                    guardarLocal(`${clave}-descanso`, nuevo);
                }}
                alSumar={(seg: number) => {
                    const nuevo: any = { fin: Math.max(Date.now(), descanso.fin) + seg * 1000, avisado: false };
                    setDescanso(nuevo);
                    guardarLocal(`${clave}-descanso`, nuevo);
                }}
                alParar={() => {
                    setDescanso(null);
                    guardarLocal(`${clave}-descanso`, null);
                }}
            />
            <div className="aviso">
                Semana {detalle.semana_programa} de {detalle.semanas_total}. {detalle.ejercicios[0] ? detalle.ejercicios[0].objetivo.nota : ""} {detalle.calentamiento}
            </div>
            {sesion.ejercicios.map((e: any, i: number) => {
                const info: any = detalle.ejercicios.find((x: any) => x.ejercicio_id == e.ejercicio_id) || {};
                return (
                    <section key={`${e.ejercicio_id}-${i}`} className="tarjeta">
                        <div className="fila separada">
                            <h3 style={{ margin: 0 }}>{e.nombre}</h3>
                            <span className="fila">
                                <button className="pequeno" aria-label="Subir" onClick={() => mover(i, -1)}>↑</button>
                                <button className="pequeno" aria-label="Bajar" onClick={() => mover(i, 1)}>↓</button>
                            </span>
                        </div>
                        {e.sustituye_a ? <p className="suave">Sustituye a {e.sustituye_a}</p> : null}
                        <p className="suave">
                            {info.objetivo ? `${info.objetivo.series_min != info.objetivo.series ? `${info.objetivo.series_min}–` : ""}${info.objetivo.series} series` : `${e.series_objetivo} series`}
                            {e.rep_min ? ` · ${e.rep_min}–${e.rep_max} reps` : info.tiempo ? ` · ${info.tiempo}` : ""}
                            {info.por_lado ? " por lado" : ""}
                            {info.objetivo ? ` · deja ${info.objetivo.rir_objetivo} en reserva` : ""}
                        </p>
                        {info.ultima ? <p className="suave">Última vez ({info.ultima.fecha}): {info.ultima.series.filter((s: any) => s.completada).map((s: any) => `${numero(s.peso_kg, 2)} kg × ${s.repeticiones}`).join(", ")}</p> : <p className="suave">Sin sesiones anteriores: elige una carga con técnica controlada.</p>}
                        {info.sugerencia && info.sugerencia.accion == "subir" ? (
                            <div className="aviso">
                                {info.sugerencia.mensaje}
                                <div><button className="pequeno" onClick={() => cambiar((s: any) => { s.ejercicios[i].series = s.ejercicios[i].series.map((x: any) => (x.completada ? x : { ...x, peso_kg: info.sugerencia.peso_sugerido })); return s; })}>Aceptar {numero(info.sugerencia.peso_sugerido, 2)} kg</button></div>
                            </div>
                        ) : info.sugerencia && info.sugerencia.accion != "sin_datos" ? <p className="suave">{info.sugerencia.mensaje}</p> : null}
                        <div className="serie suave" aria-hidden="true"><span>#</span><span>kg</span><span>reps</span><span>RIR</span><span>✓</span></div>
                        {e.series.map((s: any, j: number) => (
                            <div key={j} className="serie">
                                <span>{j + 1}</span>
                                <input inputMode="decimal" aria-label={`Peso serie ${j + 1}`} value={textoNumeroEntrada(s.peso_kg)} onChange={(ev: any) => serie(i, j, "peso_kg", entradaNumero(ev.target.value))} />
                                <input inputMode="numeric" aria-label={`Repeticiones serie ${j + 1}`} value={s.repeticiones ?? ""} onChange={(ev: any) => serie(i, j, "repeticiones", entradaNumero(ev.target.value))} />
                                <input inputMode="numeric" aria-label={`Repeticiones en reserva serie ${j + 1}`} value={s.rir ?? ""} onChange={(ev: any) => serie(i, j, "rir", entradaNumero(ev.target.value))} />
                                <input type="checkbox" aria-label={`Serie ${j + 1} completada`} checked={s.completada} onChange={() => completar(i, j)} />
                            </div>
                        ))}
                        <div className="fila">
                            <button className="pequeno" onClick={() => cambiar((s: any) => { const ultima: any = s.ejercicios[i].series[s.ejercicios[i].series.length - 1] || {}; s.ejercicios[i].series.push({ peso_kg: ultima.peso_kg ?? null, repeticiones: null, completada: false, rir: null, descanso_s: null }); return s; })}>+ Serie</button>
                            <button className="pequeno" disabled={e.series.length == 0} onClick={() => cambiar((s: any) => { s.ejercicios[i].series.pop(); return s; })}>− Serie</button>
                            <button className="pequeno" onClick={() => setAlternativas(i)}>Sustituir</button>
                            <label className="casilla" style={{ minHeight: 36 }}><input type="checkbox" checked={e.tecnica_ok != false} onChange={(ev: any) => cambiar((s: any) => { s.ejercicios[i].tecnica_ok = ev.target.checked; return s; })} /> Buena técnica</label>
                        </div>
                        <details>
                            <summary>Instrucciones y notas</summary>
                            {info.instrucciones ? <p>{info.instrucciones}</p> : null}
                            <CampoTexto etiqueta="Notas" valor={e.notas} alCambiar={(v: string) => cambiar((s: any) => { s.ejercicios[i].notas = v; return s; })} />
                        </details>
                        {alternativas == i ? (
                            <Modal titulo={`Alternativas a ${e.sustituye_a || e.nombre}`} alCerrar={() => setAlternativas(null)}>
                                <ul className="lista">
                                    {(info.alternativas || []).map((a: string) => <li key={a}><button onClick={() => sustituir(i, a)}>{a}</button></li>)}
                                </ul>
                                {(info.alternativas || []).length == 0 ? <p className="suave">No hay alternativas registradas.</p> : null}
                            </Modal>
                        ) : null}
                    </section>
                );
            })}
            <div className="tarjeta">
                <CampoTexto etiqueta="Notas de la sesión" valor={sesion.notas || ""} alCambiar={(v: string) => cambiar((s: any) => { s.notas = v; return s; })} />
                <p className="suave">{detalle.advertencia}</p>
                <div className="fila" style={{ marginTop: 8 }}>
                    <button className="primario" onClick={() => finalizar("finalizada")}>Finalizar sesión</button>
                    <button onClick={() => finalizar("parcial")}>Terminar a medias</button>
                    <button onClick={props.alTerminar}>Salir (se guarda)</button>
                </div>
            </div>
        </div>
    );
}

function RegistroEvento(props: any): any {
    const { registrar, avisar } = useApp();
    const a: any = props.actividad;
    const [datos, setDatos] = useState<any>({ duracion_min: a.datos.duracion_min ?? "", minutos_jugados: a.datos.minutos_jugados ?? "", esfuerzo: a.datos.esfuerzo ?? "", molestias: a.datos.molestias ?? "", notas: a.datos.notas ?? "" });
    const guardar = async (estado: string): Promise<void> => {
        try {
            await registrar("evento.guardar", { id_cliente: uuid(), clave_plan: a.clave_plan, fecha: props.fecha, tipo: a.tipo, titulo: a.titulo, estado: estado, datos: datos, version_base: a.version });
            avisar(estado == "realizado" ? "Registrado" : "Marcado como no realizado");
            props.alCerrar(true);
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo={`Registrar: ${a.titulo}`} alCerrar={() => props.alCerrar(false)}>
            <div className="columna">
                <div className="rejilla-2">
                    <CampoTexto etiqueta="Duración (min)" modo="numeric" valor={datos.duracion_min} alCambiar={(v: string) => setDatos({ ...datos, duracion_min: v })} />
                    {a.tipo == "partido" || a.tipo == "futbol" ? <CampoTexto etiqueta="Minutos jugados" modo="numeric" valor={datos.minutos_jugados} alCambiar={(v: string) => setDatos({ ...datos, minutos_jugados: v })} /> : null}
                </div>
                <label>Esfuerzo percibido (1–10): {datos.esfuerzo || "—"}<input type="range" min="1" max="10" value={datos.esfuerzo || 5} onChange={(e: any) => setDatos({ ...datos, esfuerzo: e.target.value })} /></label>
                <CampoTexto etiqueta="Molestias (opcional)" valor={datos.molestias} alCambiar={(v: string) => setDatos({ ...datos, molestias: v })} />
                <CampoTexto etiqueta="Notas" valor={datos.notas} alCambiar={(v: string) => setDatos({ ...datos, notas: v })} />
                <p className="suave">No se calculan calorías gastadas ni se suman a tu alimentación.</p>
                <div className="fila">
                    <button className="primario" onClick={() => guardar("realizado")}>Guardar como hecho</button>
                    <button onClick={() => guardar("omitido")}>No lo hice</button>
                </div>
            </div>
        </Modal>
    );
}

function Reprogramar(props: any): any {
    const { avisar } = useApp();
    const [fecha, setFecha] = useState<string>(props.fecha);
    const [hora, setHora] = useState<string>(props.actividad.hora || "");
    const guardar = async (omitir: boolean = false): Promise<void> => {
        try {
            await api.put(`/api/gym/plan/${props.actividad.clave_plan}`, { fecha: fecha, hora: hora || null, omitir: omitir });
            props.alCerrar(true);
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo={`Mover ${props.actividad.titulo}`} alCerrar={() => props.alCerrar(false)}>
            <div className="columna">
                <label>Día
                    <select value={fecha} onChange={(e: any) => setFecha(e.target.value)}>
                        {[-3, -2, -1, 0, 1, 2, 3].map((d: number) => { const f: string = sumarDias(props.fecha, d); return <option key={f} value={f}>{textoFecha(f)}</option>; })}
                    </select>
                </label>
                <CampoTexto etiqueta="Hora" tipo="time" valor={hora} alCambiar={setHora} />
                <p className="suave">Se mueve sin duplicarse. No hace falta recuperar sesiones perdidas.</p>
                <div className="fila">
                    <button className="primario" onClick={() => guardar(false)}>Guardar</button>
                    {props.actividad.opcional || props.actividad.tipo == "gimnasio" ? <button onClick={() => guardar(true)}>Omitir esta vez</button> : null}
                </div>
            </div>
        </Modal>
    );
}

function Partido(props: any): any {
    const { avisar } = useApp();
    const sabado: string = sumarDias(props.lunes, 5);
    const [fecha, setFecha] = useState<string>(sabado);
    const [hora, setHora] = useState<string>("");
    const guardar = async (sinPartido: boolean): Promise<void> => {
        try {
            await api.put("/api/eventos/partido", { fecha: fecha, hora: hora || null, sin_partido: sinPartido });
            avisar(sinPartido ? "Sin partido esta semana" : "Partido configurado");
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <div className="tarjeta">
            <h3>Partido de este fin de semana</h3>
            <div className="rejilla-2">
                <label>Día<select value={fecha} onChange={(e: any) => setFecha(e.target.value)}><option value={sabado}>Sábado {sabado.slice(8)}</option><option value={sumarDias(props.lunes, 6)}>Domingo {sumarDias(props.lunes, 6).slice(8)}</option></select></label>
                <CampoTexto etiqueta="Hora" tipo="time" valor={hora} alCambiar={setHora} />
            </div>
            <div className="fila" style={{ marginTop: 8 }}>
                <button onClick={() => guardar(false)}>Guardar partido</button>
                <button className="enlace" onClick={() => guardar(true)}>No hay partido</button>
            </div>
            <p className="suave">El otro día queda para descanso o recuperación.</p>
        </div>
    );
}

export default function Gym(): any {
    const { estadoSync } = useApp();
    const partes: string[] = window.location.hash.replace("#/gym", "").split("/").filter(Boolean);
    const [fecha, setFecha] = useState<string | null>(partes[0] || null);
    const semana: any = useDatos(`/api/gym/semana${fecha ? `?fecha=${fecha}` : ""}`);
    const fechaDia: string | null = fecha || (semana.datos ? semana.datos.hoy : null);
    const dia: any = useDatos(fechaDia ? `/api/gym/dia?fecha=${fechaDia}` : null);
    const rutina: any = useDatos("/api/gym/rutina");
    const [abierta, setAbierta] = useState<any>(null);
    const [evento, setEvento] = useState<any>(null);
    const [mover, setMover] = useState<any>(null);
    const [fatigaElegida, setFatigaElegida] = useState<any>({});

    if(!semana.datos || !dia.datos){
        return <Cargando error={semana.error || dia.error} />;
    }
    const recargar = (): void => {
        semana.recargar();
        dia.recargar();
    };
    if(abierta){
        return (
            <div>
                <div className="cabecera"><h1>{abierta.titulo}</h1>{estadoSync}</div>
                <EditorSesion actividad={abierta} fecha={dia.datos.fecha} rutinaId={rutina.datos && rutina.datos.rutina ? rutina.datos.rutina.id : null} alTerminar={() => { setAbierta(null); recargar(); }} />
            </div>
        );
    }
    const r: any = rutina.datos ? rutina.datos.rutina : null;
    const tieneFutbol: boolean = r ? Object.values(r.distribucion).some((l: any) => l.some((a: any) => a.tipo == "futbol")) : false;

    return (
        <div>
            <div className="cabecera">
                <div>
                    <h1>Entrenamiento</h1>
                    <p className="subtitulo">{r ? `${r.nombre} · versión ${r.version}` : ""}</p>
                </div>
                {estadoSync}
            </div>
            <div className="pestanas" role="tablist" aria-label="Días">
                <button aria-label="Semana anterior" onClick={() => setFecha(sumarDias(semana.datos.lunes, -7))}>←</button>
                {semana.datos.dias.map((d: any, i: number) => (
                    <button key={d.fecha} className={d.fecha == dia.datos.fecha ? "activa" : ""} onClick={() => setFecha(d.fecha)} aria-label={`${NOMBRES_DIAS[i]} ${d.fecha}`}>
                        {DIAS_CORTOS[i]} {Number(d.fecha.slice(8))}{d.actividades.length ? " ●" : ""}
                    </button>
                ))}
                <button aria-label="Semana siguiente" onClick={() => setFecha(sumarDias(semana.datos.lunes, 7))}>→</button>
            </div>
            <section className="tarjeta">
                <h2>{textoFecha(dia.datos.fecha)}{dia.datos.fecha == dia.datos.hoy ? " · hoy" : ""}</h2>
                {dia.datos.descanso ? <p>{dia.datos.texto_descanso}</p> : null}
                <ul className="lista">
                    {dia.datos.actividades.map((a: any) => (
                        <li key={a.clave_plan || a.evento_id}>
                            <div className="fila separada">
                                <div>
                                    <strong>{a.titulo}</strong>{a.hora ? ` · ${a.hora}` : ""}{a.reprogramada ? " · movida" : ""}{a.opcional ? " · opcional" : ""}
                                    <div className="suave">
                                        {a.tipo == "gimnasio" && a.detalle && a.detalle.ejercicios.length ? `${a.detalle.ejercicios.length} ejercicios · ${a.detalle.tiempo.texto}` : null}
                                        {a.estado == "realizado" ? " · hecho ✓" : a.estado == "omitido" ? " · no realizado" : ""}
                                        {a.sesion_registrada ? ` · ${a.sesion_registrada.estado == "en_curso" ? "en curso" : a.sesion_registrada.estado}` : ""}
                                    </div>
                                </div>
                            </div>
                            {a.detalle && a.detalle.opciones_fatiga && !fatigaElegida[a.clave_plan] ? (
                                <div className="aviso amarillo">
                                    {a.detalle.opciones_fatiga.mensaje}
                                    <div className="fila" style={{ marginTop: 6 }}>
                                        <button className="pequeno" onClick={() => setFatigaElegida({ ...fatigaElegida, [a.clave_plan]: "reducir" })}>Reducir</button>
                                        <button className="pequeno" onClick={async () => { await api.put(`/api/gym/plan/${a.clave_plan}`, { omitir: true }); recargar(); }}>Omitir hoy</button>
                                        <button className="pequeno" onClick={() => setFatigaElegida({ ...fatigaElegida, [a.clave_plan]: "normal" })}>Hacerla normal</button>
                                    </div>
                                </div>
                            ) : null}
                            {a.tipo == "gimnasio" && a.detalle && a.detalle.ejercicios.length == 0 ? <div className="aviso amarillo">Esta sesión aún no tiene ejercicios: falta importar el documento del plan. No se han inventado.</div> : null}
                            <div className="fila" style={{ marginTop: 6 }}>
                                {a.tipo == "gimnasio" && a.detalle && a.detalle.ejercicios.length > 0 && a.estado != "omitido" ? (
                                    <button className="primario" onClick={() => {
                                        if(fatigaElegida[a.clave_plan] == "reducir"){
                                            const reducida: any = { ...a, detalle: { ...a.detalle, ejercicios: a.detalle.ejercicios.map((e: any) => ({ ...e, objetivo: { ...e.objetivo, series: Math.max(1, e.objetivo.series - 1) } })) } };
                                            setAbierta(reducida);
                                        }else{
                                            setAbierta(a);
                                        }
                                    }}>{a.sesion_registrada ? (a.sesion_registrada.estado == "en_curso" ? "Continuar" : "Ver / editar") : "Empezar"}</button>
                                ) : null}
                                {a.tipo != "gimnasio" ? <button className="primario" onClick={() => setEvento(a)}>{a.estado == "realizado" ? "Editar registro" : "Registrar"}</button> : null}
                                {a.clave_plan && !a.clave_plan.startsWith("semana:") ? <button onClick={() => setMover(a)}>Mover</button> : null}
                            </div>
                        </li>
                    ))}
                </ul>
            </section>
            {tieneFutbol ? <Partido lunes={semana.datos.lunes} alCambiar={recargar} /> : null}
            {r ? (
                <details className="tarjeta">
                    <summary><strong>Rutina y distribución</strong></summary>
                    {r.avisos.map((t: string) => <p key={t} className="suave">{t}</p>)}
                    {Object.keys(r.sesiones).length == 0 ? <p className="aviso amarillo">Pendiente de importar los ejercicios del documento del plan.</p> : null}
                    {Object.entries(r.sesiones).map(([codigo, lista]: any) => (
                        <div key={codigo}>
                            <h3>{r.nombres_sesion[codigo] || codigo}</h3>
                            <table className="tabla">
                                <tbody>{lista.map((e: any) => <tr key={e.id}><td>{e.nombre}</td><td className="num">{e.series} × {e.rep_min ? `${e.rep_min}–${e.rep_max}` : e.tiempo}{e.por_lado ? " por lado" : ""}</td></tr>)}</tbody>
                            </table>
                        </div>
                    ))}
                    <p className="suave">Series de trabajo, sin contar el calentamiento. La progresión depende de tus registros y la aceptas tú.</p>
                </details>
            ) : null}
            {evento ? <RegistroEvento actividad={evento} fecha={dia.datos.fecha} alCerrar={(ok: boolean) => { setEvento(null); if(ok){ recargar(); } }} /> : null}
            {mover ? <Reprogramar actividad={mover} fecha={dia.datos.fecha} alCerrar={(ok: boolean) => { setMover(null); if(ok){ recargar(); } }} /> : null}
        </div>
    );
}
