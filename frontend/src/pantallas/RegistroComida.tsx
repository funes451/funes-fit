import { useState } from "react";
import { api } from "../api";
import { CampoTexto, Modal, Nutrientes, useApp, useDatos } from "../componentes";
import { MOMENTOS, entradaNumero, uuid } from "../utilidades";

export async function marcarComoPrevisto(registrar: any, comida: any): Promise<void> {
    await registrar("consumo.crear", { id_cliente: `prev-${comida.id}`, tipo: "previsto", comida_planificada_id: comida.id });
}

export default function RegistroComida(props: any): any {
    const { registrar, avisar } = useApp();
    const comida: any = props.comida;
    const [modo, setModo] = useState<string>(comida ? "parcial" : "extra");
    const [proporcion, setProporcion] = useState<string>("50");
    const [descripcion, setDescripcion] = useState<string>("");
    const [kcal, setKcal] = useState<string>("");
    const [proteina, setProteina] = useState<string>("");
    const [cantidades, setCantidades] = useState<any>({});
    const receta: any = useDatos(comida ? `/api/recetas/${comida.receta_id}` : null);
    const alimentos: any = useDatos(modo == "extra" || modo == "diferente" ? "/api/alimentos" : null);
    const [alimentoExtra, setAlimentoExtra] = useState<string>("");
    const [gramosExtra, setGramosExtra] = useState<string>("");

    const guardar = async (): Promise<void> => {
        const carga: any = { id_cliente: uuid(), tipo: modo, descripcion: descripcion };
        if(comida){
            carga.comida_planificada_id = comida.id;
        }else{
            carga.fecha = props.fecha;
            carga.momento = props.momento || "extra";
        }
        if(modo == "parcial"){
            carga.proporcion = Number(proporcion) / 100;
        }else if(modo == "modificado"){
            const ingredientes: any[] = receta.datos.receta.ingredientes.map((i: any) => ({ alimento_id: i.alimento_id, unidad: i.unidad, cantidad: entradaNumero(cantidades[i.id] ?? String(i.cantidad * comida.factor)) ?? 0 }));
            carga.ingredientes = ingredientes.filter((i: any) => i.cantidad > 0);
        }else if(alimentoExtra && entradaNumero(gramosExtra)){
            carga.ingredientes = [{ alimento_id: Number(alimentoExtra), cantidad: entradaNumero(gramosExtra) }];
        }else if(kcal || proteina){
            carga.nutrientes = { kcal: entradaNumero(kcal), proteina: entradaNumero(proteina) };
        }
        if((modo == "diferente" || modo == "extra") && !descripcion && !carga.ingredientes){
            avisar("Escribe qué has comido o elige un alimento", "amarillo");
            return;
        }
        try {
            await registrar("consumo.crear", carga);
            avisar("Registrado");
            props.alGuardar();
        } catch (e: any) {
            avisar(e.message, "rojo");
        }
    };

    return (
        <Modal titulo={comida ? `Registrar ${MOMENTOS[comida.momento].toLowerCase()}` : "Añadir algo extra"} alCerrar={props.alCerrar}>
            {comida ? (
                <div className="pestanas" role="tablist">
                    {[["parcial", "Una parte"], ["modificado", "Otras cantidades"], ["diferente", "Otra cosa"]].map((p: any) => (
                        <button key={p[0]} className={modo == p[0] ? "activa" : ""} onClick={() => setModo(p[0])}>{p[1]}</button>
                    ))}
                </div>
            ) : null}
            {modo == "parcial" ? (
                <label>
                    Porcentaje comido: {proporcion} %
                    <input type="range" min="10" max="100" step="5" value={proporcion} onChange={(e: any) => setProporcion(e.target.value)} />
                </label>
            ) : null}
            {modo == "modificado" && receta.datos ? (
                <div className="columna">
                    {receta.datos.receta.ingredientes.map((i: any) => (
                        <CampoTexto key={i.id} etiqueta={`${i.nombre} (${i.unidad})`} modo="decimal" valor={cantidades[i.id] ?? String(Math.round(i.cantidad * comida.factor))} alCambiar={(v: string) => setCantidades({ ...cantidades, [i.id]: v })} />
                    ))}
                    <p className="suave">Pon 0 en lo que no hayas comido.</p>
                </div>
            ) : null}
            {modo == "diferente" || modo == "extra" ? (
                <div className="columna">
                    <CampoTexto etiqueta="¿Qué has comido?" valor={descripcion} alCambiar={setDescripcion} ejemplo="Ej.: bocadillo de tortilla" />
                    <p className="suave">Opcional: elige un alimento y su cantidad, o escribe kcal y proteína si las conoces. Puedes dejarlo solo con la descripción.</p>
                    {alimentos.datos ? (
                        <div className="rejilla-2">
                            <label>
                                Alimento
                                <select value={alimentoExtra} onChange={(e: any) => setAlimentoExtra(e.target.value)}>
                                    <option value="">—</option>
                                    {alimentos.datos.alimentos.map((a: any) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
                                </select>
                            </label>
                            <CampoTexto etiqueta="Cantidad (g/ml)" modo="decimal" valor={gramosExtra} alCambiar={setGramosExtra} />
                        </div>
                    ) : null}
                    <div className="rejilla-2">
                        <CampoTexto etiqueta="kcal (opcional)" modo="decimal" valor={kcal} alCambiar={setKcal} />
                        <CampoTexto etiqueta="Proteína g (opcional)" modo="decimal" valor={proteina} alCambiar={setProteina} />
                    </div>
                    {comida ? <p className="suave">La comida prevista se conserva en el menú: esto solo registra lo que comiste.</p> : null}
                </div>
            ) : null}
            {comida ? <p><Nutrientes n={comida.nutrientes} /> previstos</p> : null}
            <div className="fila" style={{ marginTop: 12 }}>
                <button className="primario" onClick={guardar}>Guardar</button>
                <button onClick={props.alCerrar}>Cancelar</button>
            </div>
        </Modal>
    );
}

export async function borrarConsumo(registrar: any, consumo: any): Promise<void> {
    await registrar("consumo.borrar", { id: consumo.id });
}

export function textoEstado(estado: string): string {
    const textos: any = {
        pendiente: "Sin registrar",
        comido_previsto: "Comido como estaba previsto",
        comido_diferente: "Comí otra cosa",
        parcial: "Comí una parte",
        modificado: "Cantidades cambiadas",
        registrado: "Registrado",
    };
    return textos[estado] || estado;
}

export function useCargaApi(): any {
    return api;
}
