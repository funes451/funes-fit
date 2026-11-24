export const NOMBRES_DIAS: string[] = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
export const DIAS_CORTOS: string[] = ["L", "M", "X", "J", "V", "S", "D"];
export const MOMENTOS: any = { desayuno: "Desayuno", comida: "Comida", merienda: "Merienda", cena: "Cena", extra: "Extra" };

export function uuid(): string {
    if(typeof crypto != "undefined" && (crypto as any).randomUUID){
        return (crypto as any).randomUUID();
    }
    let resultado: string = "";
    for(let i = 0; i < 32; i = i + 1){
        resultado = resultado + Math.floor(Math.random() * 16).toString(16);
    }
    return resultado;
}

export function numero(valor: number | null | undefined, decimales: number = 0): string {
    if(valor == null || Number.isNaN(valor)){
        return "—";
    }
    return valor.toLocaleString("es-ES", { maximumFractionDigits: decimales, minimumFractionDigits: 0 });
}

export function euros(valor: number | null | undefined): string {
    if(valor == null){
        return "sin precio";
    }
    return valor.toLocaleString("es-ES", { style: "currency", currency: "EUR" });
}

export function cantidad(valor: number | null | undefined, unidad: string): string {
    if(valor == null){
        return "—";
    }
    if(unidad == "g" && valor >= 1000){
        return `${numero(valor / 1000, 2)} kg`;
    }
    if(unidad == "ml" && valor >= 1000){
        return `${numero(valor / 1000, 2)} l`;
    }
    return `${numero(valor, 0)} ${unidad}`;
}

export function fechaIso(fecha: Date): string {
    const anio: number = fecha.getFullYear();
    const mes: string = String(fecha.getMonth() + 1).padStart(2, "0");
    const dia: string = String(fecha.getDate()).padStart(2, "0");
    return `${anio}-${mes}-${dia}`;
}

export function desdeIso(iso: string): Date {
    const partes: number[] = iso.split("-").map(Number);
    return new Date(partes[0], partes[1] - 1, partes[2]);
}

export function sumarDias(iso: string, dias: number): string {
    const fecha: Date = desdeIso(iso);
    fecha.setDate(fecha.getDate() + dias);
    return fechaIso(fecha);
}

export function lunesDe(iso: string): string {
    const fecha: Date = desdeIso(iso);
    const dia: number = (fecha.getDay() + 6) % 7;
    return sumarDias(iso, -dia);
}

export function diaSemana(iso: string): number {
    return (desdeIso(iso).getDay() + 6) % 7;
}

export function textoFecha(iso: string, conAnio: boolean = false): string {
    const fecha: Date = desdeIso(iso);
    const opciones: any = { weekday: "long", day: "numeric", month: "long" };
    if(conAnio){
        opciones.year = "numeric";
    }
    return fecha.toLocaleDateString("es-ES", opciones);
}

export function fechaCorta(iso: string): string {
    return desdeIso(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" });
}

export function entradaNumero(texto: string): number | null {
    const limpio: string = (texto || "").trim().replace(/\s/g, "");
    if(limpio == ""){
        return null;
    }
    const normal: string = limpio.includes(",") ? limpio.replace(/\./g, "").replace(",", ".") : limpio;
    const valor: number = Number(normal);
    return Number.isFinite(valor) ? valor : null;
}

export function textoNumeroEntrada(valor: number | null | undefined): string {
    if(valor == null){
        return "";
    }
    return String(valor).replace(".", ",");
}
