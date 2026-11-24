export class ErrorApi extends Error {
    estado: number;
    datos: any;

    constructor(mensaje: string, estado: number, datos: any) {
        super(mensaje);
        this.estado = estado;
        this.datos = datos;
    }
}

export const estadoRed: any = { desdeCache: false, ultimaCache: null };

function mensajeDe(datos: any, estado: number): string {
    if(datos && typeof datos.detail == "string"){
        return datos.detail;
    }
    if(datos && Array.isArray(datos.detail)){
        return "Revisa los datos introducidos";
    }
    if(estado == 0){
        return "Sin conexión con el servidor";
    }
    return `Error ${estado}`;
}

export async function peticion(metodo: string, ruta: string, cuerpo?: any): Promise<any> {
    const opciones: any = { method: metodo, credentials: "same-origin", headers: { "X-Funes": "1" } };
    if(cuerpo instanceof FormData){
        opciones.body = cuerpo;
    }else if(cuerpo != undefined){
        opciones.headers["Content-Type"] = "application/json";
        opciones.body = JSON.stringify(cuerpo);
    }
    let respuesta: Response;
    try {
        respuesta = await fetch(ruta, opciones);
    } catch (error) {
        throw new ErrorApi("Sin conexión con el servidor", 0, null);
    }
    if(metodo == "GET"){
        estadoRed.desdeCache = respuesta.headers.get("x-desde-cache") == "1";
        if(estadoRed.desdeCache){
            estadoRed.ultimaCache = respuesta.headers.get("x-guardado-en");
        }
        window.dispatchEvent(new CustomEvent("estado-red"));
    }
    const tipo: string = respuesta.headers.get("content-type") || "";
    const datos: any = tipo.includes("application/json") ? await respuesta.json() : await respuesta.text();
    if(!respuesta.ok){
        if(respuesta.status == 401 && !ruta.startsWith("/api/auth/")){
            window.dispatchEvent(new CustomEvent("sesion-caducada"));
        }
        throw new ErrorApi(mensajeDe(datos, respuesta.status), respuesta.status, datos);
    }
    return datos;
}

export const api: any = {
    get: (ruta: string): Promise<any> => peticion("GET", ruta),
    post: (ruta: string, cuerpo?: any): Promise<any> => peticion("POST", ruta, cuerpo ?? {}),
    put: (ruta: string, cuerpo?: any): Promise<any> => peticion("PUT", ruta, cuerpo ?? {}),
    patch: (ruta: string, cuerpo?: any): Promise<any> => peticion("PATCH", ruta, cuerpo ?? {}),
    borrar: (ruta: string): Promise<any> => peticion("DELETE", ruta),
};

export async function descargar(ruta: string, nombre: string): Promise<void> {
    const respuesta: Response = await fetch(ruta, { credentials: "same-origin" });
    if(!respuesta.ok){
        throw new ErrorApi("No se pudo descargar", respuesta.status, null);
    }
    const blob: Blob = await respuesta.blob();
    const enlace: HTMLAnchorElement = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
    setTimeout(() => URL.revokeObjectURL(enlace.href), 2000);
}
