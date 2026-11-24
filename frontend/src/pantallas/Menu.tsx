import { useEffect, useState } from "react";
import { api } from "../api";
import { CampoTexto, Cargando, Modal, Nutrientes, useApp, useDatos } from "../componentes";
import { DIAS_CORTOS, MOMENTOS, euros, fechaCorta, lunesDe, numero, sumarDias, textoFecha } from "../utilidades";
import Receta, { EditorReceta } from "./Receta";
import RegistroComida, { marcarComoPrevisto, textoEstado } from "./RegistroComida";

function Equivalentes(props: any): any {
    const { avisar } = useApp();
    const { datos, error } = useDatos(`/api/menu/comidas/${props.comida.id}/equivalentes`);
    const elegir = async (o: any): Promise<void> => {
        try {
            await api.patch(`/api/menu/comidas/${props.comida.id}`, { receta_id: o.receta.id, factor: o.factor });
            avisar("Comida sustituida. La compra se ha recalculado.");
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo={`Sustituir ${props.comida.receta_nombre}`} alCerrar={props.alCerrar}>
            {!datos ? <Cargando error={error} /> : (
                <>
                    <p className="suave">Opciones con energía parecida (±12 %) y proteína similar, sin tus alimentos excluidos.</p>
                    {datos.opciones.length == 0 ? <p>No hay recetas equivalentes. Crea una en Mis recetas.</p> : null}
                    <ul className="lista">
                        {datos.opciones.map((o: any) => (
                            <li key={o.receta.id} className="fila separada">
                                <div>
                                    <strong>{o.receta.nombre}</strong>{o.factor != 1 ? ` × ${numero(o.factor, 2)}` : ""}
                                    <div className="suave">{Math.round(o.kcal)} kcal · {Math.round(o.proteina)} g proteína</div>
                                </div>
                                <button onClick={() => elegir(o)}>Elegir</button>
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </Modal>
    );
}

function EditarComida(props: any): any {
    const { avisar } = useApp();
    const c: any = props.comida;
    const [hora, setHora] = useState<string>(c.hora || "");
    const [fecha, setFecha] = useState<string>(c.fecha);
    const [momento, setMomento] = useState<string>(c.momento);
    const [factor, setFactor] = useState<string>(String(c.factor).replace(".", ","));
    const guardar = async (): Promise<void> => {
        try {
            await api.patch(`/api/menu/comidas/${c.id}`, { hora: hora || null, fecha: fecha, momento: momento, factor: factor });
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Mover o cambiar hora" alCerrar={props.alCerrar}>
            <div className="columna">
                <CampoTexto etiqueta="Hora" tipo="time" valor={hora} alCambiar={setHora} />
                <label>Día
                    <select value={fecha} onChange={(e: any) => setFecha(e.target.value)}>
                        {[0, 1, 2, 3, 4, 5, 6].map((d: number) => {
                            const f: string = sumarDias(props.lunes, d);
                            return <option key={f} value={f}>{textoFecha(f)}</option>;
                        })}
                    </select>
                </label>
                <label>Momento
                    <select value={momento} onChange={(e: any) => setMomento(e.target.value)}>
                        {Object.keys(MOMENTOS).map((m: string) => <option key={m} value={m}>{MOMENTOS[m]}</option>)}
                    </select>
                </label>
                <CampoTexto etiqueta="Raciones (1 = ración normal)" modo="decimal" valor={factor} alCambiar={setFactor} />
                <button className="primario" onClick={guardar}>Guardar</button>
            </div>
        </Modal>
    );
}

function Ajuste(props: any): any {
    const { avisar } = useApp();
    const [kcal, setKcal] = useState<string>(props.objetivo ? String(Math.round(props.objetivo.kcal)) : "");
    const [propuesta, setPropuesta] = useState<any>(null);
    const calcular = async (): Promise<void> => {
        try {
            setPropuesta(await api.post(`/api/menu/${props.planId}/ajuste/propuesta`, { kcal_objetivo: kcal }));
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const aplicar = async (): Promise<void> => {
        try {
            const r: any = await api.post(`/api/menu/${props.planId}/ajuste/aplicar`, { kcal_objetivo: kcal });
            avisar(`Raciones ajustadas en ${r.comidas_ajustadas} comidas. La compra se ha recalculado.`);
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Ajustar raciones a un objetivo" alCerrar={props.alCerrar}>
            <p className="suave">Escala comida y cena para acercarse a las kcal indicadas. No cambia nada hasta que pulses Aplicar, y no toca días pasados.</p>
            <CampoTexto etiqueta="kcal por día" modo="numeric" valor={kcal} alCambiar={setKcal} />
            <button onClick={calcular} style={{ marginTop: 8 }}>Ver propuesta</button>
            {propuesta ? (
                <>
                    <table className="tabla">
                        <thead><tr><th>Día</th><th className="num">Ahora</th><th className="num">Propuesta</th><th className="num">Factor</th></tr></thead>
                        <tbody>
                            {propuesta.dias.map((d: any) => (
                                <tr key={d.fecha}><td>{fechaCorta(d.fecha)}</td><td className="num">{Math.round(d.kcal_actual)}</td><td className="num">{Math.round(d.kcal_propuesta)}</td><td className="num">×{numero(d.factor, 2)}{d.limitado ? " (límite)" : ""}</td></tr>
                            ))}
                        </tbody>
                    </table>
                    <p className="suave">{propuesta.nota}</p>
                    <button className="primario" onClick={aplicar}>Aplicar</button>
                </>
            ) : null}
        </Modal>
    );
}

function Abaratar(props: any): any {
    const { avisar } = useApp();
    const { datos, error } = useDatos(`/api/menu/${props.planId}/abaratar`);
    const [elegidas, setElegidas] = useState<Set<number>>(new Set());
    const aplicar = async (): Promise<void> => {
        const cambios: any[] = datos.propuestas.filter((p: any) => elegidas.has(p.comida_id)).map((p: any) => ({ comida_id: p.comida_id, receta_id: p.propuesta.receta_id, factor: p.propuesta.factor }));
        try {
            await api.post(`/api/menu/${props.planId}/abaratar/aplicar`, { cambios: cambios });
            avisar("Cambios aplicados");
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Abaratar la semana" alCerrar={props.alCerrar}>
            {!datos ? <Cargando error={error} /> : (
                <>
                    <p className="suave">{datos.aviso}</p>
                    {datos.recetas_sin_precios.length ? <div className="aviso amarillo">Faltan precios de ingredientes de: {datos.recetas_sin_precios.join(", ")}. Añádelos en Compra para poder comparar.</div> : null}
                    <ul className="lista">
                        {datos.propuestas.map((p: any) => (
                            <li key={p.comida_id}>
                                <label className="casilla">
                                    <input type="checkbox" checked={elegidas.has(p.comida_id)} onChange={() => { const s: Set<number> = new Set(elegidas); s.has(p.comida_id) ? s.delete(p.comida_id) : s.add(p.comida_id); setElegidas(s); }} />
                                    <span>{fechaCorta(p.fecha)} {MOMENTOS[p.momento]}: {p.actual} → <strong>{p.propuesta.nombre}</strong> (ahorro aprox. {euros(p.ahorro)})</span>
                                </label>
                            </li>
                        ))}
                    </ul>
                    {datos.propuestas.length ? <button className="primario" disabled={elegidas.size == 0} onClick={aplicar}>Aceptar seleccionadas</button> : <p>No hay sustituciones más baratas con los precios disponibles.</p>}
                </>
            )}
        </Modal>
    );
}

function Tandas(props: any): any {
    const { datos, error } = useDatos(`/api/menu/${props.planId}/tandas`);
    return (
        <Modal titulo="Cocinar en dos tandas" alCerrar={props.alCerrar}>
            {!datos ? <Cargando error={error} /> : (
                <>
                    {datos.tandas.map((t: any) => (
                        <div key={t.fecha} className="tarjeta">
                            <h3>{t.nombre}: {textoFecha(t.fecha)}</h3>
                            {t.recetas.length == 0 ? <p className="suave">Nada que adelantar.</p> : null}
                            {t.recetas.map((r: any) => (
                                <div key={r.receta}>
                                    <strong>{r.receta}</strong> · {numero(r.raciones, 2)} raciones
                                    <ul>{r.usos.map((u: any, i: number) => <li key={i}>{fechaCorta(u.fecha)} {MOMENTOS[u.momento]}: {u.conservar}</li>)}</ul>
                                </div>
                            ))}
                        </div>
                    ))}
                    <h3>Al momento</h3>
                    <p className="suave">{datos.al_momento.map((a: any) => `${fechaCorta(a.fecha)} ${a.receta}`).filter((v: string, i: number, l: string[]) => l.indexOf(v) == i).length} preparaciones rápidas (desayunos, meriendas, ensaladas, tortillas, pescado).</p>
                    <h3>Normas de conservación</h3>
                    <ul>{datos.normas.map((n: string) => <li key={n}>{n}</li>)}</ul>
                </>
            )}
        </Modal>
    );
}

function MisRecetas(props: any): any {
    const { datos, error, recargar } = useDatos("/api/recetas");
    const [abierta, setAbierta] = useState<number | null>(null);
    const [nueva, setNueva] = useState<boolean>(false);
    return (
        <div>
            <div className="cabecera">
                <h1>Mis recetas</h1>
                <a className="boton" href="#/menu">Volver</a>
            </div>
            <button className="primario" onClick={() => setNueva(true)} style={{ marginBottom: 12 }}>+ Nueva receta</button>
            {!datos ? <Cargando error={error} /> : (
                <ul className="lista tarjeta">
                    {datos.recetas.map((r: any) => (
                        <li key={r.id} className="fila separada">
                            <div>
                                <strong>{r.favorita ? "★ " : ""}{r.nombre}</strong>
                                <div><Nutrientes n={r.nutrientes_racion} /></div>
                            </div>
                            <button onClick={() => setAbierta(r.id)}>Ver</button>
                        </li>
                    ))}
                </ul>
            )}
            {abierta ? <Receta id={abierta} alCerrar={() => setAbierta(null)} alCambiar={recargar} /> : null}
            {nueva ? <EditorReceta alCerrar={() => setNueva(false)} alGuardar={() => { setNueva(false); recargar(); }} /> : null}
            {props.children}
        </div>
    );
}

export default function Menu(): any {
    const { registrar, avisar, estadoSync } = useApp();
    const [fecha, setFecha] = useState<string | null>(null);
    const ruta: string = window.location.hash;
    const { datos, error, recargar } = useDatos(`/api/menu/semana${fecha ? `?fecha=${fecha}` : ""}`);
    const [dia, setDia] = useState<number | null>(null);
    const [receta, setReceta] = useState<number | null>(null);
    const [dialogo, setDialogo] = useState<any>(null);

    useEffect(() => {
        if(datos && dia == null){
            const hoy: string = datos.hoy;
            const indice: number = Math.round((new Date(hoy).getTime() - new Date(datos.lunes).getTime()) / 86400000);
            setDia(indice >= 0 && indice < 7 ? indice : 0);
        }
    }, [datos]);

    if(ruta.startsWith("#/menu/recetas")){
        return <MisRecetas />;
    }
    if(!datos){
        return <Cargando error={error} />;
    }

    const cambiarSemana = (dias: number): void => {
        setFecha(sumarDias(datos.lunes, dias));
        setDia(0);
    };

    const generar = async (modo: string): Promise<void> => {
        try {
            await api.post("/api/menu/semana/generar", { lunes: datos.lunes, modo: modo });
            avisar(modo == "repetir" ? "Semana creada como repetición programada" : "Semana creada variando platos");
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    const cerrar = (): void => {
        setDialogo(null);
        recargar();
    };

    const diaActual: any = datos.dias ? datos.dias[dia ?? 0] : null;

    return (
        <div>
            <div className="cabecera">
                <div>
                    <h1>Menú</h1>
                    <p className="subtitulo">Semana del {textoFecha(datos.lunes)}{datos.plan && datos.plan.origen == "repeticion_programada" ? " · repetición programada" : ""}{datos.plan && datos.plan.origen == "propuesta" ? " · propuesta" : ""}</p>
                </div>
                {estadoSync}
            </div>
            <div className="fila no-imprimir" style={{ marginBottom: 10 }}>
                <button onClick={() => cambiarSemana(-7)} aria-label="Semana anterior">←</button>
                <button onClick={() => { setFecha(datos.hoy); setDia(null); }}>Hoy</button>
                <button onClick={() => cambiarSemana(7)} aria-label="Semana siguiente">→</button>
                <a className="boton" href="#/menu/recetas">Mis recetas</a>
            </div>
            {!datos.plan ? (
                <div className="tarjeta">
                    <h2>Sin menú esta semana</h2>
                    {datos.puede_repetir_desde ? (
                        <div className="fila">
                            <button className="primario" onClick={() => generar("repetir")}>Repetir la semana anterior</button>
                            <button onClick={() => generar("variar")}>Repetir variando platos</button>
                        </div>
                    ) : <p className="suave">No hay ninguna semana anterior que usar como plantilla.</p>}
                </div>
            ) : (
                <>
                    {datos.plan_aceptado == false ? <div className="aviso">Este menú es una propuesta: confírmalo en tu perfil cuando lo hayas revisado.</div> : null}
                    <div className="pestanas no-imprimir" role="tablist" aria-label="Días">
                        {datos.dias.map((d: any, i: number) => (
                            <button key={d.fecha} role="tab" aria-selected={i == dia} className={i == dia ? "activa" : ""} onClick={() => setDia(i)}>
                                {DIAS_CORTOS[i]} {new Date(d.fecha).getDate()}{d.fecha == datos.hoy ? " •" : ""}
                            </button>
                        ))}
                    </div>
                    {datos.dias.map((d: any, i: number) => (
                        <section key={d.fecha} className={`tarjeta ${i == dia ? "" : "solo-impresion"}`}>
                            <h2>{textoFecha(d.fecha)}</h2>
                            <p><Nutrientes n={d.planificado} /> previstas{d.objetivo ? ` · objetivo ${d.objetivo.provisional ? "provisional " : ""}${Math.round(d.objetivo.kcal)} kcal` : ""}</p>
                            <ul className="lista">
                                {d.comidas.map((c: any) => (
                                    <li key={c.id}>
                                        <div className="suave">{MOMENTOS[c.momento]}{c.hora ? ` · ${c.hora}` : ""}{c.opcional ? " · opcional" : ""}{c.factor != 1 ? ` · ×${numero(c.factor, 2)}` : ""}</div>
                                        <button className="enlace" style={{ padding: 0, fontWeight: 600, textAlign: "left" }} onClick={() => setReceta(c.receta_id)}>{c.receta_nombre}</button>
                                        <div><Nutrientes n={c.nutrientes} /></div>
                                        <div className="fila no-imprimir" style={{ marginTop: 6 }}>
                                            {c.estado == "pendiente" ? <button className="pequeno primario" onClick={async () => { await marcarComoPrevisto(registrar, c); recargar(); }}>Comido ✓</button> : <span className="etiqueta ok">{textoEstado(c.estado)}</span>}
                                            <button className="pequeno" onClick={() => setDialogo({ tipo: "registro", comida: c })}>Registrar otra cosa</button>
                                            <button className="pequeno" onClick={() => setDialogo({ tipo: "sustituir", comida: c })}>Sustituir</button>
                                            <button className="pequeno" onClick={() => setDialogo({ tipo: "editar", comida: c })}>Mover/hora</button>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    ))}
                    {diaActual && diaActual.objetivo ? null : null}
                    <div className="tarjeta no-imprimir">
                        <h2>Semana</h2>
                        <p><Nutrientes n={datos.media_diaria_planificada} /> de media al día</p>
                        <div className="fila">
                            <button onClick={() => setDialogo({ tipo: "ajuste" })}>Ajustar raciones</button>
                            <button onClick={() => setDialogo({ tipo: "abaratar" })}>Abaratar semana</button>
                            <button onClick={() => setDialogo({ tipo: "tandas" })}>Cocinar en tandas</button>
                            <button onClick={() => window.print()}>Imprimir / PDF</button>
                        </div>
                        {datos.cambios && datos.cambios.length ? (
                            <details style={{ marginTop: 8 }}>
                                <summary>Historial de cambios (versión {datos.plan.version})</summary>
                                <ul>{datos.cambios.map((c: any) => <li key={c.version}>v{c.version}: {c.descripcion} · {new Date(c.momento).toLocaleString("es-ES")}</li>)}</ul>
                            </details>
                        ) : null}
                    </div>
                </>
            )}
            {receta ? <Receta id={receta} alCerrar={() => setReceta(null)} alCambiar={recargar} /> : null}
            {dialogo && dialogo.tipo == "registro" ? <RegistroComida comida={dialogo.comida} alCerrar={() => setDialogo(null)} alGuardar={cerrar} /> : null}
            {dialogo && dialogo.tipo == "sustituir" ? <Equivalentes comida={dialogo.comida} alCerrar={() => setDialogo(null)} alCambiar={cerrar} /> : null}
            {dialogo && dialogo.tipo == "editar" ? <EditarComida comida={dialogo.comida} lunes={datos.lunes} alCerrar={() => setDialogo(null)} alCambiar={cerrar} /> : null}
            {dialogo && dialogo.tipo == "ajuste" ? <Ajuste planId={datos.plan.id} objetivo={datos.dias[0].objetivo} alCerrar={() => setDialogo(null)} alCambiar={cerrar} /> : null}
            {dialogo && dialogo.tipo == "abaratar" ? <Abaratar planId={datos.plan.id} alCerrar={() => setDialogo(null)} alCambiar={cerrar} /> : null}
            {dialogo && dialogo.tipo == "tandas" ? <Tandas planId={datos.plan.id} alCerrar={() => setDialogo(null)} /> : null}
        </div>
    );
}

export { lunesDe };
