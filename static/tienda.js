const rejilla = document.getElementById("rejilla");
const modal = document.getElementById("modal");
const modalContenido = document.getElementById("modal-contenido");
let productos = [];
let enBolsa = 0;

const limpiar = (t) => t.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const pesos = (n) => "$" + n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function fotoDe(p) {
  return p.imagen ? `<img src="${p.imagen}" alt="${p.nombre}">` : dibujoPrenda(p.tipo, p.color);
}

function insignia(p) {
  if (p.stock <= 0) return `<span class="insignia agotado">Agotado</span>`;
  if (p.stock === 1) return `<span class="insignia ultima">¡Última pieza!</span>`;
  if (p.stock <= 10) return `<span class="insignia pocas">Quedan ${p.stock}</span>`;
  return "";
}

function pintar() {
  rejilla.innerHTML = productos.map((p) => `
    <article class="tarjeta ${p.stock <= 0 ? "sin-stock" : ""}">
      <div class="foto tono-${p.color.toLowerCase()} ${p.imagen ? "con-foto" : ""}">${fotoDe(p)}${insignia(p)}</div>
      <div class="datos">
        <h3>${p.nombre}</h3>
        <p class="detalle">${p.categoria} · ${p.color} · Talla ${p.talla}</p>
        <p class="precio">${pesos(p.precio)}</p>
        <button class="boton-comprar" data-id="${p.id}" ${p.stock <= 0 ? "disabled" : ""}>
          ${p.stock <= 0 ? "Agotado" : "Comprar"}
        </button>
      </div>
    </article>`).join("");
}

async function cargar() {
  try {
    productos = await (await fetch("/api/productos")).json();
    pintar();
  } catch (e) { /* si la base no responde se queda lo ultimo que se pinto */ }
}

function abrirPago(p) {
  modalContenido.innerHTML = `
    <div class="pago">
      <div class="pago-foto tono-${p.color.toLowerCase()}">${fotoDe(p)}</div>
      <div class="pago-datos">
        <p class="etiqueta">Resumen de compra</p>
        <h3>${p.nombre}</h3>
        <p class="detalle">${p.color} · Talla ${p.talla}</p>
        <p class="precio grande">${pesos(p.precio)}</p>
        <label>Nombre<input id="nombre" placeholder="¿Quién compra?" maxlength="100" autocomplete="name"></label>
        <label>Tarjeta<input value="•••• •••• •••• 4242" readonly></label>
        <div class="fila"><label>Vence<input value="08/29" readonly></label><label>CVV<input value="•••" readonly></label></div>
        <button class="boton-pagar" id="pagar">Pagar ${pesos(p.precio)}</button>
      </div>
    </div>`;
  modal.hidden = false;
  const campo = document.getElementById("nombre");
  try { campo.value = localStorage.getItem("nombre-cliente") || ""; } catch (e) { /* sin almacenamiento */ }
  document.getElementById("pagar").onclick = () => pagar(p);
}

async function comprar(id, nombre) {
  const r = await fetch("/api/comprar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_producto: id, nombre }),
  });
  return r.json();
}

async function pagar(p) {
  const campo = document.getElementById("nombre");
  const nombre = campo.value.trim();
  if (!nombre) {
    campo.classList.add("falta");
    campo.focus();
    return;
  }
  try { localStorage.setItem("nombre-cliente", nombre); } catch (e) { /* sin almacenamiento */ }
  const boton = document.getElementById("pagar");
  boton.disabled = true;
  boton.innerHTML = `<span class="girando"></span> Procesando pago…`;
  let r;
  try { r = await comprar(p.id, nombre); } catch (e) { r = { ok: false, mensaje: "Sin conexión con la tienda" }; }
  if (r.ok) {
    enBolsa++;
    document.getElementById("contador-bolsa").textContent = enBolsa;
    modalContenido.innerHTML = `
      <div class="resultado">
        <div class="palomita">✓</div>
        <h3>¡Gracias, ${limpiar(nombre)}!</h3>
        <p>${p.nombre} · ${pesos(p.precio)}</p>
        <p class="folio">Folio de venta <b>#${r.folio}</b></p>
        <p class="detalle">Recógela en H&amp;M Plaza Satélite</p>
        <button class="boton-claro" onclick="cerrar()">Seguir comprando</button>
      </div>`;
  } else {
    modalContenido.innerHTML = `
      <div class="resultado">
        <div class="tache">!</div>
        <h3>${r.mensaje}</h3>
        <p class="detalle">No se hizo ningún cargo a tu tarjeta.</p>
        <button class="boton-claro" onclick="cerrar()">Volver a la tienda</button>
      </div>`;
  }
  cargar();
}

function cerrar() { modal.hidden = true; }

rejilla.addEventListener("click", (e) => {
  const b = e.target.closest(".boton-comprar");
  if (b) abrirPago(productos.find((p) => p.id === Number(b.dataset.id)));
});
document.getElementById("cerrar-modal").onclick = cerrar;
modal.addEventListener("click", (e) => { if (e.target === modal) cerrar(); });

document.getElementById("portada-arte").innerHTML =
  `<div class="arte a1"><img src="/static/img/2142.jpg" alt="Chamarra oversize gris"></div>
   <div class="arte a2"><img src="/static/img/2289.jpg" alt="Vestido amarillo"></div>
   <div class="arte a3"><img src="/static/img/1440.jpg" alt="Bolsa edición limitada"></div>`;

// modo demo: dos clientes compran en linea la ultima pieza al mismo tiempo
const botonDoble = document.getElementById("boton-doble");
if (botonDoble) {
  botonDoble.onclick = async () => {
    const salida = document.getElementById("demo-resultado");
    salida.textContent = "Cobrando a los dos clientes…";
    const chamarra = productos[0].id;
    const [a, b] = await Promise.all([comprar(chamarra, "Ana (demo)"), comprar(chamarra, "Luis (demo)")]);
    const txt = (r) => (r.ok ? `vendida (folio #${r.folio})` : r.mensaje);
    salida.textContent = `Ana: ${txt(a)} · Luis: ${txt(b)}`;
    cargar();
  };
}

cargar();
setInterval(cargar, 3000);
