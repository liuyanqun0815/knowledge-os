import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { KbProvider } from "./app/KbContext";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <KbProvider>
        <App />
      </KbProvider>
    </BrowserRouter>
  </StrictMode>,
);
