import { createRoot } from "react-dom/client";
import App from "./App";
import { registrarServiceWorker } from "./dispositivo";
import "./estilos.css";

registrarServiceWorker();
createRoot(document.getElementById("raiz") as HTMLElement).render(<App />);
