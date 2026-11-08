const $ = (id) => document.getElementById(id);
const pesos = (n) => "$" + n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const limpiar = (t) => String(t).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const vacio = (cols, txt) => `<tr><td colspan="${cols}" class="vacio">${txt}</td></tr>`;
let alertasVistas = null;

function tiempo(seg) {
  const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60);
  return `arriba hace ${h} h ${m} min`;
}

function sonarAlarma() {
  try {
    const ctx = new AudioContext();
    [0, 0.35, 0.7].forEach((t) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.15, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + t + 0.25);
      o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.3);
    });
  } catch (e) { /* el navegador puede bloquear el sonido */ }
}

function ponerEstado(clase, icono, titulo, texto) {
  $("estado").className = "estado " + clase;
  $("estado-icono").textContent = icono;
  $("estado-titulo").textContent = titulo;
  $("estado-texto").textContent = texto;
}

async function actualizar() {
  let d;
  try {
    d = await (await fetch("/api/estado")).json();
  } catch (e) {
    ponerEstado("caida", "✕", "Sin respuesta de la aplicación", "El servidor web no contesta.");
    return;
  }
  $("latido").classList.toggle("pulso");

  if (!d.bd_ok) {
    ponerEstado("caida", "✕", "MySQL no responde", d.error);
    $("t-bd").textContent = "Caído";
    $("t-bd").className = "mal";
    return;
  }

  $("modo").innerHTML = d.control
    ? `<b>Compra con control</b><span>SELECT … FOR UPDATE</span>`
    : `<b>Compra sin control</b><span>sin bloqueo de inventario</span>`;
  $("modo").className = "modo " + (d.control ? "seguro" : "inseguro");

  $("t-bd").textContent = "Arriba";
  $("t-bd").className = "bien";
  $("t-uptime").textContent = tiempo(d.uptime);
  $("t-conex").textContent = d.conexiones;
  $("t-ventas").textContent = d.ventas_hoy;
  $("t-monto").textContent = pesos(d.monto_hoy);
  const pendientes = d.alertas.filter((a) => !a.Atendida);
  $("t-alertas").textContent = pendientes.length;
  $("t-alertas").className = pendientes.length ? "mal" : "bien";

  $("inventario").innerHTML = d.productos.map((p) => `
    <tr class="${p.stock < 0 ? "fila-mal" : p.stock <= 1 ? "fila-aviso" : ""}">
      <td>${p.nombre}</td><td>${p.color}</td><td class="num stock">${p.stock}</td>
    </tr>`).join("");

  $("alertas").innerHTML = d.alertas.length
    ? d.alertas.map((a) => `
      <tr class="${a.Atendida ? "" : "fila-mal"}"><td class="mono">${a.Fecha_Hora}</td><td>${a.Tipo}</td><td>${a.Descripcion}</td>
      <td>${a.Notificada ? "✉ enviado" : "pendiente"}${a.Atendida ? " · ✔ atendida" : ""}</td></tr>`).join("")
    : vacio(4, "Sin alertas");

  $("auditoria").innerHTML = d.auditoria.length
    ? d.auditoria.map((a) => `
      <tr class="${a.Stock_Nuevo < 0 ? "fila-mal" : ""}"><td class="mono">${a.Fecha_Hora}</td><td class="mono">${a.Usuario}</td>
      <td>${a.Producto}</td><td class="num mono">${a.Stock_Anterior} → ${a.Stock_Nuevo}</td></tr>`).join("")
    : vacio(4, "Sin movimientos");

  $("ventas").innerHTML = d.ventas.length
    ? d.ventas.map((v) => `<tr><td class="mono">#${v.ID_Venta}</td><td>${limpiar(v.Cliente)}</td><td>${v.Producto}</td><td class="num">${pesos(v.Total)}</td></tr>`).join("")
    : vacio(4, "Aún no hay ventas hoy");

  const negativos = d.productos.filter((p) => p.stock < 0);
  if (negativos.length || pendientes.length) {
    const p = negativos[0];
    ponerEstado("alerta", "!", "ALERTA · Stock negativo",
      p ? `${p.nombre} quedó con stock ${p.stock}: se vendieron ${-p.stock} pieza(s) que no existen.`
        : pendientes[0].Descripcion);
  } else if (d.reembolsos) {
    ponerEstado("ok", "✓", "Incidente atendido",
      `Se cancelaron y reembolsaron ${d.reembolsos} venta(s) por ${pesos(d.monto_reembolsado)}. El inventario quedó corregido.`);
  } else {
    ponerEstado("ok", "✓", "Todo en orden", "Sin alertas. El inventario de la tienda en línea es consistente.");
  }

  const ultima = d.alertas.length ? d.alertas[0].ID_Alerta : 0;
  if (alertasVistas !== null && ultima > alertasVistas) sonarAlarma();
  alertasVistas = ultima;
}

setInterval(() => { $("reloj").textContent = new Date().toLocaleTimeString("es-MX"); }, 1000);
actualizar();
setInterval(actualizar, 2000);
