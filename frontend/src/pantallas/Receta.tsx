import { useState } from "react";
import { api } from "../api";
import { CampoTexto, Cargando, Confianza, Modal, Nutrientes, Selector, useApp, useDatos } from "../componentes";
import { entradaNumero, numero } from "../utilidades";

const ESTADOS: any = { seco: "en seco", crudo: "en crudo", crudo_pelado: "en crudo, pelado", cocido_escurrido: "cocido y escurrido", escurrido: "escurrido", sin_cascara: "sin cáscara", comestible: "parte comestible", pelado: "pelado", tal_cual: "" };

export default function Receta(props: any): any {
    const { avisar } = useApp();
    const { datos, error, recargar } = useDatos(`/api/recetas/${props.id}`);
    const [editando, setEditando] = useState<boolean>(false);
    const [lote, setLote] = useState<any>({ peso: "", porcion: "", resultado: null });

    if(!datos){
        return <Modal titulo="Receta" alCerrar={props.alCerrar}><Cargando error={error} /></Modal>;
    }
    const r: any = datos.receta;

    const accion = async (f: () => Promise<any>, texto: string): Promise<void> => {
        try {
            await f();
            avisar(texto);
            recargar();
            props.alCambiar && props.alCambiar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    const calcularLote = async (): Promise<void> => {
        try {
            const res: any = await api.post(`/api/recetas/${r.id}/porcion-lote`, { peso_final_lote: entradaNumero(lote.peso), porcion_servida: entradaNumero(lote.porcion) });
            setLote({ ...lote, resultado: res.nutrientes });
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    if(editando){
        return <EditorReceta receta={r} alCerrar={() => setEditando(false)} alGuardar={() => { setEditando(false); recargar(); props.alCambiar && props.alCambiar(); }} />;
    }

    return (
        <Modal titulo={r.nombre} alCerrar={props.alCerrar}>
            <div className="fila">
                <Confianza valor={r.confianza} />
                {r.tiempo_min ? <span className="etiqueta">≈ {r.tiempo_min} min</span> : null}
                <span className="etiqueta">{numero(r.raciones, 2)} ración{r.raciones == 1 ? "" : "es"}</span>
                {r.favorita ? <span className="etiqueta ok">Favorita</span> : null}
            </div>
            {datos.receta.avisos_exclusion && datos.receta.avisos_exclusion.length ? <div className="aviso amarillo">Contiene algo que marcaste como no deseado: {datos.receta.avisos_exclusion.join(", ")}</div> : null}
            <p><Nutrientes n={r.nutrientes_racion} forzar /> por ración</p>
            <h3>Ingredientes por ración</h3>
            <table className="tabla">
                <tbody>
                    {r.ingredientes.map((i: any) => (
                        <tr key={i.id}>
                            <td>{i.nombre} <span className="suave">{ESTADOS[i.estado_peso] ?? i.estado_peso}</span></td>
                            <td className="num">{numero(i.cantidad / r.raciones, 1)} {i.unidad}</td>
                            <td className="num suave">{Math.round(i.valores.kcal)} kcal</td>
                        </tr>
                    ))}
                </tbody>
            </table>
            <p className="suave">El aceite incluye todo el de cocinar y aliñar. Los valores son estimaciones de los ingredientes; cámbialos por los de tus etiquetas en Compra → Alimentos.</p>
            <h3>Preparación</h3>
            <ol>{r.pasos.map((p: string, i: number) => <li key={i}>{p}</li>)}</ol>
            {r.alergenos.length ? <p><strong>Alérgenos:</strong> {r.alergenos.join(", ")}</p> : <p className="suave">Sin alérgenos registrados en los ingredientes.</p>}
            {r.conservacion ? <p><strong>Conservación:</strong> {r.conservacion}</p> : null}
            {r.sustituciones.length ? (<><h3>Sustituciones</h3><ul>{r.sustituciones.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></>) : null}
            {r.notas ? <p className="suave">{r.notas}</p> : null}
            <details>
                <summary>Calcular una porción de un lote cocinado</summary>
                <p className="suave">Pesa el lote cocinado entero y la porción que te sirves. No se usa ninguna conversión universal de seco a cocido.</p>
                <div className="rejilla-2">
                    <CampoTexto etiqueta="Peso final del lote (g)" modo="decimal" valor={lote.peso} alCambiar={(v: string) => setLote({ ...lote, peso: v })} />
                    <CampoTexto etiqueta="Porción servida (g)" modo="decimal" valor={lote.porcion} alCambiar={(v: string) => setLote({ ...lote, porcion: v })} />
                </div>
                <button onClick={calcularLote} style={{ marginTop: 8 }}>Calcular</button>
                {lote.resultado ? <p><Nutrientes n={lote.resultado} forzar /></p> : null}
            </details>
            <div className="fila" style={{ marginTop: 12 }}>
                <button onClick={() => setEditando(true)}>Editar</button>
                <button onClick={() => accion(() => api.put(`/api/recetas/${r.id}`, { favorita: !r.favorita }), r.favorita ? "Quitada de favoritas" : "Guardada en favoritas")}>{r.favorita ? "Quitar favorita" : "Favorita"}</button>
                <button onClick={() => accion(() => api.post(`/api/recetas/${r.id}/duplicar`), "Receta duplicada")}>Duplicar</button>
            </div>
        </Modal>
    );
}

export function EditorReceta(props: any): any {
    const { avisar } = useApp();
    const r: any = props.receta || { nombre: "", momento_tipico: "comida", raciones: 1, tiempo_min: null, pasos: [], conservacion: "", sustituciones: [], ingredientes: [] };
    const alimentos: any = useDatos("/api/alimentos");
    const [f, setF] = useState<any>({
        nombre: r.nombre,
        momento_tipico: r.momento_tipico,
        raciones: String(r.raciones).replace(".", ","),
        tiempo_min: r.tiempo_min ? String(r.tiempo_min) : "",
        pasos: (r.pasos || []).join("\n"),
        conservacion: r.conservacion || "",
        sustituciones: (r.sustituciones || []).join("\n"),
        ingredientes: r.ingredientes.map((i: any) => ({ alimento_id: String(i.alimento_id), cantidad: String(i.cantidad).replace(".", ","), unidad: i.unidad })),
    });

    const guardar = async (): Promise<void> => {
        const cuerpo: any = {
            nombre: f.nombre,
            momento_tipico: f.momento_tipico,
            raciones: f.raciones,
            tiempo_min: f.tiempo_min,
            pasos: f.pasos.split("\n"),
            conservacion: f.conservacion,
            sustituciones: f.sustituciones.split("\n"),
            ingredientes: f.ingredientes.filter((i: any) => i.alimento_id).map((i: any) => ({ alimento_id: Number(i.alimento_id), cantidad: i.cantidad, unidad: i.unidad })),
        };
        try {
            const res: any = props.receta ? await api.put(`/api/recetas/${r.id}`, cuerpo) : await api.post("/api/recetas", cuerpo);
            avisar([res.aviso, ...(res.avisos || [])].filter(Boolean).join(" ") || "Receta guardada", res.avisos && res.avisos.length ? "amarillo" : "");
            props.alGuardar(res.receta);
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    const ingrediente = (indice: number, campo: string, valor: string): void => {
        const lista: any[] = f.ingredientes.slice();
        lista[indice] = { ...lista[indice], [campo]: valor };
        if(campo == "alimento_id" && alimentos.datos){
            const a: any = alimentos.datos.alimentos.find((x: any) => String(x.id) == valor);
            if(a){
                lista[indice].unidad = a.unidad_base;
            }
        }
        setF({ ...f, ingredientes: lista });
    };

    return (
        <Modal titulo={props.receta ? `Editar ${r.nombre}` : "Nueva receta"} alCerrar={props.alCerrar}>
            <div className="columna">
                <CampoTexto etiqueta="Nombre" valor={f.nombre} alCambiar={(v: string) => setF({ ...f, nombre: v })} />
                <div className="rejilla-3">
                    <Selector etiqueta="Momento" valor={f.momento_tipico} alCambiar={(v: string) => setF({ ...f, momento_tipico: v })} opciones={[{ valor: "desayuno", texto: "Desayuno" }, { valor: "comida", texto: "Comida" }, { valor: "merienda", texto: "Merienda" }, { valor: "cena", texto: "Cena" }, { valor: "extra", texto: "Extra" }]} />
                    <CampoTexto etiqueta="Raciones" modo="decimal" valor={f.raciones} alCambiar={(v: string) => setF({ ...f, raciones: v })} />
                    <CampoTexto etiqueta="Minutos" modo="numeric" valor={f.tiempo_min} alCambiar={(v: string) => setF({ ...f, tiempo_min: v })} />
                </div>
                <h3>Ingredientes (receta completa)</h3>
                {f.ingredientes.map((i: any, indice: number) => (
                    <div key={indice} className="fila" style={{ flexWrap: "nowrap" }}>
                        <select value={i.alimento_id} onChange={(e: any) => ingrediente(indice, "alimento_id", e.target.value)} aria-label="Alimento">
                            <option value="">—</option>
                            {(alimentos.datos ? alimentos.datos.alimentos : []).map((a: any) => <option key={a.id} value={a.id}>{a.nombre}{a.excluido ? " ⚠" : ""}</option>)}
                        </select>
                        <input style={{ width: 90 }} inputMode="decimal" value={i.cantidad} onChange={(e: any) => ingrediente(indice, "cantidad", e.target.value)} aria-label="Cantidad" />
                        <select style={{ width: 76 }} value={i.unidad} onChange={(e: any) => ingrediente(indice, "unidad", e.target.value)} aria-label="Unidad">
                            {["g", "kg", "ml", "l", "ud"].map((u: string) => <option key={u} value={u}>{u}</option>)}
                        </select>
                        <button className="pequeno" aria-label="Quitar ingrediente" onClick={() => setF({ ...f, ingredientes: f.ingredientes.filter((_: any, k: number) => k != indice) })}>✕</button>
                    </div>
                ))}
                <button onClick={() => setF({ ...f, ingredientes: [...f.ingredientes, { alimento_id: "", cantidad: "", unidad: "g" }] })}>+ Ingrediente</button>
                <label>Pasos (uno por línea)<textarea value={f.pasos} onChange={(e: any) => setF({ ...f, pasos: e.target.value })} /></label>
                <label>Conservación<textarea value={f.conservacion} onChange={(e: any) => setF({ ...f, conservacion: e.target.value })} /></label>
                <label>Sustituciones (una por línea)<textarea value={f.sustituciones} onChange={(e: any) => setF({ ...f, sustituciones: e.target.value })} /></label>
                <div className="fila">
                    <button className="primario" onClick={guardar}>Guardar</button>
                    <button onClick={props.alCerrar}>Cancelar</button>
                </div>
            </div>
        </Modal>
    );
}
