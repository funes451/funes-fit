const VERSION = "funesfit-v1";
const CACHE_APP = `${VERSION}-app`;
const CACHE_CUENTA = "funesfit-cuenta";
const PREFIJO_API = "funesfit-api-";
const ESENCIALES = ["/", "/index.html", "/manifest.webmanifest", "/iconos/icono-192.png", "/iconos/icono-512.png"];
const API_SIN_CACHE = ["/api/auth/", "/api/sync", "/api/exportar/", "/api/fotos/", "/api/invitaciones/"];

self.addEventListener("install", (evento) => {
    evento.waitUntil(caches.open(CACHE_APP).then((cache) => cache.addAll(ESENCIALES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
    evento.waitUntil(
        caches.keys().then((claves) => Promise.all(claves.filter((c) => c.startsWith("funesfit-v") && !c.startsWith(VERSION)).map((c) => caches.delete(c)))).then(() => self.clients.claim())
    );
});

async function usuarioActual() {
    const cache = await caches.open(CACHE_CUENTA);
    const respuesta = await cache.match("/__usuario");
    if(!respuesta){
        return null;
    }
    const texto = await respuesta.text();
    return texto == "" ? null : texto;
}

async function fijarUsuario(id) {
    const cache = await caches.open(CACHE_CUENTA);
    const anterior = await usuarioActual();
    if(anterior != id){
        const claves = await caches.keys();
        await Promise.all(claves.filter((c) => c.startsWith(PREFIJO_API)).map((c) => caches.delete(c)));
    }
    await cache.put("/__usuario", new Response(id == null ? "" : String(id)));
}

self.addEventListener("message", (evento) => {
    const datos = evento.data || {};
    if(datos.tipo == "usuario"){
        evento.waitUntil(fijarUsuario(datos.id));
    }
    if(datos.tipo == "actualizar"){
        self.skipWaiting();
    }
});

async function redPrimeroApi(peticion) {
    const usuario = await usuarioActual();
    try {
        const respuesta = await fetch(peticion);
        if(respuesta.ok && usuario){
            const copia = respuesta.clone();
            const cuerpo = await copia.blob();
            const cabeceras = new Headers(copia.headers);
            cabeceras.set("x-guardado-en", new Date().toISOString());
            const cache = await caches.open(PREFIJO_API + usuario);
            await cache.put(peticion, new Response(cuerpo, { status: 200, headers: cabeceras }));
        }
        return respuesta;
    } catch (error) {
        if(usuario){
            const cache = await caches.open(PREFIJO_API + usuario);
            const guardada = await cache.match(peticion);
            if(guardada){
                const cabeceras = new Headers(guardada.headers);
                cabeceras.set("x-desde-cache", "1");
                return new Response(await guardada.blob(), { status: 200, headers: cabeceras });
            }
        }
        return new Response(JSON.stringify({ detail: "Sin conexión y sin copia guardada de estos datos" }), { status: 503, headers: { "Content-Type": "application/json" } });
    }
}

async function navegacion(peticion) {
    try {
        const respuesta = await fetch(peticion);
        const cache = await caches.open(CACHE_APP);
        cache.put("/index.html", respuesta.clone());
        return respuesta;
    } catch (error) {
        const cache = await caches.open(CACHE_APP);
        return (await cache.match("/index.html")) || (await cache.match("/"));
    }
}

async function recursoEstatico(peticion) {
    const cache = await caches.open(CACHE_APP);
    const guardada = await cache.match(peticion);
    if(guardada){
        return guardada;
    }
    const respuesta = await fetch(peticion);
    if(respuesta.ok){
        cache.put(peticion, respuesta.clone());
    }
    return respuesta;
}

self.addEventListener("fetch", (evento) => {
    const peticion = evento.request;
    const url = new URL(peticion.url);
    if(url.origin != self.location.origin || peticion.method != "GET"){
        return;
    }
    if(url.pathname.startsWith("/api/")){
        if(API_SIN_CACHE.some((p) => url.pathname.startsWith(p))){
            return;
        }
        evento.respondWith(redPrimeroApi(peticion));
        return;
    }
    if(peticion.mode == "navigate"){
        evento.respondWith(navegacion(peticion));
        return;
    }
    if(url.pathname.startsWith("/assets/") || url.pathname.startsWith("/iconos/")){
        evento.respondWith(recursoEstatico(peticion));
    }
});

self.addEventListener("push", (evento) => {
    let datos = {};
    try {
        datos = evento.data ? evento.data.json() : {};
    } catch (error) {
        datos = {};
    }
    evento.waitUntil(
        usuarioActual().then((usuario) => {
            const coincide = usuario != null && String(datos.usuario) == usuario;
            const cuerpo = coincide ? datos.cuerpo || "Tienes un recordatorio" : "Tienes un recordatorio en Funes Fit";
            return self.registration.showNotification(datos.titulo || "Funes Fit", { body: cuerpo, icon: "/iconos/icono-192.png", badge: "/iconos/icono-192.png", tag: datos.tipo || "funesfit", data: { url: datos.url || "/" } });
        })
    );
});

self.addEventListener("notificationclick", (evento) => {
    evento.notification.close();
    const destino = (evento.notification.data && evento.notification.data.url) || "/";
    evento.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ventanas) => {
            for(const ventana of ventanas){
                if("focus" in ventana){
                    return ventana.focus();
                }
            }
            return self.clients.openWindow(destino);
        })
    );
});
