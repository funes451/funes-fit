import { useEffect, useState } from "react";
import { api } from "../api";
import { CampoTexto } from "../componentes";

export default function Acceso(props: any): any {
    const token: string | null = props.ruta.startsWith("/invitacion/") ? props.ruta.replace("/invitacion/", "") : null;
    const [email, setEmail] = useState<string>("");
    const [contrasena, setContrasena] = useState<string>("");
    const [repetida, setRepetida] = useState<string>("");
    const [codigo, setCodigo] = useState<string>("");
    const [pasoTotp, setPasoTotp] = useState<boolean>(false);
    const [usarRecuperacion, setUsarRecuperacion] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [invitacion, setInvitacion] = useState<any>(null);
    const [ocupado, setOcupado] = useState<boolean>(false);

    useEffect(() => {
        if(token && !props.usuario){
            api.get(`/api/invitaciones/${token}`).then(setInvitacion).catch((e: any) => setError(e.message));
        }
    }, [token]);

    const ejecutar = async (accion: () => Promise<void>): Promise<void> => {
        setError(null);
        setOcupado(true);
        try {
            await accion();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setOcupado(false);
        }
    };

    const acceder = (e: any): void => {
        e.preventDefault();
        ejecutar(async () => {
            const r: any = await api.post("/api/auth/acceso", { email: email, contrasena: contrasena });
            if(r.requiere_totp){
                setPasoTotp(true);
                return;
            }
            await props.alEntrar(r.usuario);
        });
    };

    const segundoFactor = (e: any): void => {
        e.preventDefault();
        ejecutar(async () => {
            const r: any = await api.post("/api/auth/segundo-factor", usarRecuperacion ? { recuperacion: codigo } : { codigo: codigo });
            await props.alEntrar(r.usuario);
        });
    };

    const activar = (e: any): void => {
        e.preventDefault();
        if(contrasena != repetida){
            setError("Las contraseñas no coinciden");
            return;
        }
        ejecutar(async () => {
            const r: any = await api.post(`/api/invitaciones/${token}/activar`, { email: email, contrasena: contrasena });
            window.location.hash = "/perfil";
            await props.alEntrar(r.usuario);
        });
    };

    if(token && props.usuario){
        return (
            <div className="app">
                <div className="tarjeta">
                    <h2>Invitación</h2>
                    <p>Tienes una sesión abierta. Para activar otra cuenta con esta invitación, cierra antes tu sesión en este dispositivo.</p>
                    <div className="fila">
                        <button className="primario" onClick={() => props.alSalir()}>Cerrar sesión</button>
                        <a className="boton" href="#/">Volver</a>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="app">
            <div className="cabecera">
                <h1>Funes Fit</h1>
            </div>
            {props.mensaje ? <div className={`aviso ${props.mensaje.tipo}`}>{props.mensaje.texto}</div> : null}
            {error ? <div className="aviso rojo" role="alert">{error}</div> : null}
            {token ? (
                <form className="tarjeta columna" onSubmit={activar}>
                    <h2>Activa tu cuenta</h2>
                    {invitacion ? <p className="suave">Invitación para «{invitacion.nombre_provisional}». Caduca el {new Date(invitacion.expira_en).toLocaleString("es-ES")}. Al entrar podrás revisar y confirmar tu plan y completar tus datos.</p> : null}
                    <CampoTexto etiqueta="Correo" tipo="email" valor={email} alCambiar={setEmail} autocompletar="email" obligatorio />
                    <CampoTexto etiqueta="Contraseña (mínimo 10 caracteres)" tipo="password" valor={contrasena} alCambiar={setContrasena} autocompletar="new-password" obligatorio />
                    <CampoTexto etiqueta="Repite la contraseña" tipo="password" valor={repetida} alCambiar={setRepetida} autocompletar="new-password" obligatorio />
                    <button className="primario" disabled={ocupado || !invitacion}>Crear mi cuenta</button>
                </form>
            ) : pasoTotp ? (
                <form className="tarjeta columna" onSubmit={segundoFactor}>
                    <h2>Segundo factor</h2>
                    <CampoTexto etiqueta={usarRecuperacion ? "Código de recuperación" : "Código de 6 cifras de tu app de autenticación"} valor={codigo} alCambiar={setCodigo} modo={usarRecuperacion ? "text" : "numeric"} autocompletar="one-time-code" obligatorio />
                    <button className="primario" disabled={ocupado}>Entrar</button>
                    <button type="button" className="enlace" onClick={() => setUsarRecuperacion(!usarRecuperacion)}>{usarRecuperacion ? "Usar código de la app" : "Usar un código de recuperación"}</button>
                </form>
            ) : (
                <form className="tarjeta columna" onSubmit={acceder}>
                    <h2>Entrar</h2>
                    <CampoTexto etiqueta="Correo" tipo="email" valor={email} alCambiar={setEmail} autocompletar="username" obligatorio />
                    <CampoTexto etiqueta="Contraseña" tipo="password" valor={contrasena} alCambiar={setContrasena} autocompletar="current-password" obligatorio />
                    <button className="primario" disabled={ocupado}>Entrar</button>
                    <p className="suave">Las cuentas se crean desde <a href="#/admin">Administración</a> o con una invitación de un solo uso.</p>
                </form>
            )}
        </div>
    );
}
