import { useEffect, useState } from "react";
import { api, estadoRed } from "./api";
import { Contexto } from "./componentes";
import { activarCola, avisarUsuarioAlServiceWorker, cola, desactivarCola, desactivarPush, registrar } from "./dispositivo";
import Acceso from "./pantallas/Acceso";
import Admin from "./pantallas/Admin";
import Compra from "./pantallas/Compra";
import Gym from "./pantallas/Gym";
import Hoy from "./pantallas/Hoy";
import Menu from "./pantallas/Menu";
import Perfil from "./pantallas/Perfil";
import Progreso from "./pantallas/Progreso";

const SECCIONES: any[] = [
    { ruta: "/", texto: "Hoy", icono: "☀" },
    { ruta: "/menu", texto: "Menú", icono: "🍽" },
    { ruta: "/gym", texto: "Gym", icono: "🏋" },
    { ruta: "/compra", texto: "Compra", icono: "🛒" },
    { ruta: "/progreso", texto: "Progreso", icono: "📈" },
];

function rutaActual(): string {
    const hash: string = window.location.hash.replace(/^#/, "");
    return hash == "" ? "/" : hash;
}

function aplicarTema(tema: string): void {
    const oscuro: boolean = tema == "oscuro" || (tema == "sistema" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.tema = oscuro ? "oscuro" : "claro";
}

function EstadoSync(props: any): any {
    const { sync, enLinea } = props;
    if(!enLinea){
        return <span className="estado-sync sin-conexion" role="status">Sin conexión{sync && sync.pendientes ? ` · ${sync.pendientes} pendientes` : ""}</span>;
    }
    if(sync && sync.errores && sync.errores.length > 0){
        return <a href="#/perfil" className="estado-sync sin-conexion" role="status">{sync.errores.length} sin guardar</a>;
    }
    if(sync && (sync.pendientes > 0 || sync.enviando)){
        return <span className="estado-sync pendiente" role="status">Sincronizando {sync.pendientes}…</span>;
    }
    return <span className="estado-sync" role="status">{estadoRed.desdeCache ? "Datos guardados" : "Sincronizado"}</span>;
}

export default function App(): any {
    const [ruta, setRuta] = useState<string>(rutaActual());
    const [usuario, setUsuario] = useState<any>(undefined);
    const [perfil, setPerfil] = useState<any>(null);
    const [sync, setSync] = useState<any>(null);
    const [enLinea, setEnLinea] = useState<boolean>(navigator.onLine);
    const [mensaje, setMensaje] = useState<any>(null);
    const [, setTic] = useState<number>(0);

    const cargarPerfil = async (): Promise<void> => {
        try {
            const datos: any = await api.get("/api/perfil");
            setPerfil(datos.perfil);
            aplicarTema(datos.perfil.tema);
        } catch (error) {
            console.log(`Perfil no disponible: ${error}`);
        }
    };

    const entrar = async (datosUsuario: any): Promise<void> => {
        setUsuario(datosUsuario);
        const c: any = activarCola(datosUsuario.id);
        c.suscribir(setSync);
        setSync(await c.estado());
        await avisarUsuarioAlServiceWorker(datosUsuario.id);
        await cargarPerfil();
        if(navigator.onLine){
            c.vaciar();
        }
    };

    const salir = async (): Promise<void> => {
        const c: any = cola();
        const estado: any = c ? await c.estado() : { pendientes: 0, errores: [] };
        const sinEnviar: number = estado.pendientes + estado.errores.length;
        if(sinEnviar > 0){
            const ok: boolean = window.confirm(`Hay ${sinEnviar} registros sin sincronizar en este dispositivo. Se quedan guardados aquí y se enviarán solo cuando vuelvas a entrar con esta misma cuenta. ¿Cerrar sesión igualmente?`);
            if(!ok){
                return;
            }
        }
        await desactivarPush();
        try {
            await api.post("/api/auth/salir");
        } catch (error) {
            console.log(`Cierre de sesión sin conexión: ${error}`);
        }
        await avisarUsuarioAlServiceWorker(null);
        desactivarCola();
        setPerfil(null);
        setSync(null);
        setUsuario(null);
        window.location.hash = "/";
    };

    useEffect(() => {
        const alCambiarHash = (): void => setRuta(rutaActual());
        const alConectar = (): void => {
            setEnLinea(true);
            cola()?.vaciar();
        };
        const alDesconectar = (): void => setEnLinea(false);
        const caducada = (): void => {
            avisarUsuarioAlServiceWorker(null);
            desactivarCola();
            setUsuario(null);
        };
        const red = (): void => setTic((t: number) => t + 1);
        window.addEventListener("hashchange", alCambiarHash);
        window.addEventListener("online", alConectar);
        window.addEventListener("offline", alDesconectar);
        window.addEventListener("sesion-caducada", caducada);
        window.addEventListener("estado-red", red);
        aplicarTema("sistema");
        api.get("/api/auth/yo").then((r: any) => entrar(r.usuario)).catch((e: any) => {
            if(e.estado == 0 || e.estado == 503){
                setMensaje({ texto: "Sin conexión: inicia sesión cuando vuelvas a tener red.", tipo: "amarillo" });
            }
            setUsuario(null);
        });
        const intervalo: number = window.setInterval(() => {
            if(navigator.onLine){
                cola()?.vaciar();
            }
        }, 30000);
        return () => {
            window.removeEventListener("hashchange", alCambiarHash);
            window.removeEventListener("online", alConectar);
            window.removeEventListener("offline", alDesconectar);
            window.removeEventListener("sesion-caducada", caducada);
            window.removeEventListener("estado-red", red);
            window.clearInterval(intervalo);
        };
    }, []);

    if(ruta.startsWith("/admin")){
        return <Admin />;
    }
    if(usuario === undefined){
        return <div className="app"><p className="suave">Cargando…</p></div>;
    }
    if(usuario == null || ruta.startsWith("/invitacion/")){
        return <Acceso ruta={ruta} usuario={usuario} alEntrar={entrar} alSalir={salir} mensaje={mensaje} />;
    }

    const contexto: any = {
        usuario: usuario,
        perfil: perfil,
        recargarPerfil: cargarPerfil,
        salir: salir,
        sync: sync,
        enLinea: enLinea,
        registrar: registrar,
        avisar: (texto: string, tipo: string = "") => {
            setMensaje({ texto: texto, tipo: tipo });
            window.setTimeout(() => setMensaje(null), 5000);
        },
        estadoSync: <EstadoSync sync={sync} enLinea={enLinea} />,
    };

    let pantalla: any = <Hoy />;
    if(ruta.startsWith("/menu")){
        pantalla = <Menu />;
    }else if(ruta.startsWith("/gym")){
        pantalla = <Gym />;
    }else if(ruta.startsWith("/compra")){
        pantalla = <Compra />;
    }else if(ruta.startsWith("/progreso")){
        pantalla = <Progreso />;
    }else if(ruta.startsWith("/perfil")){
        pantalla = <Perfil />;
    }

    return (
        <Contexto.Provider value={contexto}>
            <div className="app">
                {estadoRed.desdeCache ? <div className="aviso amarillo" role="status">Sin conexión con el servidor: estás viendo la última copia guardada{estadoRed.ultimaCache ? ` (${new Date(estadoRed.ultimaCache).toLocaleString("es-ES")})` : ""}. Lo que registres se guardará y se enviará al reconectar.</div> : null}
                {mensaje ? <div className={`aviso ${mensaje.tipo}`} role="status">{mensaje.texto}</div> : null}
                {pantalla}
            </div>
            <nav className="navegacion" aria-label="Secciones">
                {SECCIONES.map((s: any) => {
                    const activa: boolean = s.ruta == "/" ? ruta == "/" : ruta.startsWith(s.ruta);
                    return (
                        <a key={s.ruta} href={`#${s.ruta}`} className={activa ? "activa" : ""} aria-current={activa ? "page" : undefined}>
                            <span className="icono" aria-hidden="true">{s.icono}</span>
                            {s.texto}
                        </a>
                    );
                })}
            </nav>
        </Contexto.Provider>
    );
}
