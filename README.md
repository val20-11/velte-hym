# Tienda en línea H&M y monitor de inventario

Aplicación web en Flask que se conecta a la base `bd_hm_retail` (MySQL 8). Tiene tres partes:

- Una tienda donde se pueden comprar ocho productos de la sucursal 1.
- Un panel de monitoreo que se actualiza cada 2 segundos.
- Un proceso en segundo plano que manda correos cuando el inventario queda negativo.

La tienda tiene dos modos de compra. Uno tiene una condición de carrera: si dos personas compran la última pieza al mismo tiempo, el stock queda en -1. El otro la corrige con `SELECT ... FOR UPDATE`.

## Requisitos

- Python 3.10 o superior
- MySQL Server 8.0 con la base `bd_hm_retail` ya creada (ver la sección de la base de datos)
- Paquetes de Python:

```
pip install flask mysql-connector-python
```

## Archivos

```
demo/
├── app.py                        servidor Flask: tienda, monitor, API y correo de alertas
├── config.ini                    conexión a MySQL, modo de compra y cuenta de correo
├── prueba_inventario_negativo.py prueba de consola de la condición de carrera
├── templates/
│   ├── tienda.html               página de la tienda
│   └── monitor.html              panel de monitoreo
└── static/
    ├── tienda.js / tienda.css    carga de productos, compra y modo demo
    ├── monitor.js / monitor.css  consulta /api/estado cada 2 s y pinta el panel
    ├── prendas.js                dibujos SVG para productos sin foto
    ├── img/<ID_Producto>.jpg     fotos de los productos
    └── *.png                     logos de H&M y Velté (el de Velté también va en el correo)
```

## Base de datos

Los scripts están en `../sql/` y se corren como `root` en MySQL Workbench, en este orden:

| Script | Qué hace |
|---|---|
| `01_crear_bd_tablas.sql` | Crea `bd_hm_retail` y las 8 tablas. `DETALLE_VENTA` está particionada por rango. |
| `02_datos.sql` | Carga los datos. |
| `03_llaves.sql` | Llaves primarias, foráneas e índices. |
| `05_preparar_demo.sql` | Folios `AUTO_INCREMENT` en `VENTA` y `DETALLE_VENTA`, el cliente genérico 1000002, el usuario `app_tienda` y deja el inventario 128 con 1 pieza. |
| `06_auditoria_triggers.sql` | Tablas `AUDITORIA_INVENTARIO`, `ALERTA` y `REEMBOLSO`, y el trigger `audita_inventario_update`. |

`04_dml.sql` tiene consultas de ejemplo y no es necesario para la aplicación. `06b_tablas_incidentes.sql` solo se usa en una base que ya tenía una versión anterior del 06.

Scripts que se usan mientras corre la aplicación:

| Script | Para qué |
|---|---|
| `07_deteccion.sql` | Alertas, stock negativo, bitácora y ventas del producto afectado. |
| `08_reiniciar_demo.sql` | Borra las ventas en línea, alertas, reembolsos y bitácora, y regresa el inventario 128 a 1. |
| `09_monitoreo_en_vivo.sql` | Conexiones de `app_tienda`, bloqueos (`sys.innodb_lock_waits`), stock, bitácora y alertas. |
| `10_atender_incidente.sql` | En una transacción: cancela las ventas sobrantes, registra el reembolso, regresa el stock a 0 y marca la alerta como atendida. |
| `11_reponer_pieza.sql` | Suma 1 pieza al inventario 128 para probar el modo corregido. |

### Usuario de la aplicación

La aplicación se conecta como `app_tienda@localhost`, que solo tiene estos permisos:

- `SELECT` en toda la base
- `INSERT` en `CLIENTE`, `VENTA` y `DETALLE_VENTA`
- `UPDATE` en `INVENTARIO` y `ALERTA`

No puede borrar nada. Por eso `08_reiniciar_demo.sql` y `10_atender_incidente.sql` se corren como `root`.

### Trigger `audita_inventario_update`

Es `AFTER UPDATE` sobre `INVENTARIO` y hace dos cosas:

- Si el stock cambia, inserta en `AUDITORIA_INVENTARIO` el stock anterior, el nuevo, `USER()` y `NOW(3)` (con milisegundos).
- Si el stock nuevo es menor que 0, inserta una alerta `STOCK_NEGATIVO` en `ALERTA`.

Se usa `USER()` y no `CURRENT_USER()` porque dentro de un trigger `CURRENT_USER()` regresa al dueño del trigger y no a quien hizo el cambio.

## Configuración (`config.ini`)

| Sección | Clave | Descripción |
|---|---|---|
| `mysql` | `host`, `user`, `password`, `database` | Conexión. Por defecto `app_tienda` en `localhost`. |
| `tienda` | `sucursal` | Sucursal de la que se muestra y descuenta inventario (1). |
| | `empleado` | Empleado con el que se registran las ventas en línea. |
| | `cliente` | ID del cliente genérico. Los clientes que se registran desde la tienda reciben IDs mayores a este. |
| | `tiempo_pago` | Segundos que tarda el "cobro con tarjeta". Es la ventana en la que se cruzan dos compras. |
| | `control_concurrencia` | `no`: compra con el fallo. `si`: compra con `FOR UPDATE`. |
| `empresa` | `nombre` | Nombre que aparece en el monitor y en el correo. |
| `correo` | `usuario` | Cuenta de Gmail que envía las alertas. |
| | `contrasena_app` | Contraseña de aplicación de Google (16 letras), no la contraseña normal. Si está vacía, no se mandan correos. |
| | `destinatarios` | Correos que reciben la alerta, separados por coma. |

Después de cambiar `config.ini` hay que reiniciar `app.py`.

> Antes de entregar o compartir la carpeta, borra el valor de `contrasena_app` y de `password`.

## Cómo correrlo

```
cd demo
python app.py
```

Al arrancar, la consola muestra:

- **Tienda:** http://localhost:5000. Desde un celular en la misma red Wi-Fi se usa la IP que imprime la consola, por ejemplo `http://192.168.1.70:5000`.
- **Tienda en modo demo:** http://localhost:5000/?demo=1. Agrega un botón que lanza dos compras simultáneas de la chamarra desde la misma página.
- **Monitor:** http://localhost:5000/monitor.

Si Windows pregunta por el firewall, hay que permitir el acceso en redes privadas para que entren los celulares.

## Cómo funciona la compra

`POST /api/comprar` recibe `id_producto` y `nombre`. Primero busca al cliente por nombre y, si no existe, lo da de alta con un ID mayor o igual a `cliente`. Después usa una de estas dos funciones según `control_concurrencia`.

**`comprar_sin_control`** (con el fallo):

1. `SELECT` del stock, sin bloqueo.
2. Si hay al menos 1 pieza, espera `tiempo_pago` segundos.
3. Inserta `VENTA` y `DETALLE_VENTA` y hace `UPDATE INVENTARIO SET Stock = Stock - 1`.

Si dos compras hacen el paso 1 antes de que alguna llegue al 3, las dos ven `Stock = 1` y las dos descuentan. El stock queda en -1.

**`comprar_con_control`** (corregida):

1. `START TRANSACTION`.
2. `SELECT ... FOR UPDATE OF i`, que bloquea el renglón de `INVENTARIO`.
3. Valida el stock, cobra, inserta la venta, descuenta y hace `COMMIT`.

La segunda compra se queda esperando en el paso 2 hasta que la primera termina. Cuando por fin lee el stock, ya ve 0 y responde "Lo sentimos, este artículo se agotó" (HTTP 409).

## API

| Ruta | Método | Respuesta |
|---|---|---|
| `/` | GET | Página de la tienda (`?demo=1` muestra el botón de compra doble). |
| `/monitor` | GET | Panel de monitoreo. |
| `/api/productos` | GET | Lista de los 8 productos con precio, talla, color, `ID_Inventario` y stock. |
| `/api/comprar` | POST | `{"ok": true, "folio": ID_Venta}`, o bien `409` con `mensaje` si se agotó o falló. |
| `/api/estado` | GET | Estado de la base (uptime, conexiones), modo de compra, productos, últimas 8 alertas, últimos 8 renglones de la bitácora, ventas en línea del día y reembolsos del día. Si MySQL no responde, regresa `bd_ok: false`. |

La tienda vuelve a pedir `/api/productos` cada 3 s. El monitor pide `/api/estado` cada 2 s.

## Correo de alertas

Si en `config.ini` hay usuario, contraseña de aplicación y destinatarios, `app.py` arranca el hilo `vigilar_alertas`:

1. Cada 2 s busca en `ALERTA` las filas con `Notificada = 0`.
2. Si hay alguna, arma un correo en texto y HTML con el producto, la sucursal, el stock y la lista de alertas. El logo de Velté va incrustado en el correo.
3. Lo manda por `smtp.gmail.com:465` (SSL) y marca esas alertas con `Notificada = 1`.

Si falla la conexión a MySQL o a Gmail, imprime el error en la consola y espera 30 s antes de volver a intentar.

## Prueba sin la página

`prueba_inventario_negativo.py` reproduce el problema sin Flask y sin tocar `bd_hm_retail`. Crea una base aparte, `hm_pruebas`, con una tabla de una sola pieza, y lanza dos hilos que compran al mismo tiempo. Lo hace tres veces sin control y una vez con `FOR UPDATE`:

```
python prueba_inventario_negativo.py <contraseña_de_root>
```

Resultado esperado: en los intentos sin control las dos cajas dicen `VENDIDA` y el stock final es -1. Con control, una dice `VENDIDA`, la otra `SIN STOCK` y el stock final es 0.

## Problemas comunes

| Síntoma | Causa |
|---|---|
| `Access denied for user 'app_tienda'` | No se corrió `05_preparar_demo.sql` o la contraseña de `config.ini` no coincide. |
| `INSERT command denied ... table 'ALERTA'` o el trigger falla | Falta correr `06_auditoria_triggers.sql`. |
| La tienda dice que se agotó desde el principio | El inventario 128 está en 0 o negativo. Corre `08_reiniciar_demo.sql`. |
| El monitor dice "MySQL no responde" | MySQL está detenido. Revisa el servicio `MySQL80` en Windows. |
| `no se pudo mandar el correo de alerta: (535 ...)` | Gmail rechazó la contraseña. Tiene que ser una contraseña de aplicación con la verificación en dos pasos activa. |
| Las dos compras no se cruzan | Las compras se mandaron con más de `tiempo_pago` segundos de diferencia. Sube `tiempo_pago` o usa `?demo=1`. |
