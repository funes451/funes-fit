export const TIPOS_FUSIONABLES: string[] = ["sesion.guardar", "diario.guardar", "evento.guardar"];

export function claveFusion(tipo: string, carga: any): string | null {
    if(tipo == "sesion.guardar"){
        return `sesion:${carga.id_cliente}`;
    }
    if(tipo == "diario.guardar"){
        return `diario:${carga.fecha}`;
    }
    if(tipo == "evento.guardar"){
        return `evento:${carga.clave_plan || carga.id_cliente}`;
    }
    return null;
}

export function crearAlmacenMemoria(): any {
    const datos: Map<string, any> = new Map();
    return {
        todas: async (): Promise<any[]> => Array.from(datos.values()).sort((a: any, b: any) => a.creada - b.creada),
        guardar: async (op: any): Promise<void> => {
            datos.set(op.id_operacion, op);
        },
        borrar: async (id: string): Promise<void> => {
            datos.delete(id);
        },
    };
}

export function crearAlmacenIndexedDB(nombre: string): any {
    const abrir = (): Promise<IDBDatabase> => new Promise((resolver: any, rechazar: any) => {
        const solicitud: IDBOpenDBRequest = indexedDB.open(nombre, 1);
        solicitud.onupgradeneeded = () => {
            solicitud.result.createObjectStore("operaciones", { keyPath: "id_operacion" });
        };
        solicitud.onsuccess = () => resolver(solicitud.result);
        solicitud.onerror = () => rechazar(solicitud.error);
    });
    const transaccion = async (modo: IDBTransactionMode, accion: (almacen: IDBObjectStore) => IDBRequest): Promise<any> => {
        const bd: IDBDatabase = await abrir();
        return new Promise((resolver: any, rechazar: any) => {
            const tx: IDBTransaction = bd.transaction("operaciones", modo);
            const solicitud: IDBRequest = accion(tx.objectStore("operaciones"));
            tx.oncomplete = () => {
                bd.close();
                resolver(solicitud.result);
            };
            tx.onerror = () => {
                bd.close();
                rechazar(tx.error);
            };
        });
    };
    return {
        todas: async (): Promise<any[]> => {
            const lista: any[] = await transaccion("readonly", (a: IDBObjectStore) => a.getAll());
            return lista.sort((a: any, b: any) => a.creada - b.creada);
        },
        guardar: async (op: any): Promise<void> => {
            await transaccion("readwrite", (a: IDBObjectStore) => a.put(op));
        },
        borrar: async (id: string): Promise<void> => {
            await transaccion("readwrite", (a: IDBObjectStore) => a.delete(id));
        },
    };
}

export function crearCola(usuarioId: number, almacen: any, enviar: (cuerpo: any) => Promise<any>, generarId: () => string): any {
    const oyentes: Set<(estado: any) => void> = new Set();
    const versiones: Map<string, number> = new Map();
    let enviando: boolean = false;
    let ultimoError: string | null = null;

    const estado = async (): Promise<any> => {
        const ops: any[] = await almacen.todas();
        return {
            pendientes: ops.filter((o: any) => o.estado == "pendiente").length,
            errores: ops.filter((o: any) => o.estado == "error"),
            enviando: enviando,
            ultimoError: ultimoError,
        };
    };

    const avisar = async (): Promise<void> => {
        const actual: any = await estado();
        oyentes.forEach((f: (estado: any) => void) => f(actual));
    };

    const encolar = async (tipo: string, carga: any): Promise<any> => {
        const clave: string | null = claveFusion(tipo, carga);
        if(clave != null && versiones.has(clave) && (carga.version_base ?? 0) < (versiones.get(clave) as number)){
            carga = { ...carga, version_base: versiones.get(clave) };
        }
        if(clave != null){
            const ops: any[] = await almacen.todas();
            const previa: any = ops.find((o: any) => o.clave_fusion == clave && o.estado == "pendiente" && !o.en_vuelo);
            if(previa){
                previa.carga = { ...carga, version_base: previa.carga.version_base ?? carga.version_base };
                previa.actualizada = Date.now();
                await almacen.guardar(previa);
                await avisar();
                return previa;
            }
        }
        const op: any = { id_operacion: generarId(), tipo: tipo, carga: carga, creada: Date.now(), intentos: 0, estado: "pendiente", error: null, clave_fusion: clave, usuario_id: usuarioId };
        await almacen.guardar(op);
        await avisar();
        return op;
    };

    const vaciarInterno = async (profundidad: number): Promise<any[]> => {
        if(enviando){
            return [];
        }
        const ops: any[] = (await almacen.todas()).filter((o: any) => o.estado == "pendiente" && o.usuario_id == usuarioId);
        if(ops.length == 0){
            return [];
        }
        enviando = true;
        await avisar();
        const vistas: Set<string> = new Set();
        const lote: any[] = [];
        for(const o of ops){
            if(o.clave_fusion){
                if(vistas.has(o.clave_fusion)){
                    continue;
                }
                vistas.add(o.clave_fusion);
            }
            if(lote.length < 100){
                lote.push(o);
            }
        }
        for(const o of lote){
            o.en_vuelo = true;
            await almacen.guardar(o);
        }
        let resultados: any[] = [];
        try {
            const respuesta: any = await enviar({ usuario_id: usuarioId, operaciones: lote.map((o: any) => ({ id_operacion: o.id_operacion, tipo: o.tipo, carga: o.carga })) });
            resultados = respuesta.resultados || [];
            ultimoError = null;
            for(const r of resultados){
                const op: any = lote.find((o: any) => o.id_operacion == r.id_operacion);
                if(!op){
                    continue;
                }
                if(r.estado == "aplicada" || r.estado == "duplicada" || r.estado == "conflicto"){
                    await almacen.borrar(op.id_operacion);
                    const entidad: any = r.resultado && (r.resultado.sesion || r.resultado.diario || r.resultado.evento);
                    if(r.estado == "aplicada" && entidad && op.clave_fusion){
                        versiones.set(op.clave_fusion, entidad.version);
                        const siguientes: any[] = (await almacen.todas()).filter((o: any) => o.clave_fusion == op.clave_fusion && o.estado == "pendiente" && o.id_operacion != op.id_operacion);
                        for(const s of siguientes){
                            s.carga = { ...s.carga, version_base: entidad.version };
                            await almacen.guardar(s);
                        }
                    }
                }else{
                    op.estado = "error";
                    op.en_vuelo = false;
                    op.error = (r.resultado && r.resultado.error) || "Error al guardar";
                    await almacen.guardar(op);
                }
            }
        } catch (error: any) {
            ultimoError = error && error.message ? error.message : "Sin conexión";
            for(const o of lote){
                o.en_vuelo = false;
                o.intentos = o.intentos + 1;
                if(error && error.estado == 409){
                    o.estado = "error";
                    o.error = error.message;
                }
                await almacen.guardar(o);
            }
        } finally {
            enviando = false;
            await avisar();
        }
        const quedan: any[] = (await almacen.todas()).filter((o: any) => o.estado == "pendiente" && o.usuario_id == usuarioId);
        if(ultimoError == null && quedan.length > 0 && resultados.length > 0 && profundidad < 5){
            return resultados.concat(await vaciarInterno(profundidad + 1));
        }
        return resultados;
    };

    const vaciar = async (): Promise<any[]> => vaciarInterno(0);

    const reintentar = async (id: string): Promise<void> => {
        const op: any = (await almacen.todas()).find((o: any) => o.id_operacion == id);
        if(op){
            op.estado = "pendiente";
            op.error = null;
            await almacen.guardar(op);
            await avisar();
        }
    };

    const descartar = async (id: string): Promise<void> => {
        await almacen.borrar(id);
        await avisar();
    };

    return {
        usuarioId: usuarioId,
        encolar: encolar,
        vaciar: vaciar,
        estado: estado,
        reintentar: reintentar,
        descartar: descartar,
        suscribir: (f: (estado: any) => void): (() => void) => {
            oyentes.add(f);
            return () => oyentes.delete(f);
        },
    };
}
