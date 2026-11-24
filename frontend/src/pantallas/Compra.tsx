import { useState } from "react";
import { api } from "../api";
import { CampoTexto, Cargando, Modal, Selector, useApp, useDatos } from "../componentes";
import { cantidad, entradaNumero, euros, numero, sumarDias, textoFecha, uuid } from "../utilidades";

const ORIGEN_PRECIO: any = { desconocido: "sin precio", referencia_externa: "referencia externa sin confirmar", manual: "introducido por ti", ticket: "de ticket", catalogo: "de catálogo" };

function EditarProducto(props: any): any {
    const { avisar } = useApp();
    const p: any = props.producto;
    const [f, setF] = useState<any>({ nombre: p.nombre, capacidad: String(p.capacidad).replace(".", ","), unidad: p.unidad, capacidad_util: String(p.capacidad_util).replace(".", ","), precio: p.precio == null ? "" : String(p.precio).replace(".", ","), tienda: p.tienda || "", formato_verificado: p.formato_verificado });
    const guardar = async (): Promise<void> => {
        try {
            await api.put(`/api/productos/${p.id}`, { ...f, precio: f.precio == "" ? null : f.precio, precio_origen: "manual" });
            avisar("Producto actualizado");
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Formato y precio" alCerrar={props.alCerrar}>
            <div className="columna">
                <CampoTexto etiqueta="Producto" valor={f.nombre} alCambiar={(v: string) => setF({ ...f, nombre: v })} />
                <div className="rejilla-2">
                    <CampoTexto etiqueta="Contenido del envase" modo="decimal" valor={f.capacidad} alCambiar={(v: string) => setF({ ...f, capacidad: v })} />
                    <Selector etiqueta="Unidad" valor={f.unidad} alCambiar={(v: string) => setF({ ...f, unidad: v })} opciones={["g", "kg", "ml", "l", "ud"].map((u: string) => ({ valor: u, texto: u }))} />
                </div>
                <CampoTexto etiqueta={`Cantidad útil en ${props.unidadBase} (escurrida o comestible)`} modo="decimal" valor={f.capacidad_util} alCambiar={(v: string) => setF({ ...f, capacidad_util: v })} />
                <CampoTexto etiqueta="Precio del envase (€)" modo="decimal" valor={f.precio} alCambiar={(v: string) => setF({ ...f, precio: v })} />
                <CampoTexto etiqueta="Tienda y zona" valor={f.tienda} alCambiar={(v: string) => setF({ ...f, tienda: v })} />
                <label className="casilla"><input type="checkbox" checked={f.formato_verificado} onChange={(e: any) => setF({ ...f, formato_verificado: e.target.checked })} /> He comprobado el formato en la etiqueta</label>
                <p className="suave">{p.nota_capacidad}</p>
                {p.precio_fuente ? <p className="suave">Precio actual: {ORIGEN_PRECIO[p.precio_origen]}{p.precio_fecha ? ` (${p.precio_fecha})` : ""}. {p.precio_fuente}</p> : null}
                <button className="primario" onClick={guardar}>Guardar</button>
            </div>
        </Modal>
    );
}

function Ticket(props: any): any {
    const { avisar } = useApp();
    const [texto, setTexto] = useState<string>("");
    const [tienda, setTienda] = useState<string>("");
    const [filas, setFilas] = useState<any[] | null>(null);
    const previsualizar = async (): Promise<void> => {
        try {
            setFilas((await api.post("/api/productos/ticket/previsualizar", { csv: texto })).filas);
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const confirmar = async (): Promise<void> => {
        try {
            const r: any = await api.post("/api/productos/ticket/confirmar", { filas: filas, tienda: tienda });
            avisar(`${r.guardados} precios guardados`);
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Precios desde un ticket" alCerrar={props.alCerrar}>
            <p className="suave">Pega líneas con el formato «producto;precio», por ejemplo «Arroz redondo 1 kg;1,15». Revisa lo detectado antes de guardar.</p>
            <label>Líneas del ticket<textarea value={texto} onChange={(e: any) => setTexto(e.target.value)} /></label>
            <CampoTexto etiqueta="Tienda y zona" valor={tienda} alCambiar={setTienda} />
            <button onClick={previsualizar} style={{ marginTop: 8 }}>Revisar</button>
            {filas ? (
                <>
                    <table className="tabla">
                        <tbody>
                            {filas.map((f: any, i: number) => (
                                <tr key={i}>
                                    <td>{f.texto}{f.error ? <div className="suave">{f.error}</div> : null}</td>
                                    <td className="num">{f.precio != null ? euros(f.precio) : ""}</td>
                                    <td>
                                        {f.candidatos ? (
                                            <select value={f.producto_id ?? ""} onChange={(e: any) => { const copia: any[] = filas.slice(); copia[i] = { ...f, producto_id: e.target.value ? Number(e.target.value) : null }; setFilas(copia); }}>
                                                <option value="">No guardar</option>
                                                {(props.productos || []).map((p: any) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                                            </select>
                                        ) : null}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <button className="primario" onClick={confirmar}>Guardar precios confirmados</button>
                </>
            ) : null}
        </Modal>
    );
}

function Despensa(props: any): any {
    const { avisar } = useApp();
    const { datos, recargar } = useDatos("/api/despensa");
    const alimentos: any = useDatos("/api/alimentos");
    const [alimento, setAlimento] = useState<string>("");
    const [valor, setValor] = useState<string>("");
    const guardar = async (id: string, cantidadNueva: string): Promise<void> => {
        try {
            await api.put(`/api/despensa/${id}`, { cantidad: cantidadNueva });
            recargar();
            props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Despensa" alCerrar={props.alCerrar}>
            <p className="suave">Lo que ya tienes en casa. Se descuenta de la lista sin generar cantidades negativas. Usa peso escurrido en conservas y peso con piel en fruta.</p>
            <ul className="lista">
                {(datos ? datos.despensa : []).map((d: any) => (
                    <li key={d.alimento_id} className="fila separada">
                        <span>{d.nombre}</span>
                        <span className="fila"><strong>{cantidad(d.cantidad, d.unidad)}</strong><button className="pequeno" onClick={() => guardar(String(d.alimento_id), "0")}>Vaciar</button></span>
                    </li>
                ))}
            </ul>
            <div className="rejilla-2" style={{ marginTop: 8 }}>
                <label>Alimento<select value={alimento} onChange={(e: any) => setAlimento(e.target.value)}><option value="">—</option>{(alimentos.datos ? alimentos.datos.alimentos : []).map((a: any) => <option key={a.id} value={a.id}>{a.nombre} ({a.unidad_base})</option>)}</select></label>
                <CampoTexto etiqueta="Cantidad que tienes" modo="decimal" valor={valor} alCambiar={setValor} />
            </div>
            <button style={{ marginTop: 8 }} disabled={!alimento} onClick={() => guardar(alimento, valor)}>Guardar</button>
        </Modal>
    );
}

function NuevoAlimento(props: any): any {
    const { avisar } = useApp();
    const [f, setF] = useState<any>({ nombre: "", base: "100g", kcal: "", proteina: "", hidratos: "", grasas: "", fibra: "", estado_peso: "tal_cual", seccion: "Otros", codigo_barras: "", origen: "etiqueta" });
    const guardar = async (): Promise<void> => {
        try {
            await api.post("/api/alimentos", { ...f, fibra: f.fibra == "" ? null : f.fibra });
            avisar("Alimento añadido");
            props.alCerrar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    return (
        <Modal titulo="Añadir alimento con su etiqueta" alCerrar={props.alCerrar}>
            <div className="columna">
                <CampoTexto etiqueta="Nombre" valor={f.nombre} alCambiar={(v: string) => setF({ ...f, nombre: v })} />
                <div className="rejilla-2">
                    <Selector etiqueta="Valores por" valor={f.base} alCambiar={(v: string) => setF({ ...f, base: v })} opciones={[{ valor: "100g", texto: "100 g" }, { valor: "100ml", texto: "100 ml" }, { valor: "unidad", texto: "unidad" }]} />
                    <Selector etiqueta="Origen" valor={f.origen} alCambiar={(v: string) => setF({ ...f, origen: v })} opciones={[{ valor: "etiqueta", texto: "Etiqueta" }, { valor: "manual", texto: "Estimación manual" }, { valor: "generico", texto: "Base genérica" }]} />
                </div>
                <div className="rejilla-2">
                    {[["kcal", "kcal"], ["proteina", "Proteína g"], ["hidratos", "Hidratos g"], ["grasas", "Grasas g"], ["fibra", "Fibra g (si viene)"]].map((c: any) => <CampoTexto key={c[0]} etiqueta={c[1]} modo="decimal" valor={f[c[0]]} alCambiar={(v: string) => setF({ ...f, [c[0]]: v })} />)}
                </div>
                <Selector etiqueta="Cómo se pesa" valor={f.estado_peso} alCambiar={(v: string) => setF({ ...f, estado_peso: v })} opciones={[{ valor: "tal_cual", texto: "Tal cual" }, { valor: "crudo", texto: "En crudo" }, { valor: "seco", texto: "En seco" }, { valor: "cocido_escurrido", texto: "Cocido y escurrido" }, { valor: "escurrido", texto: "Escurrido" }, { valor: "comestible", texto: "Parte comestible" }]} />
                <CampoTexto etiqueta="Código de barras (opcional)" modo="numeric" valor={f.codigo_barras} alCambiar={(v: string) => setF({ ...f, codigo_barras: v })} />
                <button className="primario" onClick={guardar}>Guardar</button>
            </div>
        </Modal>
    );
}

export default function Compra(): any {
    const { registrar, avisar, estadoSync } = useApp();
    const [fecha, setFecha] = useState<string | null>(null);
    const semana: any = useDatos(`/api/menu/semana${fecha ? `?fecha=${fecha}` : ""}`);
    const planId: number | null = semana.datos && semana.datos.plan ? semana.datos.plan.id : null;
    const lista: any = useDatos(planId ? `/api/menu/${planId}/compra` : null, [planId]);
    const productos: any = useDatos("/api/productos");
    const [dialogo, setDialogo] = useState<any>(null);
    const [marcando, setMarcando] = useState<Set<number>>(new Set());

    if(!semana.datos){
        return <Cargando error={semana.error} />;
    }
    const recargar = (): void => {
        lista.recargar();
        productos.recargar();
    };
    const marcar = async (l: any): Promise<void> => {
        if(marcando.has(l.alimento_id)){
            return;
        }
        setMarcando(new Set(marcando).add(l.alimento_id));
        try {
            await registrar("compra.marcar", { id_cliente: uuid(), plan_id: planId, alimento_id: l.alimento_id, producto_id: l.producto ? l.producto.id : null, envases: l.envases ?? 1, cantidad: l.producto ? null : l.cantidad_a_comprar });
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const cerrarSemana = async (): Promise<void> => {
        if(!window.confirm("Se descontará de la despensa lo previsto para esta semana. ¿Continuar?")){
            return;
        }
        try {
            const r: any = await api.post(`/api/compra/${planId}/cerrar`);
            avisar(r.aviso || "Semana cerrada");
            recargar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };
    const exportarCsv = (): void => {
        const filas: string[] = ["Sección;Producto;Necesario;Unidad;Envases;Sobrante;Precio;Estado precio"];
        for(const l of lista.datos.lineas){
            filas.push([l.seccion, l.producto ? l.producto.nombre : l.nombre, Math.round(l.necesidad_compra), l.unidad, l.envases ?? "", l.sobrante == null ? "" : Math.round(l.sobrante), l.producto && l.producto.precio != null ? String(l.producto.precio).replace(".", ",") : "", l.precio_estado].join(";"));
        }
        const enlace: HTMLAnchorElement = document.createElement("a");
        enlace.href = URL.createObjectURL(new Blob(["﻿" + filas.join("\n")], { type: "text/csv" }));
        enlace.download = `compra-${semana.datos.lunes}.csv`;
        enlace.click();
    };

    const datos: any = lista.datos;
    return (
        <div>
            <div className="cabecera">
                <div>
                    <h1>Compra</h1>
                    <p className="subtitulo">Semana del {textoFecha(semana.datos.lunes)}{datos ? ` · ${datos.comensales} comensal${datos.comensales == 1 ? "" : "es"}` : ""}</p>
                </div>
                {estadoSync}
            </div>
            <div className="fila no-imprimir" style={{ marginBottom: 10 }}>
                <button aria-label="Semana anterior" onClick={() => setFecha(sumarDias(semana.datos.lunes, -7))}>←</button>
                <button aria-label="Semana siguiente" onClick={() => setFecha(sumarDias(semana.datos.lunes, 7))}>→</button>
                <button onClick={() => setDialogo({ tipo: "despensa" })}>Despensa</button>
                <button onClick={() => setDialogo({ tipo: "ticket" })}>Precios de ticket</button>
                <button onClick={() => setDialogo({ tipo: "alimento" })}>+ Alimento</button>
            </div>
            {!planId ? <div className="tarjeta">No hay menú esta semana. <a href="#/menu">Créalo en Menú</a>.</div> : !datos ? <Cargando error={lista.error} /> : (
                <>
                    <div className="tarjeta">
                        <h2>Resumen</h2>
                        <p>Desembolso pendiente con precios conocidos: <strong>{euros(datos.totales.desembolso_pendiente_conocido)}</strong>. Ya gastado: {euros(datos.totales.desembolso_realizado_conocido)}.</p>
                        <p>Coste de lo que vas a consumir: {euros(datos.totales.coste_consumido_conocido)} (lo que sobra pasa a la despensa).</p>
                        <div className={`aviso ${datos.totales.estado == "parcial" ? "amarillo" : ""}`}>{datos.totales.aviso}</div>
                        {datos.presupuesto.importe != null ? <p className="suave">Presupuesto {datos.presupuesto.confirmado ? "" : "provisional "}{euros(datos.presupuesto.importe)}: {datos.presupuesto.mensaje}</p> : null}
                        {datos.aviso_semana_anterior ? <div className="aviso amarillo">{datos.aviso_semana_anterior}</div> : null}
                        <p className="suave">No hay conexión con ninguna tienda: no se muestran precios, disponibilidad ni enlaces que no hayas confirmado.</p>
                    </div>
                    {datos.secciones.map((s: any) => (
                        <section key={s.nombre} className="tarjeta">
                            <h2>{s.nombre}</h2>
                            <ul className="lista">
                                {s.lineas.map((l: any) => (
                                    <li key={l.alimento_id}>
                                        <div className="fila separada" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
                                            <label className="casilla" style={{ alignItems: "flex-start" }}>
                                                <input type="checkbox" checked={l.estado != "pendiente"} disabled={l.estado != "pendiente" || marcando.has(l.alimento_id)} onChange={() => marcar(l)} aria-label={`Marcar ${l.nombre} como comprado`} />
                                                <span>
                                                    <strong>{l.producto ? l.producto.nombre : l.nombre}</strong>
                                                    <div className="suave">
                                                        Consumo: {cantidad(l.necesidad_neta, l.unidad)}{l.factor_compra != 1 ? ` (${cantidad(l.necesidad_compra, l.unidad)} con merma, factor ${numero(l.factor_compra, 2)})` : ""}
                                                        {l.uso_despensa > 0 ? ` · de despensa ${cantidad(l.uso_despensa, l.unidad)}` : ""}
                                                    </div>
                                                    <div className="suave">
                                                        {l.estado == "pendiente" ? (l.envases != null ? `Comprar ${l.envases} envase${l.envases == 1 ? "" : "s"}` : `Comprar ${cantidad(l.cantidad_a_comprar, l.unidad)} (sin formato)`) : l.estado == "comprado" ? "Comprado" : "Ya en despensa"}
                                                        {l.sobrante != null && l.sobrante > 0.5 ? ` · sobrará ${cantidad(l.sobrante, l.unidad)}` : ""}
                                                    </div>
                                                    {l.producto && !l.producto.formato_verificado ? <span className="etiqueta aviso">formato sin verificar</span> : null}
                                                </span>
                                            </label>
                                            <div className="columna" style={{ alignItems: "flex-end", flex: "none" }}>
                                                <span>{l.producto && l.producto.precio != null ? euros(l.producto.precio) : <span className="suave">sin precio</span>}</span>
                                                {l.producto && l.producto.precio != null && l.precio_estado == "estimado" ? <span className="etiqueta aviso">orientativo</span> : null}
                                                {l.producto ? <button className="pequeno no-imprimir" onClick={() => setDialogo({ tipo: "producto", producto: productos.datos ? productos.datos.productos.find((p: any) => p.id == l.producto.id) : null, unidadBase: l.unidad })}>Editar</button> : null}
                                            </div>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    ))}
                    <div className="tarjeta no-imprimir">
                        <div className="fila">
                            <button onClick={() => window.print()}>Imprimir / PDF</button>
                            <button onClick={exportarCsv}>Exportar CSV</button>
                            <button onClick={cerrarSemana} disabled={datos.plan.cerrada}>{datos.plan.cerrada ? "Semana cerrada" : "Cerrar semana"}</button>
                        </div>
                        <p className="suave">Al cerrar la semana se descuenta lo previsto y lo que sobra (aceite, arroz…) queda en la despensa para la siguiente.</p>
                    </div>
                </>
            )}
            {dialogo && dialogo.tipo == "producto" && dialogo.producto ? <EditarProducto producto={dialogo.producto} unidadBase={dialogo.unidadBase} alCerrar={() => setDialogo(null)} alCambiar={() => { setDialogo(null); recargar(); }} /> : null}
            {dialogo && dialogo.tipo == "ticket" ? <Ticket productos={productos.datos ? productos.datos.productos : []} alCerrar={() => setDialogo(null)} alCambiar={() => { setDialogo(null); recargar(); }} /> : null}
            {dialogo && dialogo.tipo == "despensa" ? <Despensa alCerrar={() => setDialogo(null)} alCambiar={recargar} /> : null}
            {dialogo && dialogo.tipo == "alimento" ? <NuevoAlimento alCerrar={() => setDialogo(null)} /> : null}
        </div>
    );
}

export { entradaNumero };
