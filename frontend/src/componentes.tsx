import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

export const Contexto = createContext<any>(null);

export function useApp(): any {
    return useContext(Contexto);
}

export function useDatos(ruta: string | null, dependencias: any[] = []): any {
    const [datos, setDatos] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [cargando, setCargando] = useState<boolean>(true);
    const [version, setVersion] = useState<number>(0);
    useEffect(() => {
        let activo: boolean = true;
        if(ruta == null){
            setCargando(false);
            return;
        }
        setCargando(true);
        api.get(ruta).then((r: any) => {
            if(activo){
                setDatos(r);
                setError(null);
            }
        }).catch((e: any) => {
            if(activo){
                setError(e.message);
            }
        }).finally(() => {
            if(activo){
                setCargando(false);
            }
        });
        return () => {
            activo = false;
        };
    }, [ruta, version, ...dependencias]);
    return { datos: datos, error: error, cargando: cargando, recargar: () => setVersion((v: number) => v + 1), setDatos: setDatos };
}

export function Modal(props: any): any {
    useEffect(() => {
        const tecla = (e: KeyboardEvent): void => {
            if(e.key == "Escape"){
                props.alCerrar();
            }
        };
        window.addEventListener("keydown", tecla);
        return () => window.removeEventListener("keydown", tecla);
    }, []);
    return (
        <div className="fondo-modal" onClick={props.alCerrar}>
            <div className="modal" role="dialog" aria-modal="true" aria-label={props.titulo} onClick={(e: any) => e.stopPropagation()}>
                <div className="fila separada">
                    <h2>{props.titulo}</h2>
                    <button className="enlace" onClick={props.alCerrar} aria-label="Cerrar">Cerrar</button>
                </div>
                {props.children}
            </div>
        </div>
    );
}

export function Cargando(props: any): any {
    if(props.error){
        return <div className="aviso rojo">{props.error}</div>;
    }
    return <p className="suave">Cargando…</p>;
}

export function Nutrientes(props: any): any {
    const n: any = props.n || {};
    const { perfil } = useApp();
    if(perfil && perfil.modo_registro == "sin_calorias" && !props.forzar){
        return null;
    }
    const f = (v: any): string => (v == null ? "—" : Math.round(v).toLocaleString("es-ES"));
    return (
        <span className="suave">
            {f(n.kcal)} kcal · P {f(n.proteina)} g · H {f(n.hidratos)} g · G {f(n.grasas)} g{n.fibra != null ? ` · fibra ${f(n.fibra)} g` : ""}
        </span>
    );
}

export function Confianza(props: any): any {
    const textos: any = {
        etiqueta_verificada: "Etiqueta verificada",
        base_generica: "Valores genéricos estimados",
        incluye_estimacion_manual: "Incluye estimación manual",
        sin_datos: "Sin datos",
    };
    return <span className="etiqueta">{textos[props.valor] || props.valor}</span>;
}

export function CampoTexto(props: any): any {
    return (
        <label>
            {props.etiqueta}
            <input
                type={props.tipo || "text"}
                inputMode={props.modo}
                value={props.valor ?? ""}
                placeholder={props.ejemplo}
                onChange={(e: any) => props.alCambiar(e.target.value)}
                autoComplete={props.autocompletar}
                required={props.obligatorio}
            />
        </label>
    );
}

export function Selector(props: any): any {
    return (
        <label>
            {props.etiqueta}
            <select value={props.valor ?? ""} onChange={(e: any) => props.alCambiar(e.target.value)}>
                {props.vacio ? <option value="">{props.vacio}</option> : null}
                {props.opciones.map((o: any) => (
                    <option key={o.valor} value={o.valor}>{o.texto}</option>
                ))}
            </select>
        </label>
    );
}

export function GraficaLinea(props: any): any {
    const puntos: any[] = props.puntos || [];
    const medias: any[] = props.medias || [];
    const todos: number[] = puntos.map((p: any) => p.valor).concat(medias.map((m: any) => m.valor)).concat(props.lineas || []);
    if(puntos.length == 0){
        return <p className="suave">Sin datos todavía. La gráfica no se rellena con valores inventados.</p>;
    }
    const fechas: number[] = puntos.map((p: any) => new Date(p.fecha).getTime()).concat(medias.map((m: any) => new Date(m.fecha).getTime()));
    const minF: number = Math.min(...fechas);
    const maxF: number = Math.max(...fechas, minF + 86400000);
    const minV: number = Math.min(...todos) - 0.5;
    const maxV: number = Math.max(...todos) + 0.5;
    const ancho: number = 600;
    const alto: number = 220;
    const x = (f: string): number => 40 + ((new Date(f).getTime() - minF) / (maxF - minF)) * (ancho - 60);
    const y = (v: number): number => 10 + (1 - (v - minV) / (maxV - minV)) * (alto - 40);
    const camino: string = medias.map((m: any, i: number) => `${i == 0 ? "M" : "L"}${x(m.fecha)},${y(m.valor)}`).join(" ");
    return (
        <svg className="grafica" viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={props.descripcion}>
            <line x1="40" x2={ancho - 20} y1={alto - 30} y2={alto - 30} stroke="var(--borde)" />
            <text x="4" y={y(maxV - 0.5) + 4} fontSize="12" fill="var(--texto-suave)">{(maxV - 0.5).toLocaleString("es-ES", { maximumFractionDigits: 1 })}</text>
            <text x="4" y={y(minV + 0.5) + 4} fontSize="12" fill="var(--texto-suave)">{(minV + 0.5).toLocaleString("es-ES", { maximumFractionDigits: 1 })}</text>
            {(props.lineas || []).map((l: number) => (
                <g key={l}>
                    <line x1="40" x2={ancho - 20} y1={y(l)} y2={y(l)} stroke="var(--acento)" strokeDasharray="4 4" />
                    <text x={ancho - 60} y={y(l) - 4} fontSize="12" fill="var(--acento)">{l} kg</text>
                </g>
            ))}
            {puntos.map((p: any, i: number) => (
                <circle key={i} cx={x(p.fecha)} cy={y(p.valor)} r="4" fill="var(--texto-suave)" opacity="0.6" />
            ))}
            {camino ? <path d={camino} fill="none" stroke="var(--primario)" strokeWidth="3" /> : null}
            <text x="40" y={alto - 10} fontSize="12" fill="var(--texto-suave)">{new Date(minF).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" })}</text>
            <text x={ancho - 70} y={alto - 10} fontSize="12" fill="var(--texto-suave)">{new Date(maxF).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" })}</text>
        </svg>
    );
}
