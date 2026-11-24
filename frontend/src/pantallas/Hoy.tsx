import { useState } from "react";
import { Cargando, Nutrientes, useApp, useDatos } from "../componentes";
import { MOMENTOS, entradaNumero, textoNumeroEntrada } from "../utilidades";
import RegistroComida, { marcarComoPrevisto, textoEstado } from "./RegistroComida";

export default function Hoy(): any {
    const { perfil, registrar, avisar, estadoSync } = useApp();
    const { datos, error, recargar } = useDatos("/api/hoy");
    const [registro, setRegistro] = useState<any>(null);
    const [diario, setDiario] = useState<any>({});
    const [enviando, setEnviando] = useState<Set<number>>(new Set());

    if(!datos){
        return <Cargando error={error} />;
    }
    const menu: any = datos.menu;
    const entreno: any = datos.entreno;
    const entrada: any = { ...(datos.diario.datos || {}), ...diario };

    const comido = async (comida: any): Promise<void> => {
        if(enviando.has(comida.id)){
            return;
        }
        setEnviando(new Set(enviando).add(comida.id));
        try {
            await marcarComoPrevisto(registrar, comida);
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    const guardarDiario = async (): Promise<void> => {
        const valores: any = { ...(datos.diario.datos || {}) };
        for(const clave of ["agua_ml", "pasos", "sueno_horas"]){
            if(diario[clave] != undefined){
                const n: number | null = entradaNumero(diario[clave]);
                if(n == null){
                    delete valores[clave];
                }else{
                    valores[clave] = n;
                }
            }
        }
        try {
            await registrar("diario.guardar", { fecha: datos.fecha, datos: valores, version_base: datos.diario.version });
            setDiario({});
            avisar("Guardado");
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    return (
        <div>
            <div className="cabecera">
                <div>
                    <h1>{datos.nombre ? `Hola, ${datos.nombre}` : "Hoy"}</h1>
                    <p className="subtitulo">{datos.texto_fecha}</p>
                </div>
                <div className="columna" style={{ alignItems: "flex-end" }}>
                    {estadoSync}
                    <a href="#/perfil" className="suave">Perfil y ajustes</a>
                </div>
            </div>
            {datos.pendientes > 0 ? <a href="#/perfil" className="aviso amarillo" style={{ display: "block", color: "inherit" }}>Faltan {datos.pendientes} datos de tu perfil. Puedes completarlos cuando quieras; la app funciona igual mientras tanto.</a> : null}
            {!datos.plan_aceptado ? <a href="#/perfil" className="aviso" style={{ display: "block", color: "inherit" }}>Tu menú y tu rutina son una propuesta. Revísalos y confírmalos en tu perfil.</a> : null}

            <section className="tarjeta" aria-labelledby="t-entreno">
                <h2 id="t-entreno">Actividad de hoy</h2>
                {entreno.sin_rutina ? <p className="suave">No hay rutina configurada.</p> : null}
                {entreno.descanso && !entreno.sin_rutina ? <p>{entreno.texto_descanso}</p> : null}
                <ul className="lista">
                    {entreno.actividades.map((a: any) => (
                        <li key={a.clave_plan || a.evento_id} className="fila separada">
                            <div>
                                <strong>{a.titulo}</strong>{a.hora ? ` · ${a.hora}` : ""}
                                {a.detalle && a.detalle.ejercicios.length ? <div className="suave">{a.detalle.tiempo.texto}</div> : null}
                            </div>
                            <a className="boton" href={`#/gym/${datos.fecha}`}>
                                {a.sesion_registrada ? (a.sesion_registrada.estado == "en_curso" ? "Continuar" : "Ver") : a.estado == "realizado" ? "Hecho ✓" : "Abrir"}
                            </a>
                        </li>
                    ))}
                </ul>
            </section>

            <section className="tarjeta" aria-labelledby="t-comidas">
                <div className="fila separada">
                    <h2 id="t-comidas">Comidas</h2>
                    <a href="#/menu" className="suave">Ver semana</a>
                </div>
                {!menu.hay_plan ? <p>No hay menú para esta semana. <a href="#/menu">Prepáralo desde Menú</a>.</p> : null}
                <ul className="lista">
                    {menu.comidas.map((c: any) => (
                        <li key={c.id}>
                            <div className="fila separada">
                                <div>
                                    <div className="suave">{MOMENTOS[c.momento]}{c.hora ? ` · ${c.hora}` : ""}{c.opcional ? " · opcional" : ""}</div>
                                    <strong>{c.receta_nombre}</strong>
                                    <div><Nutrientes n={c.nutrientes} /></div>
                                    {c.estado != "pendiente" ? <span className="etiqueta ok">{textoEstado(c.estado)}</span> : null}
                                </div>
                            </div>
                            {c.estado == "pendiente" ? (
                                <div className="fila" style={{ marginTop: 8 }}>
                                    <button className="primario" disabled={enviando.has(c.id)} onClick={() => comido(c)}>Comido ✓</button>
                                    <button onClick={() => setRegistro(c)}>Otra cosa / parte</button>
                                </div>
                            ) : null}
                        </li>
                    ))}
                </ul>
                <div className="fila" style={{ marginTop: 8 }}>
                    <button onClick={() => setRegistro({ extra: true })}>+ Añadir extra</button>
                </div>
                {menu.aviso_registro ? <p className="suave">{menu.aviso_registro}</p> : null}
                {perfil && perfil.modo_registro != "sin_calorias" ? (
                    <p className="suave">
                        Previsto: {Math.round(menu.planificado.kcal)} kcal. Registrado: {menu.consumido_registrado ? `${Math.round(menu.consumido_registrado.kcal || 0)} kcal en lo que tiene cantidades` : "nada todavía"}.
                        {menu.objetivo ? ` Objetivo ${menu.objetivo.provisional ? "provisional" : "vigente"}: ${Math.round(menu.objetivo.kcal)} kcal.` : ""}
                    </p>
                ) : null}
            </section>

            <section className="tarjeta" aria-labelledby="t-diario">
                <h2 id="t-diario">Registro rápido</h2>
                <p className="suave">Todo es opcional.</p>
                <div className="rejilla-3">
                    <label>Agua (ml)<input inputMode="numeric" value={diario.agua_ml ?? textoNumeroEntrada(entrada.agua_ml)} onChange={(e: any) => setDiario({ ...diario, agua_ml: e.target.value })} /></label>
                    <label>Pasos<input inputMode="numeric" value={diario.pasos ?? textoNumeroEntrada(entrada.pasos)} onChange={(e: any) => setDiario({ ...diario, pasos: e.target.value })} /></label>
                    <label>Sueño (h)<input inputMode="decimal" value={diario.sueno_horas ?? textoNumeroEntrada(entrada.sueno_horas)} onChange={(e: any) => setDiario({ ...diario, sueno_horas: e.target.value })} /></label>
                </div>
                <div className="fila" style={{ marginTop: 8 }}>
                    <button className="primario" onClick={guardarDiario} disabled={Object.keys(diario).length == 0}>Guardar</button>
                    <a href="#/progreso/diario" className="suave">Diario completo</a>
                </div>
            </section>

            {registro ? (
                <RegistroComida
                    comida={registro.extra ? null : registro}
                    fecha={datos.fecha}
                    alCerrar={() => setRegistro(null)}
                    alGuardar={() => {
                        setRegistro(null);
                        recargar();
                    }}
                />
            ) : null}
        </div>
    );
}
