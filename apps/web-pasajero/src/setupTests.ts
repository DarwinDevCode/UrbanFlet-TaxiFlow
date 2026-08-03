import "@testing-library/jest-dom/vitest";

// App.tsx abre un WebSocket a `${getApiBaseUrl()}/ws/pasajero/{id}` mientras
// el viaje sigue en un estado que puede cambiar en vivo. En los tests nunca
// se llama a configureApiClient (no hay backend real), así que la URL queda
// relativa y el WebSocket real de jsdom la rechaza como inválida — un stub
// mínimo evita ese crash sin tener que simular mensajes en vivo, que no es
// lo que estos tests verifican (el polling de respaldo ya cubre las mismas
// transiciones y es lo que se prueba).
class WebSocketStub {
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(_url: string) {}
  close() {}
}
// @ts-expect-error -- stub de test, no implementa la interfaz completa de WebSocket
globalThis.WebSocket = WebSocketStub;
