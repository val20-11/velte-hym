# tienda en linea H&M + panel de monitoreo
# uso: python app.py   (la tienda queda en http://localhost:5000 y el panel en /monitor)
import configparser
import smtplib
import socket
import threading
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import mysql.connector
from flask import Flask, jsonify, render_template, request

BASE = Path(__file__).parent
cfg = configparser.ConfigParser()
cfg.read(BASE / "config.ini", encoding="utf-8-sig")

SUCURSAL = cfg.getint("tienda", "sucursal")
EMPLEADO = cfg.getint("tienda", "empleado")
CLIENTE = cfg.getint("tienda", "cliente")
TIEMPO_PAGO = cfg.getfloat("tienda", "tiempo_pago")
CONTROL = cfg.get("tienda", "control_concurrencia").strip().lower() in ("si", "sí")
EMPRESA = cfg.get("empresa", "nombre")
CORREO_USUARIO = cfg.get("correo", "usuario", fallback="").strip()
CORREO_CONTRASENA = cfg.get("correo", "contrasena_app", fallback="").replace(" ", "")
CORREO_DESTINO = [c.strip() for c in cfg.get("correo", "destinatarios", fallback="").split(",") if c.strip()]

# productos que se muestran en la tienda (el primero es la chamarra con la ultima pieza)
PRODUCTOS_TIENDA = [2142, 2289, 1055, 1440, 2121, 1582, 2848, 742]

app = Flask(__name__)


def conectar():
    return mysql.connector.connect(
        host=cfg.get("mysql", "host"),
        user=cfg.get("mysql", "user"),
        password=cfg.get("mysql", "password"),
        database=cfg.get("mysql", "database"),
    )


def imagen(id_producto):
    for ext in ("jpg", "jpeg", "png", "webp"):
        if (BASE / "static" / "img" / f"{id_producto}.{ext}").exists():
            return f"/static/img/{id_producto}.{ext}"
    return None


def productos_tienda(cur):
    marcas = ",".join(["%s"] * len(PRODUCTOS_TIENDA))
    cur.execute(
        f"""SELECT p.ID_Producto, p.Nombre, p.Precio, p.Talla, p.Color, c.Nombre AS Categoria,
                   i.ID_Inventario, i.Stock
            FROM INVENTARIO i
            JOIN PRODUCTO p ON i.ID_Producto = p.ID_Producto
            JOIN CATEGORIA c ON p.ID_Categoria = c.ID_Categoria
            WHERE i.ID_Sucursal = %s AND p.ID_Producto IN ({marcas})""",
        (SUCURSAL, *PRODUCTOS_TIENDA),
    )
    filas = {f["ID_Producto"]: f for f in cur.fetchall()}
    salida = []
    for id_p in PRODUCTOS_TIENDA:
        f = filas[id_p]
        salida.append({
            "id": id_p,
            "nombre": f["Nombre"],
            "tipo": f["Nombre"].split()[0].lower(),
            "precio": float(f["Precio"]),
            "talla": f["Talla"],
            "color": f["Color"],
            "categoria": f["Categoria"],
            "inventario": f["ID_Inventario"],
            "stock": f["Stock"],
            "imagen": imagen(id_p),
        })
    return salida


# los clientes en linea usan ID_Cliente >= CLIENTE; si el nombre es nuevo se da de alta
def obtener_cliente(cn, nombre):
    if not nombre:
        return CLIENTE
    cur = cn.cursor()
    for _ in range(5):
        cur.execute("SELECT ID_Cliente FROM CLIENTE WHERE Nombre = %s AND ID_Cliente >= %s "
                    "ORDER BY ID_Cliente LIMIT 1", (nombre, CLIENTE))
        fila = cur.fetchone()
        if fila:
            cn.commit()
            return fila[0]
        cur.execute("SELECT MAX(ID_Cliente) + 1 FROM CLIENTE WHERE ID_Cliente >= %s", (CLIENTE,))
        nuevo = cur.fetchone()[0]
        try:
            cur.execute("INSERT INTO CLIENTE (ID_Cliente, Nombre, Email, Telefono) VALUES (%s, %s, %s, %s)",
                        (nuevo, nombre, f"cliente{nuevo}@tiendalinea.hm", "5500000000"))
            cn.commit()
            return nuevo
        except mysql.connector.IntegrityError:
            # otro celular dio de alta un cliente con ese ID al mismo tiempo; se vuelve a intentar
            cn.rollback()
    raise mysql.connector.Error("No se pudo registrar al cliente")


def registrar_venta(cur, id_producto, precio, id_inventario, id_cliente):
    cur.execute(
        "INSERT INTO VENTA (Fecha, Total, ID_Cliente, ID_Empleado, ID_Sucursal) "
        "VALUES (CURDATE(), %s, %s, %s, %s)",
        (precio, id_cliente, EMPLEADO, SUCURSAL),
    )
    id_venta = cur.lastrowid
    cur.execute(
        "INSERT INTO DETALLE_VENTA (ID_Venta, ID_Producto, Cantidad, Precio_Unitario) VALUES (%s, %s, 1, %s)",
        (id_venta, id_producto, precio),
    )
    cur.execute("UPDATE INVENTARIO SET Stock = Stock - 1 WHERE ID_Inventario = %s", (id_inventario,))
    return id_venta


# version con el fallo: revisa el stock, cobra y despues descuenta
def comprar_sin_control(cn, id_producto, id_cliente):
    cur = cn.cursor(dictionary=True)
    cur.execute(
        "SELECT i.ID_Inventario, i.Stock, p.Precio FROM INVENTARIO i "
        "JOIN PRODUCTO p ON i.ID_Producto = p.ID_Producto "
        "WHERE i.ID_Sucursal = %s AND i.ID_Producto = %s",
        (SUCURSAL, id_producto),
    )
    fila = cur.fetchone()
    if fila["Stock"] < 1:
        return None
    time.sleep(TIEMPO_PAGO)  # cobro con tarjeta
    id_venta = registrar_venta(cur, id_producto, fila["Precio"], fila["ID_Inventario"], id_cliente)
    cn.commit()
    return id_venta


# version corregida: el renglon del inventario queda bloqueado hasta terminar la compra
def comprar_con_control(cn, id_producto, id_cliente):
    cur = cn.cursor(dictionary=True)
    cn.start_transaction()
    cur.execute(
        "SELECT i.ID_Inventario, i.Stock, p.Precio FROM INVENTARIO i "
        "JOIN PRODUCTO p ON i.ID_Producto = p.ID_Producto "
        "WHERE i.ID_Sucursal = %s AND i.ID_Producto = %s FOR UPDATE OF i",
        (SUCURSAL, id_producto),
    )
    fila = cur.fetchone()
    if fila["Stock"] < 1:
        cn.rollback()
        return None
    time.sleep(TIEMPO_PAGO)
    id_venta = registrar_venta(cur, id_producto, fila["Precio"], fila["ID_Inventario"], id_cliente)
    cn.commit()
    return id_venta


@app.route("/")
def tienda():
    return render_template("tienda.html", demo=request.args.get("demo") == "1")


@app.route("/monitor")
def monitor():
    return render_template("monitor.html", empresa=EMPRESA)


@app.route("/api/productos")
def api_productos():
    cn = conectar()
    try:
        return jsonify(productos_tienda(cn.cursor(dictionary=True)))
    finally:
        cn.close()


@app.route("/api/comprar", methods=["POST"])
def api_comprar():
    id_producto = int(request.json["id_producto"])
    nombre = " ".join(str(request.json.get("nombre", "")).split())[:100]
    cn = conectar()
    try:
        id_cliente = obtener_cliente(cn, nombre)
        compra = comprar_con_control if CONTROL else comprar_sin_control
        id_venta = compra(cn, id_producto, id_cliente)
    except mysql.connector.Error as e:
        cn.rollback()
        return jsonify({"ok": False, "mensaje": "No se pudo completar la compra", "error": str(e)}), 409
    finally:
        cn.close()
    if id_venta is None:
        return jsonify({"ok": False, "mensaje": "Lo sentimos, este artículo se agotó"}), 409
    return jsonify({"ok": True, "folio": id_venta})


@app.route("/api/estado")
def api_estado():
    try:
        cn = conectar()
    except mysql.connector.Error as e:
        return jsonify({"bd_ok": False, "error": str(e), "control": CONTROL})
    try:
        cur = cn.cursor(dictionary=True)
        cur.execute("SHOW GLOBAL STATUS WHERE Variable_name IN ('Uptime', 'Threads_connected')")
        status = {f["Variable_name"]: int(f["Value"]) for f in cur.fetchall()}
        productos = productos_tienda(cur)

        cur.execute("SELECT ID_Alerta, Tipo, Descripcion, Fecha_Hora, Notificada, Atendida FROM ALERTA "
                    "ORDER BY ID_Alerta DESC LIMIT 8")
        alertas = cur.fetchall()

        marcas = ",".join(["%s"] * len(productos))
        cur.execute(
            f"""SELECT a.Fecha_Hora, a.Usuario, p.Nombre AS Producto, a.Stock_Anterior, a.Stock_Nuevo
                FROM AUDITORIA_INVENTARIO a JOIN PRODUCTO p ON a.ID_Producto = p.ID_Producto
                WHERE a.ID_Inventario IN ({marcas})
                ORDER BY a.ID_Auditoria DESC LIMIT 8""",
            [p["inventario"] for p in productos],
        )
        auditoria = cur.fetchall()

        cur.execute(
            """SELECT v.ID_Venta, c.Nombre AS Cliente, p.Nombre AS Producto, v.Total
               FROM VENTA v
               JOIN CLIENTE c ON v.ID_Cliente = c.ID_Cliente
               JOIN DETALLE_VENTA d ON v.ID_Venta = d.ID_Venta
               JOIN PRODUCTO p ON d.ID_Producto = p.ID_Producto
               WHERE v.ID_Cliente >= %s AND v.Fecha = CURDATE()
               ORDER BY v.ID_Venta DESC LIMIT 8""",
            (CLIENTE,),
        )
        ventas = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(Total), 0) AS monto FROM VENTA "
                    "WHERE ID_Cliente >= %s AND Fecha = CURDATE()", (CLIENTE,))
        resumen = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(Monto), 0) AS monto FROM REEMBOLSO "
                    "WHERE DATE(Fecha_Hora) = CURDATE()")
        reembolsos = cur.fetchone()
    finally:
        cn.close()

    for f in alertas + auditoria:
        f["Fecha_Hora"] = f["Fecha_Hora"].strftime("%H:%M:%S.%f")[:-3]
    for v in ventas:
        v["Total"] = float(v["Total"])
    return jsonify({
        "bd_ok": True,
        "uptime": status.get("Uptime"),
        "conexiones": status.get("Threads_connected"),
        "control": CONTROL,
        "productos": productos,
        "alertas": alertas,
        "auditoria": auditoria,
        "ventas": ventas,
        "ventas_hoy": resumen["n"],
        "monto_hoy": float(resumen["monto"]),
        "reembolsos": reembolsos["n"],
        "monto_reembolsado": float(reembolsos["monto"]),
    })


# correo de alertas: revisa la tabla ALERTA y avisa por Gmail las que no se han notificado
def alertas_pendientes(cur):
    cur.execute(
        """SELECT a.ID_Alerta, a.Tipo, a.Descripcion, a.Fecha_Hora,
                  p.Nombre AS Producto, s.Nombre AS Sucursal, i.Stock
           FROM ALERTA a
           LEFT JOIN INVENTARIO i ON a.ID_Inventario = i.ID_Inventario
           LEFT JOIN PRODUCTO p ON i.ID_Producto = p.ID_Producto
           LEFT JOIN SUCURSAL s ON i.ID_Sucursal = s.ID_Sucursal
           WHERE a.Notificada = 0
           ORDER BY a.ID_Alerta"""
    )
    return cur.fetchall()


def armar_correo(alertas):
    a = alertas[-1]
    producto = a["Producto"] or "Producto desconocido"
    msg = EmailMessage()
    msg["Subject"] = f"⚠️ Stock negativo: {producto} ({a['Sucursal']}) quedó en {a['Stock']}"
    msg["From"] = formataddr((f"{EMPRESA} · Alertas", CORREO_USUARIO))
    msg["To"] = ", ".join(CORREO_DESTINO)

    renglones = "\n".join(
        f"  #{x['ID_Alerta']}  {x['Fecha_Hora']:%H:%M:%S}  {x['Descripcion']}" for x in alertas)
    msg.set_content(
        f"{EMPRESA} detectó una inconsistencia en bd_hm_retail.\n\n"
        f"Producto: {producto}\nSucursal: {a['Sucursal']}\nStock actual: {a['Stock']}\n\n"
        f"Alertas:\n{renglones}\n\n"
        "Se vendieron piezas que no existen. Revisar las ventas en linea y la bitacora AUDITORIA_INVENTARIO.\n")

    celda = "padding:6px 10px;border-top:1px solid #eee"
    filas = "".join(
        f"<tr><td style='{celda};font-family:monospace'>#{x['ID_Alerta']}</td>"
        f"<td style='{celda};font-family:monospace'>{x['Fecha_Hora']:%H:%M:%S}</td>"
        f"<td style='{celda}'>{x['Descripcion']}</td></tr>" for x in alertas)
    msg.add_alternative(f"""\
<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;border:1px solid #e5e5e5">
  <div style="padding:18px 20px;border-bottom:3px solid #0a3e62">
    <img src="cid:logo-velte" alt="{EMPRESA}" height="80" style="display:block;height:80px"><br>
    <span style="color:#0a3e62;font-size:13px">Centro de monitoreo · bd_hm_retail</span>
  </div>
  <div style="background:#d0021b;color:#fff;padding:14px 20px;font-size:16px"><b>ALERTA · Stock negativo</b></div>
  <div style="padding:20px">
    <p style="margin:0 0 14px">Se vendió un artículo que ya no tenía existencias.</p>
    <table style="border-collapse:collapse;margin-bottom:16px">
      <tr><td style="color:#777;padding:3px 16px 3px 0">Producto</td><td><b>{producto}</b></td></tr>
      <tr><td style="color:#777;padding:3px 16px 3px 0">Sucursal</td><td>{a['Sucursal']}</td></tr>
      <tr><td style="color:#777;padding:3px 16px 3px 0">Stock actual</td>
          <td><b style="color:#d0021b;font-size:18px">{a['Stock']}</b></td></tr>
    </table>
    <table style="border-collapse:collapse;width:100%;font-size:13px;background:#fafafa">{filas}</table>
    <p style="color:#777;font-size:12px;margin-top:18px">
      Generado por el trigger audita_inventario_update · tabla ALERTA.<br>
      Revisar las ventas en línea y la bitácora AUDITORIA_INVENTARIO.
    </p>
  </div>
</div>""", subtype="html")
    # el logo va adjunto dentro del correo (Gmail no puede ver archivos de esta computadora)
    logo = BASE / "static" / "velte-logo.png"
    if logo.exists():
        msg.get_payload()[1].add_related(logo.read_bytes(), "image", "png", cid="<logo-velte>")
    return msg


def vigilar_alertas():
    while True:
        espera = 2
        try:
            cn = conectar()
            try:
                cur = cn.cursor(dictionary=True)
                alertas = alertas_pendientes(cur)
                if alertas:
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
                        smtp.login(CORREO_USUARIO, CORREO_CONTRASENA)
                        smtp.send_message(armar_correo(alertas))
                    marcas = ",".join(["%s"] * len(alertas))
                    cur.execute(f"UPDATE ALERTA SET Notificada = 1 WHERE ID_Alerta IN ({marcas})",
                                [x["ID_Alerta"] for x in alertas])
                    cn.commit()
                    print(f"  ✉ correo de alerta enviado a {', '.join(CORREO_DESTINO)}")
            finally:
                cn.close()
        except (mysql.connector.Error, smtplib.SMTPException, OSError) as e:
            print(f"  ✉ no se pudo mandar el correo de alerta: {e}")
            espera = 30  # para no insistir cada 2 segundos si Gmail rechaza la contrasena
        time.sleep(espera)


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    print(f"\n  Tienda:   http://localhost:5000      (celulares en la misma red: http://{ip_local()}:5000)")
    print("  Monitor:  http://localhost:5000/monitor")
    print(f"  Modo:     {'CON control (corregido)' if CONTROL else 'SIN control (con el fallo)'}")
    if CORREO_USUARIO and CORREO_CONTRASENA and CORREO_DESTINO:
        threading.Thread(target=vigilar_alertas, daemon=True).start()
        print(f"  Correo:   alertas a {', '.join(CORREO_DESTINO)}\n")
    else:
        print("  Correo:   desactivado (falta contrasena_app en config.ini)\n")
    app.run(host="0.0.0.0", port=5000, threaded=True)
