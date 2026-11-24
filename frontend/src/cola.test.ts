import { describe, expect, it } from "vitest";
import "fake-indexeddb/auto";
import { crearAlmacenIndexedDB, crearAlmacenMemoria, crearCola } from "./cola";

function servidorFalso(): any {
    const aplicadas: Set<string> = new Set();
    const versiones: Map<string, number> = new Map();
    const estado: any = { caido: false, recibidas: [] as any[], aplicadas: aplicadas };
    estado.enviar = async (cuerpo: any): Promise<any> => {
        if(estado.caido){
            throw new Error("Sin conexión");
        }
        estado.recibidas.push(cuerpo);
        return {
            resultados: cuerpo.operaciones.map((o: any) => {
                if(aplicadas.has(o.id_operacion)){
                    return { id_operacion: o.id_operacion, estado: "duplicada" };
                }
                if(o.tipo == "diario.guardar"){
                    const actual: number = versiones.get(o.carga.fecha) || 0;
                    if((o.carga.version_base || 0) != actual){
                        return { id_operacion: o.id_operacion, estado: "conflicto", resultado: {} };
                    }
                    versiones.set(o.carga.fecha, actual + 1);
                    aplicadas.add(o.id_operacion);
                    return { id_operacion: o.id_operacion, estado: "aplicada", resultado: { diario: { version: actual + 1 } } };
                }
                aplicadas.add(o.id_operacion);
                return { id_operacion: o.id_operacion, estado: "aplicada", resultado: {} };
            }),
        };
    };
    return estado;
}

let contador: number = 0;
const generar = (): string => {
    contador = contador + 1;
    return `op-${contador}`;
};

describe("cola offline", () => {
    it("guarda sin conexión y envía una sola vez al reconectar", async () => {
        const servidor: any = servidorFalso();
        const cola: any = crearCola(1, crearAlmacenMemoria(), servidor.enviar, generar);
        servidor.caido = true;
        await cola.encolar("medicion.crear", { id_cliente: "m1", tipo: "peso", valor: 111.8 });
        await cola.vaciar();
        expect((await cola.estado()).pendientes).toBe(1);
        servidor.caido = false;
        await cola.vaciar();
        await cola.vaciar();
        expect((await cola.estado()).pendientes).toBe(0);
        expect(servidor.aplicadas.size).toBe(1);
        expect(servidor.recibidas.length).toBe(1);
    });

    it("fusiona guardados repetidos de la misma sesión", async () => {
        const servidor: any = servidorFalso();
        const cola: any = crearCola(1, crearAlmacenMemoria(), servidor.enviar, generar);
        servidor.caido = true;
        await cola.encolar("diario.guardar", { fecha: "2026-11-24", datos: { pasos: 1000 }, version_base: 0 });
        await cola.encolar("diario.guardar", { fecha: "2026-11-24", datos: { pasos: 5000 }, version_base: 0 });
        expect((await cola.estado()).pendientes).toBe(1);
        servidor.caido = false;
        await cola.vaciar();
        expect(servidor.recibidas[0].operaciones[0].carga.datos.pasos).toBe(5000);
    });

    it("actualiza la versión base de guardados posteriores", async () => {
        const servidor: any = servidorFalso();
        const almacen: any = crearAlmacenMemoria();
        const cola: any = crearCola(1, almacen, servidor.enviar, generar);
        await cola.encolar("diario.guardar", { fecha: "2026-11-25", datos: { pasos: 1 }, version_base: 0 });
        const ops: any[] = await almacen.todas();
        ops[0].en_vuelo = true;
        await almacen.guardar(ops[0]);
        await cola.encolar("diario.guardar", { fecha: "2026-11-25", datos: { pasos: 2 }, version_base: 0 });
        ops[0].en_vuelo = false;
        await almacen.guardar(ops[0]);
        await cola.vaciar();
        expect(servidor.aplicadas.size).toBe(2);
        expect(servidor.recibidas.length).toBe(2);
        expect(servidor.recibidas[1].operaciones[0].carga.version_base).toBe(1);
        expect((await cola.estado()).pendientes).toBe(0);
    });

    it("cada cuenta tiene su propia cola en IndexedDB", async () => {
        const servidor: any = servidorFalso();
        const colaA: any = crearCola(1, crearAlmacenIndexedDB("funesfit-cola-1"), servidor.enviar, generar);
        await colaA.encolar("medicion.crear", { id_cliente: "a" });
        const colaB: any = crearCola(2, crearAlmacenIndexedDB("funesfit-cola-2"), servidor.enviar, generar);
        expect((await colaB.estado()).pendientes).toBe(0);
        await colaB.vaciar();
        expect(servidor.recibidas.length).toBe(0);
        await colaA.vaciar();
        expect(servidor.recibidas[0].usuario_id).toBe(1);
    });

    it("conserva los errores para reintentar o descartar", async () => {
        const cola: any = crearCola(1, crearAlmacenMemoria(), async (cuerpo: any) => ({ resultados: cuerpo.operaciones.map((o: any) => ({ id_operacion: o.id_operacion, estado: "error", resultado: { error: "Peso fuera de rango" } })) }), generar);
        await cola.encolar("medicion.crear", { valor: 9999 });
        await cola.vaciar();
        const estado: any = await cola.estado();
        expect(estado.errores[0].error).toBe("Peso fuera de rango");
        await cola.descartar(estado.errores[0].id_operacion);
        expect((await cola.estado()).errores.length).toBe(0);
    });
});
