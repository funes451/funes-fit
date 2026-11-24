import { useEffect, useState } from "react";
import { api, descargar } from "../api";
import { CampoTexto, Cargando, Selector, useApp, useDatos } from "../componentes";
import { activarPush, cola, compatibilidadPush, desactivarPush } from "../dispositivo";
import { DIAS_CORTOS, euros, numero } from "../utilidades";

const CONTINUIDAD: any[] = [
    { valor: "continuo", texto: "Entreno de forma continua" },
    { valor: "menos_de_1_mes", texto: "Parado menos de 1 mes" },
    { valor: "1_a_3_meses", texto: "Parado 1–3 meses" },
    { valor: "mas_de_3_meses", texto: "Parado más de 3 meses" },
    { valor: "mas_de_6_meses", texto: "Parado más de 6 meses" },
];
const TIPOS_AVISO: any = { comida: "Comida", gimnasio: "Gimnasio", compra: "Compra", registro: "Registro del día" };

function Seccion(props: any): any {
    return (
        <details className="tarjeta" open={props.abierta}>
            <summary><strong>{props.titulo}</strong></summary>
            <div style={{ marginTop: 10 }}>{props.children}</div>
        </details>
    );
}

function ConfirmarPlan(props: any): any {
    const { avisar, recargarPerfil } = useApp();
    const p: any = props.perfil;
    const [f, setF] = useState<any>({
        nombre: p.nombre == "Amigo de Funes" ? "" : p.nombre,
        inicio_plan: "",
        edad_referencia: p.edad_referencia ?? "",
        sexo_formula: p.sexo_formula ?? "",
        altura_cm: p.altura_cm ? String(p.altura_cm).replace(".", ",") : "",
        peso_referencia_kg: p.peso_referencia_kg ? String(p.peso_referencia_kg).replace(".", ",") : "",
        alergias: "",
        excluidos: "",
        molestias_actuales: "",
        actividad_cotidiana: "",
        presupuesto_semanal: "",
        desayuno: "", comida: "", merienda: "", cena: "", gimnasio: "",
    });
    const confirmar = async (): Promise<void> => {
        if(!f.nombre || !f.inicio_plan){
            avisar("Indica al menos tu nombre y la fecha de inicio", "amarillo");
            return;
        }
        try {
            await api.post("/api/perfil/confirmar-plan", {
                nombre: f.nombre,
                inicio_plan: f.inicio_plan,
                edad_referencia: f.edad_referencia,
                sexo_formula: f.sexo_formula || null,
                altura_cm: f.altura_cm,
                peso_referencia_kg: f.peso_referencia_kg,
                alergias: f.alergias,
                alimentos_excluidos: f.excluidos.split(",").map((x: string) => x.trim()).filter(Boolean),
                molestias_actuales: f.molestias_actuales,
                actividad_cotidiana: f.actividad_cotidiana,
                presupuesto_semanal: f.presupuesto_semanal,
                presupuesto_confirmado: f.presupuesto_semanal != "",
                horarios: { desayuno: f.desayuno, comida: f.comida, merienda: f.merienda, cena: f.cena, gimnasio: f.gimnasio },
            });
            avisar("Plan confirmado. Tu menú y tu rutina empiezan en la fecha indicada.");
            await recargarPerfil();
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const c = (clave: string) => (v: string) => setF({ ...f, [clave]: v });
    return (
        <section className="tarjeta">
            <h2>Revisa y confirma tu plan</h2>
            <p className="suave">Estos datos vienen del documento de tu plan y están pendientes de que los confirmes. Corrige lo que no sea correcto. {p.objetivo_descripcion}</p>
            <div className="columna">
                <CampoTexto etiqueta="Tu nombre" valor={f.nombre} alCambiar={c("nombre")} />
                <CampoTexto etiqueta="Fecha en la que empiezas" tipo="date" valor={f.inicio_plan} alCambiar={c("inicio_plan")} />
                <div className="rejilla-2">
                    <CampoTexto etiqueta="Edad" modo="numeric" valor={f.edad_referencia} alCambiar={c("edad_referencia")} />
                    <Selector etiqueta="Sexo para la fórmula" valor={f.sexo_formula} alCambiar={c("sexo_formula")} vacio="Sin indicar" opciones={[{ valor: "masculino", texto: "Masculino" }, { valor: "femenino", texto: "Femenino" }]} />
                    <CampoTexto etiqueta="Altura (cm)" modo="decimal" valor={f.altura_cm} alCambiar={c("altura_cm")} />
                    <CampoTexto etiqueta="Peso de referencia (kg)" modo="decimal" valor={f.peso_referencia_kg} alCambiar={c("peso_referencia_kg")} />
                </div>
                <p className="suave">El peso de referencia no se guarda como medición. Cuando te peses, regístralo en Progreso con su fecha.</p>
                <CampoTexto etiqueta="Alergias o intolerancias" valor={f.alergias} alCambiar={c("alergias")} ejemplo="Escribe «ninguna» si no tienes" />
                <CampoTexto etiqueta="Alimentos que no te gustan (separados por comas)" valor={f.excluidos} alCambiar={c("excluidos")} />
                <CampoTexto etiqueta="¿Tienes alguna molestia o lesión ahora mismo?" valor={f.molestias_actuales} alCambiar={c("molestias_actuales")} ejemplo="Déjalo vacío si no" />
                <CampoTexto etiqueta="Actividad diaria fuera del deporte" valor={f.actividad_cotidiana} alCambiar={c("actividad_cotidiana")} ejemplo="Trabajo, estudios, pasos…" />
                <CampoTexto etiqueta="Presupuesto semanal de comida (€)" modo="decimal" valor={f.presupuesto_semanal} alCambiar={c("presupuesto_semanal")} />
                <div className="rejilla-3">
                    {["desayuno", "comida", "merienda", "cena", "gimnasio"].map((m: string) => <CampoTexto key={m} etiqueta={`Hora ${m}`} tipo="time" valor={f[m]} alCambiar={c(m)} />)}
                </div>
                <button className="primario" onClick={confirmar}>Confirmar mi plan</button>
            </div>
        </section>
    );
}

function FormularioInicial(props: any): any {
    const { avisar, recargarPerfil } = useApp();
    const p: any = props.perfil;
    const [f, setF] = useState<any>({
        sexo_formula: p.sexo_formula ?? "",
        nivel_actividad: p.nivel_actividad ?? "",
        pasos_habituales: p.pasos_habituales ?? "",
        presupuesto_semanal: p.presupuesto_semanal ?? "",
        presupuesto_confirmado: p.presupuesto_confirmado,
        equipo_gimnasio: p.equipo_gimnasio ?? "",
        continuidad_entrenamiento: p.continuidad_entrenamiento ?? "",
        cargas_conocidas: p.cargas_conocidas ?? "",
        horarios: { ...p.horarios },
    });
    const guardar = async (): Promise<void> => {
        try {
            await api.put("/api/perfil", { ...f, sexo_formula: f.sexo_formula || null, nivel_actividad: f.nivel_actividad || null, continuidad_entrenamiento: f.continuidad_entrenamiento || null, version: p.version });
            avisar("Datos guardados");
            await recargarPerfil();
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <div className="columna">
            <p className="suave">Solo lo que falta. Puedes dejar cualquier campo para más tarde.</p>
            <Selector etiqueta="Sexo usado en la fórmula energética" valor={f.sexo_formula} alCambiar={(v: string) => setF({ ...f, sexo_formula: v })} vacio="Sin indicar" opciones={[{ valor: "masculino", texto: "Masculino" }, { valor: "femenino", texto: "Femenino" }]} />
            <Selector etiqueta="Actividad fuera del gimnasio" valor={f.nivel_actividad} alCambiar={(v: string) => setF({ ...f, nivel_actividad: v })} vacio="Sin indicar" opciones={Object.entries(props.niveles).map(([k, v]: any) => ({ valor: k, texto: `${v.etiqueta} (×${numero(v.minimo, 2)}–${numero(v.maximo, 2)})` }))} />
            <CampoTexto etiqueta="Pasos habituales al día (media)" modo="numeric" valor={f.pasos_habituales} alCambiar={(v: string) => setF({ ...f, pasos_habituales: v })} />
            <div className="rejilla-2">
                <CampoTexto etiqueta="Presupuesto semanal (€)" modo="decimal" valor={f.presupuesto_semanal} alCambiar={(v: string) => setF({ ...f, presupuesto_semanal: v })} />
                <label className="casilla"><input type="checkbox" checked={f.presupuesto_confirmado} onChange={(e: any) => setF({ ...f, presupuesto_confirmado: e.target.checked })} /> Confirmado</label>
            </div>
            <div className="rejilla-3">
                {["desayuno", "comida", "merienda", "cena", "gimnasio"].map((m: string) => <CampoTexto key={m} etiqueta={`Hora ${m}`} tipo="time" valor={f.horarios[m] || ""} alCambiar={(v: string) => setF({ ...f, horarios: { ...f.horarios, [m]: v } })} />)}
            </div>
            <CampoTexto etiqueta="Equipo de tu gimnasio (máquinas que hay o faltan)" valor={f.equipo_gimnasio} alCambiar={(v: string) => setF({ ...f, equipo_gimnasio: v })} />
            <Selector etiqueta="Continuidad reciente del entrenamiento" valor={f.continuidad_entrenamiento} alCambiar={(v: string) => setF({ ...f, continuidad_entrenamiento: v })} vacio="Sin indicar" opciones={CONTINUIDAD} />
            <CampoTexto etiqueta="Cargas actuales que conozcas (opcional)" valor={f.cargas_conocidas} alCambiar={(v: string) => setF({ ...f, cargas_conocidas: v })} ejemplo="Ej.: prensa 120 kg × 10" />
            <button className="primario" onClick={guardar}>Guardar</button>
        </div>
    );
}

function Energia(props: any): any {
    const { avisar } = useApp();
    const e: any = props.energia;
    const objetivo: any = props.objetivo;
    const crear = async (): Promise<void> => {
        if(!window.confirm(`Se creará un objetivo de ${e.propuesta.kcal} kcal/día vigente desde hoy. El historial no cambia. ¿Continuar?`)){
            return;
        }
        try {
            await api.post("/api/objetivos", { kcal: e.propuesta.kcal, proteina_g: objetivo ? objetivo.proteina_g : null, origen: "propuesta_aceptada", nota: "Estimación Mifflin–St Jeor × factor de actividad con déficit moderado" });
            avisar("Objetivo creado. Ajusta las raciones del menú desde Menú → Ajustar raciones.");
            props.alCambiar();
        } catch (er: any) {
            avisar(er.message, "rojo");
        }
    };
    return (
        <div>
            <p>{e.formula}</p>
            {e.reposo_por_sexo ? <p>Metabolismo en reposo estimado: {Math.round(e.reposo_por_sexo.masculino)} kcal (fórmula masculina) · {Math.round(e.reposo_por_sexo.femenino)} kcal (femenina), con {numero(e.peso_usado.kg, 1)} kg, {e.edad_usada} años.</p> : null}
            <div className="aviso amarillo">{e.aviso}</div>
            {e.faltan && e.faltan.length ? <p className="suave">Para estimar el gasto falta: {e.faltan.join(", ")}.</p> : null}
            {e.gasto ? <p>Gasto estimado: {Math.round(e.gasto.minimo)}–{Math.round(e.gasto.maximo)} kcal/día (factor {numero(e.gasto.factor_minimo, 2)}–{numero(e.gasto.factor_maximo, 2)}). Es una hipótesis.</p> : null}
            {e.propuesta ? <p>Propuesta con déficit moderado: <strong>{e.propuesta.kcal} kcal/día</strong> (déficit entre {Math.round(e.propuesta.deficit_rango[0])} y {Math.round(e.propuesta.deficit_rango[1])} kcal según el factor real). {e.propuesta.explicacion}</p> : null}
            {e.plantilla ? <div className="aviso">Plantilla del menú (≈{Math.round(e.plantilla.kcal_plantilla)} kcal): déficit estimado {Math.round(e.plantilla.deficit_rango[0])}–{Math.round(e.plantilla.deficit_rango[1])} kcal. {e.plantilla.mensaje}</div> : null}
            {e.propuesta && props.modo == "perder" ? <button onClick={crear}>Usar esta propuesta como objetivo</button> : null}
            <p className="suave">Las calorías que estime un reloj o una máquina no se suman a tu alimentación. Si quieres personalizar el plan, una revisión con un médico o dietista-nutricionista es una buena idea.</p>
        </div>
    );
}

function Avisos(): any {
    const { avisar, recargarPerfil, perfil } = useApp();
    const { datos, recargar } = useDatos("/api/avisos");
    const compat: any = compatibilidadPush();
    const [silencio, setSilencio] = useState<any>(null);
    useEffect(() => {
        if(datos){
            setSilencio(datos.silencio);
        }
    }, [datos]);
    if(!datos){
        return <Cargando />;
    }
    const cambiar = async (r: any, cambios: any): Promise<void> => {
        try {
            await api.put(`/api/avisos/recordatorios/${r.id}`, cambios);
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const activar = async (): Promise<void> => {
        try {
            await activarPush(datos.clave_publica);
            avisar("Este dispositivo recibirá tus avisos");
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <div className="columna">
            {!datos.push_configurado ? <div className="aviso amarillo">El servidor no tiene claves de avisos (VAPID). Hay que generarlas con «python -m app.cli generar-vapid»; mientras tanto usa el calendario.</div> : null}
            {compat.motivo ? <div className="aviso amarillo">{compat.motivo}</div> : null}
            <p className="suave">{datos.aviso} Dispositivos suscritos: {datos.suscripciones}. Permiso: {compat.permiso == "granted" ? "concedido" : compat.permiso == "denied" ? "denegado (cámbialo en los ajustes del navegador)" : "sin pedir"}.</p>
            <div className="fila">
                <button className="primario" disabled={!datos.push_configurado || !compat.soporta} onClick={activar}>Activar en este dispositivo</button>
                <button onClick={async () => { await desactivarPush(); recargar(); }}>Desactivar aquí</button>
                <button disabled={!datos.push_configurado} onClick={async () => { try { const r: any = await api.post("/api/avisos/prueba"); avisar(`Prueba enviada a ${r.enviados} dispositivo(s). Que llegue depende del navegador.`); } catch (e: any) { avisar(e.message, "rojo"); } }}>Enviar prueba</button>
            </div>
            <ul className="lista">
                {datos.recordatorios.map((r: any) => (
                    <li key={r.id} className="columna">
                        <div className="fila separada">
                            <label className="casilla"><input type="checkbox" checked={r.activo} onChange={(e: any) => cambiar(r, { activo: e.target.checked })} />{TIPOS_AVISO[r.tipo]}</label>
                            <input type="time" style={{ width: 130 }} value={r.hora} onChange={(e: any) => cambiar(r, { hora: e.target.value })} aria-label={`Hora del aviso de ${TIPOS_AVISO[r.tipo]}`} />
                        </div>
                        <div className="fila">
                            {DIAS_CORTOS.map((d: string, i: number) => (
                                <button key={i} className={`pequeno ${r.dias.includes(i) ? "primario" : ""}`} aria-pressed={r.dias.includes(i)} onClick={() => cambiar(r, { dias: r.dias.includes(i) ? r.dias.filter((x: number) => x != i) : [...r.dias, i] })}>{d}</button>
                            ))}
                        </div>
                        <label className="casilla"><input type="checkbox" checked={r.texto_generico} onChange={(e: any) => cambiar(r, { texto_generico: e.target.checked })} />Texto genérico en la pantalla bloqueada</label>
                    </li>
                ))}
            </ul>
            {silencio ? (
                <div className="rejilla-2">
                    <CampoTexto etiqueta="Silencio desde" tipo="time" valor={silencio.inicio} alCambiar={(v: string) => setSilencio({ ...silencio, inicio: v })} />
                    <CampoTexto etiqueta="Silencio hasta" tipo="time" valor={silencio.fin} alCambiar={(v: string) => setSilencio({ ...silencio, fin: v })} />
                    <button onClick={async () => { await api.put("/api/perfil", { silencio_inicio: silencio.inicio, silencio_fin: silencio.fin, version: perfil.version }); await recargarPerfil(); avisar("Franja de silencio guardada"); }}>Guardar franja</button>
                </div>
            ) : null}
            <button onClick={() => descargar("/api/avisos/calendario.ics", "funes-fit-recordatorios.ics")}>Descargar recordatorios para el calendario</button>
            <p className="suave">Alternativa si los avisos web no funcionan (por ejemplo en iPhone sin instalar la app): importa el archivo en Calendario o Recordatorios. Si el servidor está apagado, no se envían avisos.</p>
        </div>
    );
}

function Seguridad(props: any): any {
    const { avisar } = useApp();
    const [totp, setTotp] = useState<any>(null);
    const [codigo, setCodigo] = useState<string>("");
    const [codigos, setCodigos] = useState<string[] | null>(null);
    const [contrasenas, setContrasenas] = useState<any>({ actual: "", nueva: "" });
    return (
        <div className="columna">
            <p>Segundo factor (TOTP): {props.usuario.totp_activo ? "activado" : "desactivado"}.</p>
            {!props.usuario.totp_activo && !totp ? <button onClick={async () => setTotp(await api.post("/api/auth/totp/configurar"))}>Activar segundo factor</button> : null}
            {totp && !codigos ? (
                <div className="columna">
                    <p>Añade esta clave en tu app de autenticación (Google Authenticator, Aegis, 1Password…):</p>
                    <code style={{ wordBreak: "break-all" }}>{totp.secreto}</code>
                    <a href={totp.uri} className="boton">Abrir en la app de autenticación</a>
                    <CampoTexto etiqueta="Código de 6 cifras" modo="numeric" valor={codigo} alCambiar={setCodigo} />
                    <button className="primario" onClick={async () => { try { setCodigos((await api.post("/api/auth/totp/activar", { codigo: codigo })).codigos_recuperacion); } catch (e: any) { avisar(e.message, "rojo"); } }}>Confirmar</button>
                </div>
            ) : null}
            {codigos ? <div className="aviso amarillo">Guarda estos códigos de recuperación (cada uno sirve una vez y no se volverán a mostrar): <strong>{codigos.join("  ")}</strong></div> : null}
            <h3>Cambiar contraseña</h3>
            <CampoTexto etiqueta="Contraseña actual" tipo="password" valor={contrasenas.actual} alCambiar={(v: string) => setContrasenas({ ...contrasenas, actual: v })} autocompletar="current-password" />
            <CampoTexto etiqueta="Nueva (mínimo 10 caracteres)" tipo="password" valor={contrasenas.nueva} alCambiar={(v: string) => setContrasenas({ ...contrasenas, nueva: v })} autocompletar="new-password" />
            <button onClick={async () => { try { await api.post("/api/auth/contrasena", contrasenas); avisar("Contraseña cambiada. Se cerraron las demás sesiones."); setContrasenas({ actual: "", nueva: "" }); } catch (e: any) { avisar(e.message, "rojo"); } }}>Cambiar</button>
        </div>
    );
}

function Sincronizacion(): any {
    const { sync, avisar } = useApp();
    const conflictos: any = useDatos("/api/sync/conflictos");
    return (
        <div className="columna">
            <p>Pendientes de enviar: {sync ? sync.pendientes : 0}.{sync && sync.ultimoError ? ` Último intento: ${sync.ultimoError}` : ""}</p>
            <button onClick={() => cola()?.vaciar()}>Sincronizar ahora</button>
            {sync && sync.errores.length ? (
                <ul className="lista">
                    {sync.errores.map((o: any) => (
                        <li key={o.id_operacion}>
                            <div>{o.tipo} · {new Date(o.creada).toLocaleString("es-ES")}</div>
                            <div className="suave">{o.error}</div>
                            <div className="fila"><button className="pequeno" onClick={() => cola().reintentar(o.id_operacion)}>Reintentar</button><button className="pequeno peligro" onClick={() => { if(window.confirm("Se perderá este registro. ¿Descartar?")){ cola().descartar(o.id_operacion); } }}>Descartar</button></div>
                        </li>
                    ))}
                </ul>
            ) : null}
            <h3>Conflictos</h3>
            {conflictos.datos && conflictos.datos.conflictos.length == 0 ? <p className="suave">Ninguno.</p> : null}
            {(conflictos.datos ? conflictos.datos.conflictos : []).map((c: any) => (
                <div key={c.id} className="tarjeta">
                    <p>{c.entidad} · {new Date(c.creado_en).toLocaleString("es-ES")}. Se cambió en dos dispositivos; ninguna versión se ha borrado.</p>
                    <details><summary>Ver las dos versiones</summary><pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{`Este dispositivo:\n${JSON.stringify(c.cliente.datos || c.cliente.ejercicios || c.cliente, null, 1)}\n\nServidor:\n${JSON.stringify(c.servidor.datos || c.servidor.ejercicios || c.servidor, null, 1)}`}</pre></details>
                    <div className="fila">
                        <button className="pequeno" onClick={async () => { try { await api.post(`/api/sync/conflictos/${c.id}/resolver`, { eleccion: "cliente" }); conflictos.recargar(); } catch (e: any) { avisar(e.message, "rojo"); } }}>Quedarme con la de este dispositivo</button>
                        <button className="pequeno" onClick={async () => { await api.post(`/api/sync/conflictos/${c.id}/resolver`, { eleccion: "servidor" }); conflictos.recargar(); }}>Quedarme con la del servidor</button>
                    </div>
                </div>
            ))}
        </div>
    );
}

function Datos(): any {
    const { avisar, usuario, salir } = useApp();
    const [confirmacion, setConfirmacion] = useState<any>({ contrasena: "", confirmacion: "" });
    const importarJson = async (archivo: File): Promise<void> => {
        try {
            const datos: any = JSON.parse(await archivo.text());
            const r: any = await api.post("/api/importar/json", datos);
            avisar(r.aviso);
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const importarCsv = async (archivo: File): Promise<void> => {
        try {
            const texto: string = await archivo.text();
            const previa: any = await api.post("/api/importar/csv/mediciones", { csv: texto });
            const validas: number = previa.filas.filter((f: any) => !f.error).length;
            if(!window.confirm(`Se han detectado ${validas} medidas válidas y ${previa.filas.length - validas} con errores. ¿Guardar las válidas?`)){
                return;
            }
            const r: any = await api.post("/api/importar/csv/mediciones", { csv: texto, confirmar: true });
            avisar(`${r.guardadas} guardadas, ${r.duplicadas} ya existían`);
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <div className="columna">
            <p className="suave">Las exportaciones contienen solo los datos de tu cuenta ({usuario.email}) y se descargan directamente: no se crean enlaces públicos.</p>
            <button onClick={() => descargar("/api/exportar/json", "funes-fit-exportacion.json")}>Exportar todo (JSON)</button>
            <div className="fila">
                {["mediciones", "consumos", "diario", "sesiones", "eventos"].map((t: string) => <button key={t} className="pequeno" onClick={() => descargar(`/api/exportar/csv/${t}`, `funes-fit-${t}.csv`)}>CSV {t}</button>)}
            </div>
            <label className="boton">Importar exportación JSON<input type="file" accept="application/json" style={{ display: "none" }} onChange={(e: any) => e.target.files[0] && importarJson(e.target.files[0])} /></label>
            <label className="boton">Importar medidas CSV (fecha;valor;tipo)<input type="file" accept=".csv,text/csv" style={{ display: "none" }} onChange={(e: any) => e.target.files[0] && importarCsv(e.target.files[0])} /></label>
            <h3>Borrar mi cuenta</h3>
            <p className="suave">Borra todos tus datos y fotos del servidor. No afecta a otras cuentas. Exporta antes si quieres conservarlos.</p>
            <CampoTexto etiqueta="Contraseña" tipo="password" valor={confirmacion.contrasena} alCambiar={(v: string) => setConfirmacion({ ...confirmacion, contrasena: v })} />
            <CampoTexto etiqueta="Escribe BORRAR" valor={confirmacion.confirmacion} alCambiar={(v: string) => setConfirmacion({ ...confirmacion, confirmacion: v })} />
            <button className="peligro" onClick={async () => { try { await api.post("/api/cuenta/borrar", confirmacion); await salir(); } catch (e: any) { avisar(e.message, "rojo"); } }}>Borrar cuenta</button>
        </div>
    );
}

export default function Perfil(): any {
    const { usuario, salir, avisar, recargarPerfil } = useApp();
    const { datos, error, recargar } = useDatos("/api/perfil");
    const objetivos: any = useDatos("/api/objetivos");
    const rutina: any = useDatos("/api/gym/rutina");
    if(!datos){
        return <Cargando error={error} />;
    }
    const p: any = datos.perfil;
    const guardar = async (cambios: any): Promise<void> => {
        try {
            await api.put("/api/perfil", { ...cambios, version: p.version });
            await recargarPerfil();
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const cambiarDistribucion = async (modo: string): Promise<void> => {
        try {
            const r: any = await api.put("/api/gym/distribucion", { modo: modo });
            await guardar({ modo_dias_entreno: modo });
            avisar(r.avisos.join(" ") || "Distribución cambiada");
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const recargarTodo = (): void => {
        recargar();
        objetivos.recargar();
    };
    const esFunes: boolean = rutina.datos && rutina.datos.rutina && rutina.datos.rutina.nombre == "Rutina de cinco días";
    return (
        <div>
            <div className="cabecera">
                <div>
                    <h1>{p.nombre || "Perfil"}</h1>
                    <p className="subtitulo">{usuario.email} · objetivo: {p.modo_objetivo == "ganar" ? "ganar peso y músculo" : p.modo_objetivo == "mantener" ? "mantener" : "perder grasa"}</p>
                </div>
                <button onClick={salir}>Cerrar sesión</button>
            </div>
            {!p.plan_aceptado && datos.pendientes.length ? <ConfirmarPlan perfil={p} alCambiar={recargarTodo} /> : null}
            {p.plan_aceptado && datos.pendientes.length ? (
                <Seccion titulo={`Datos que faltan (${datos.pendientes.length})`} abierta>
                    <ul>{datos.pendientes.map((x: any) => <li key={x.campo}>{x.pregunta}</li>)}</ul>
                    <FormularioInicial perfil={p} niveles={datos.energia.niveles || {}} alCambiar={recargarTodo} />
                </Seccion>
            ) : null}
            <Seccion titulo="Energía y objetivo">
                <Energia energia={datos.energia} objetivo={datos.objetivo_vigente} modo={p.modo_objetivo} alCambiar={recargarTodo} />
                {datos.objetivo_vigente ? (
                    <p>Objetivo {datos.objetivo_vigente.provisional ? "provisional" : "vigente"} desde {datos.objetivo_vigente.vigente_desde}: <strong>{Math.round(datos.objetivo_vigente.kcal)} kcal</strong>{datos.objetivo_vigente.proteina_g ? `, ${Math.round(datos.objetivo_vigente.proteina_g)} g proteína` : ""}{datos.objetivo_vigente.hidratos_g ? `, ${Math.round(datos.objetivo_vigente.hidratos_g)} g hidratos` : ""}{datos.objetivo_vigente.grasas_g ? `, ${Math.round(datos.objetivo_vigente.grasas_g)} g grasas` : ""}{datos.objetivo_vigente.fibra_g ? `, unos ${Math.round(datos.objetivo_vigente.fibra_g)} g fibra` : ""}. <span className="suave">{datos.objetivo_vigente.detalle.nota}</span></p>
                ) : null}
                <h3>Historial de objetivos</h3>
                <table className="tabla">
                    <tbody>{(objetivos.datos ? objetivos.datos.objetivos : []).map((o: any) => <tr key={o.id}><td>Desde {o.vigente_desde}</td><td className="num">{o.kcal ? `${Math.round(o.kcal)} kcal` : "—"}</td><td className="suave">{o.origen}{o.provisional ? " (provisional)" : ""}</td></tr>)}</tbody>
                </table>
                <p className="suave">Un objetivo nuevo empieza hoy o más tarde y nunca se aplica a días anteriores.</p>
            </Seccion>
            <Seccion titulo="Preferencias">
                <div className="columna">
                    <Selector etiqueta="Modo de registro" valor={p.modo_registro} alCambiar={(v: string) => guardar({ modo_registro: v })} opciones={[{ valor: "calorias", texto: "Con calorías y macros" }, { valor: "sin_calorias", texto: "Solo qué como, sin contar calorías" }]} />
                    <Selector etiqueta="Tema" valor={p.tema} alCambiar={(v: string) => guardar({ tema: v })} opciones={[{ valor: "sistema", texto: "Como el sistema" }, { valor: "claro", texto: "Claro" }, { valor: "oscuro", texto: "Oscuro" }]} />
                    <Selector etiqueta="Modo de objetivo" valor={p.modo_objetivo} alCambiar={(v: string) => guardar({ modo_objetivo: v })} opciones={[{ valor: "perder", texto: "Perder grasa" }, { valor: "mantener", texto: "Mantener" }, { valor: "ganar", texto: "Ganar peso" }]} />
                    <CampoTexto etiqueta="Comensales" modo="numeric" valor={String(p.comensales)} alCambiar={(v: string) => v && guardar({ comensales: v })} />
                    <label>Alimentos que no te gustan (separados por comas)
                        <input defaultValue={p.alimentos_excluidos.join(", ")} onBlur={(e: any) => guardar({ alimentos_excluidos: e.target.value.split(",").map((x: string) => x.trim()).filter(Boolean) })} />
                    </label>
                    {p.presupuesto_semanal != null ? <p className="suave">Presupuesto {p.presupuesto_confirmado ? "confirmado" : "provisional de planificación"}: {euros(p.presupuesto_semanal)} por semana.</p> : null}
                    {esFunes ? (
                        <Selector etiqueta="Días de gimnasio" valor={p.modo_dias_entreno} alCambiar={cambiarDistribucion} opciones={[{ valor: "estandar", texto: "L torso · M pierna A · J empuje · V tirón · S pierna B" }, { valor: "lunes_viernes", texto: "Solo de lunes a viernes (volumen ajustado)" }]} />
                    ) : null}
                </div>
            </Seccion>
            <Seccion titulo="Salud y señales de alerta">
                <p className="suave">Marca si te pasa. Mientras haya alguna marcada, la app no propone bajar calorías y te recomienda consultar con un profesional. No es un diagnóstico.</p>
                {[["mareos", "Mareos"], ["fatiga_marcada", "Fatiga marcada"], ["caida_rendimiento", "Caída persistente del rendimiento"], ["perdida_rapida", "Pérdida de peso demasiado rápida"]].map((s: any) => (
                    <label key={s[0]} className="casilla"><input type="checkbox" checked={!!p.sintomas_alerta[s[0]]} onChange={(e: any) => guardar({ sintomas_alerta: { ...p.sintomas_alerta, [s[0]]: e.target.checked } })} />{s[1]}</label>
                ))}
            </Seccion>
            <Seccion titulo="Avisos"><Avisos /></Seccion>
            <Seccion titulo="Sincronización"><Sincronizacion /></Seccion>
            <Seccion titulo="Seguridad"><Seguridad usuario={usuario} /></Seccion>
            <Seccion titulo="Tus datos"><Datos /></Seccion>
            <Seccion titulo="Instalar en el móvil">
                <ul>
                    <li><strong>iPhone (Safari):</strong> botón Compartir → «Añadir a pantalla de inicio». Ábrela desde el icono para tener avisos (iOS 16.4 o posterior).</li>
                    <li><strong>Android (Chrome):</strong> menú ⋮ → «Instalar aplicación» o «Añadir a pantalla de inicio».</li>
                    <li><strong>Ordenador (Chrome/Edge):</strong> icono de instalar en la barra de direcciones.</li>
                </ul>
                <p className="suave">Para instalarla desde el móvil hace falta abrirla por HTTPS (ver la guía del proyecto). Sin conexión puedes consultar el menú y la rutina ya cargados y registrar; se sincroniza al volver la red.</p>
            </Seccion>
        </div>
    );
}
