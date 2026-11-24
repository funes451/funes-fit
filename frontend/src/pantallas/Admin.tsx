import { useState } from "react";
import { api } from "../api";
import { CampoTexto, Selector } from "../componentes";

export default function Admin(): any {
    const [clave, setClave] = useState<string>("");
    const [estado, setEstado] = useState<any>(null);
    const [cuenta, setCuenta] = useState<any>({ email: "", contrasena: "", repetida: "", plan: "funes" });
    const [enlace, setEnlace] = useState<string | null>(null);
    const [mensaje, setMensaje] = useState<any>(null);

    const ejecutar = async (accion: () => Promise<void>): Promise<void> => {
        setMensaje(null);
        try {
            await accion();
        } catch (e: any) {
            setMensaje({ texto: e.message, tipo: "rojo" });
        }
    };

    const consultar = (): Promise<void> => ejecutar(async () => setEstado(await api.post("/api/admin/estado", { clave_admin: clave })));

    const crear = (): Promise<void> => ejecutar(async () => {
        if(cuenta.contrasena != cuenta.repetida){
            throw new Error("Las contraseñas no coinciden");
        }
        const r: any = await api.post("/api/admin/cuentas", { clave_admin: clave, email: cuenta.email, contrasena: cuenta.contrasena, plan: cuenta.plan });
        setMensaje({ texto: `Cuenta creada para ${r.email}. Ya puedes entrar con ella.`, tipo: "" });
        setCuenta({ email: "", contrasena: "", repetida: "", plan: "funes" });
        await consultar();
    });

    const invitar = (): Promise<void> => ejecutar(async () => {
        const r: any = await api.post("/api/admin/invitaciones", { clave_admin: clave, plan: "amigo", horas: 72 });
        setEnlace(`${window.location.origin}${r.ruta}`);
    });

    return (
        <div className="app">
            <div className="cabecera">
                <h1>Administración</h1>
                <a className="boton" href="#/">Volver</a>
            </div>
            <p className="suave">Solo para preparar las cuentas. Necesitas la clave FUNES_CLAVE_ADMIN que pusiste en Vercel. Aquí no se ven datos de nadie, solo recuentos.</p>
            {mensaje ? <div className={`aviso ${mensaje.tipo}`} role="status">{mensaje.texto}</div> : null}
            <section className="tarjeta columna">
                <CampoTexto etiqueta="Clave de administración" tipo="password" valor={clave} alCambiar={setClave} autocompletar="off" />
                <button onClick={consultar} disabled={!clave}>Comprobar</button>
                {estado ? (
                    <div>
                        <p className="suave">Base de datos: {estado.base_de_datos} · avisos: {estado.avisos}</p>
                        {estado.cuentas.length == 0 ? <p>Todavía no hay cuentas.</p> : null}
                        <ul className="lista">
                            {estado.cuentas.map((c: any) => <li key={c.id}>{c.email} · {c.perfil} · {c.modo} · {c.recetas} recetas, {c.semanas} semana{c.semanas == 1 ? "" : "s"}, {c.consumos} registros</li>)}
                        </ul>
                    </div>
                ) : null}
            </section>
            {estado ? (
                <>
                    <section className="tarjeta columna">
                        <h2>Crear cuenta</h2>
                        <Selector etiqueta="Plan" valor={cuenta.plan} alCambiar={(v: string) => setCuenta({ ...cuenta, plan: v })} opciones={[{ valor: "funes", texto: "Plan de Funes (menú, rutina y perfil)" }, { valor: "vacio", texto: "Cuenta vacía" }]} />
                        <CampoTexto etiqueta="Correo" tipo="email" valor={cuenta.email} alCambiar={(v: string) => setCuenta({ ...cuenta, email: v })} autocompletar="off" />
                        <CampoTexto etiqueta="Contraseña (mínimo 10 caracteres)" tipo="password" valor={cuenta.contrasena} alCambiar={(v: string) => setCuenta({ ...cuenta, contrasena: v })} autocompletar="new-password" />
                        <CampoTexto etiqueta="Repite la contraseña" tipo="password" valor={cuenta.repetida} alCambiar={(v: string) => setCuenta({ ...cuenta, repetida: v })} autocompletar="new-password" />
                        <button className="primario" onClick={crear}>Crear cuenta</button>
                    </section>
                    <section className="tarjeta columna">
                        <h2>Invitar a tu amigo</h2>
                        <p className="suave">Genera un enlace de un solo uso que caduca en 72 horas. No contiene datos personales y no se envía solo: cópialo y pásaselo tú.</p>
                        <button onClick={invitar}>Generar enlace</button>
                        {enlace ? (
                            <div className="columna">
                                <input readOnly value={enlace} onFocus={(e: any) => e.target.select()} aria-label="Enlace de invitación" />
                                <button onClick={() => navigator.clipboard && navigator.clipboard.writeText(enlace)}>Copiar</button>
                            </div>
                        ) : null}
                    </section>
                </>
            ) : null}
        </div>
    );
}
