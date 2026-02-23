import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { bootstrapCanonicalUserFromUrl } from "./lib/canonical-user";

bootstrapCanonicalUserFromUrl();

createRoot(document.getElementById("root")!).render(<App />);
