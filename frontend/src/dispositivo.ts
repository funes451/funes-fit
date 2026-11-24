import { api } from "./api";
import { crearAlmacenIndexedDB, crearCola } from "./cola";
import { uuid } from "./utilidades";

let colaActiva: any = null;

export function idDispositivo(): string {
    let id: string | null = null;
    try {
        id = localStorage.getItem("funesfit-dispositivo");
        if(!id){
            id = uuid();
            localStorage.setItem("funesfit-dispositivo", id);
        }
    } catch (error) {
        id = "sin-almacenamiento";
    }
    return id as string;
}

export async function registrarServiceWorker(): Promise<void> {
    if("serviceWorker" in navigator){
        try {
            await navigator.serviceWorker.register("/sw.js");
        } catch (error) {
            console.log(`No se pudo registrar el service worker: ${error}`);
        }
    }
}

export async function avisarUsuarioAlServiceWorker(id: number | null): Promise<void> {
    if(!("serviceWorker" in navigator)){
        return;
    }
    const registro: ServiceWorkerRegistration | undefined = await navigator.serviceWorker.getRegistration();
    const trabajador: ServiceWorker | null | undefined = registro?.active || registro?.waiting || registro?.installing;
    trabajador?.postMessage({ tipo: "usuario", id: id });
    if(id == null && "caches" in window){
        const claves: string[] = await caches.keys();
        await Promise.all(claves.filter((c: string) => c.startsWith("funesfit-api-")).map((c: string) => caches.delete(c)));
    }
}

export function activarCola(usuarioId: number): any {
    if(colaActiva && colaActiva.usuarioId == usuarioId){
        return colaActiva;
    }
    colaActiva = crearCola(usuarioId, crearAlmacenIndexedDB(`funesfit-cola-${usuarioId}`), (cuerpo: any) => api.post("/api/sync", cuerpo), uuid);
    return colaActiva;
}

export function cola(): any {
    return colaActiva;
}

export function desactivarCola(): void {
    colaActiva = null;
}

export async function registrar(tipo: string, carga: any): Promise<void> {
    if(!colaActiva){
        throw new Error("No hay sesión activa");
    }
    await colaActiva.encolar(tipo, carga);
    if(navigator.onLine){
        await colaActiva.vaciar();
    }
}

function base64AUint8(base64: string): Uint8Array {
    const relleno: string = "=".repeat((4 - (base64.length % 4)) % 4);
    const normal: string = (base64 + relleno).replace(/-/g, "+").replace(/_/g, "/");
    const binario: string = atob(normal);
    const resultado: Uint8Array = new Uint8Array(binario.length);
    for(let i = 0; i < binario.length; i = i + 1){
        resultado[i] = binario.charCodeAt(i);
    }
    return resultado;
}

export function compatibilidadPush(): any {
    const esIos: boolean = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const instalada: boolean = window.matchMedia("(display-mode: standalone)").matches || (navigator as any).standalone == true;
    const soporta: boolean = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
    let motivo: string | null = null;
    if(!soporta){
        motivo = esIos && !instalada ? "En iPhone los avisos web solo funcionan con la app añadida a la pantalla de inicio (iOS 16.4 o posterior)." : "Este navegador no admite avisos web.";
    }else if(esIos && !instalada){
        motivo = "En iPhone, añade primero la app a la pantalla de inicio y ábrela desde allí.";
    }
    return { soporta: soporta && motivo == null, motivo: motivo, permiso: "Notification" in window ? Notification.permission : "no-disponible", esIos: esIos, instalada: instalada };
}

export async function activarPush(clavePublica: string): Promise<void> {
    const permiso: NotificationPermission = await Notification.requestPermission();
    if(permiso != "granted"){
        throw new Error("Permiso de notificaciones denegado. Puedes cambiarlo en los ajustes del navegador.");
    }
    const registro: ServiceWorkerRegistration = await navigator.serviceWorker.ready;
    let suscripcion: PushSubscription | null = await registro.pushManager.getSubscription();
    if(!suscripcion){
        suscripcion = await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: base64AUint8(clavePublica) as any });
    }
    const datos: any = suscripcion.toJSON();
    await api.post("/api/avisos/suscripciones", { endpoint: datos.endpoint, keys: datos.keys, dispositivo: idDispositivo(), agente: navigator.userAgent });
}

export async function desactivarPush(): Promise<void> {
    if(!("serviceWorker" in navigator)){
        return;
    }
    const registro: ServiceWorkerRegistration | undefined = await navigator.serviceWorker.getRegistration();
    const suscripcion: PushSubscription | null | undefined = await registro?.pushManager.getSubscription();
    if(suscripcion){
        try {
            await api.post("/api/avisos/suscripciones/borrar", { endpoint: suscripcion.endpoint });
        } catch (error) {
            console.log(`No se pudo borrar la suscripción en el servidor: ${error}`);
        }
        await suscripcion.unsubscribe();
    }
}
