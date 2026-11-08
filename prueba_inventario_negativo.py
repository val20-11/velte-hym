# prueba: dos cajas compran la ultima pieza al mismo tiempo
# usa una base aparte (hm_pruebas) para no tocar bd_hm_retail
# uso: python prueba_inventario_negativo.py <password_root>
import sys
import threading
import time
import mysql.connector

PWD = sys.argv[1] if len(sys.argv) > 1 else ""


def conectar(db=None):
    return mysql.connector.connect(host="localhost", user="root", password=PWD, database=db)


def preparar():
    cn = conectar()
    cur = cn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS hm_pruebas")
    cur.execute("USE hm_pruebas")
    cur.execute("DROP TABLE IF EXISTS inventario_prueba")
    cur.execute("CREATE TABLE inventario_prueba (ID_Inventario INT PRIMARY KEY, Stock INT NOT NULL)")
    cur.execute("INSERT INTO inventario_prueba VALUES (1, 1)")  # ultima pieza
    cn.commit()
    cn.close()


def stock_actual():
    cn = conectar("hm_pruebas")
    cur = cn.cursor()
    cur.execute("SELECT Stock FROM inventario_prueba WHERE ID_Inventario = 1")
    s = cur.fetchone()[0]
    cn.close()
    return s


# version con el fallo: revisa stock, "procesa el pago" y luego descuenta
def compra_sin_control(caja, resultados):
    cn = conectar("hm_pruebas")
    cur = cn.cursor()
    cur.execute("SELECT Stock FROM inventario_prueba WHERE ID_Inventario = 1")
    stock = cur.fetchone()[0]
    if stock >= 1:
        time.sleep(2)  # simula el cobro con tarjeta
        cur.execute("UPDATE inventario_prueba SET Stock = Stock - 1 WHERE ID_Inventario = 1")
        cn.commit()
        resultados[caja] = "VENDIDA"
    else:
        resultados[caja] = "SIN STOCK"
    cn.close()


# version corregida: transaccion con SELECT ... FOR UPDATE
def compra_con_control(caja, resultados):
    cn = conectar("hm_pruebas")
    cur = cn.cursor()
    cn.start_transaction()
    cur.execute("SELECT Stock FROM inventario_prueba WHERE ID_Inventario = 1 FOR UPDATE")
    stock = cur.fetchone()[0]
    if stock >= 1:
        time.sleep(2)
        cur.execute("UPDATE inventario_prueba SET Stock = Stock - 1 WHERE ID_Inventario = 1")
        cn.commit()
        resultados[caja] = "VENDIDA"
    else:
        cn.rollback()
        resultados[caja] = "SIN STOCK"
    cn.close()


def correr(funcion, titulo):
    preparar()
    resultados = {}
    hilos = [threading.Thread(target=funcion, args=(f"Caja {i}", resultados)) for i in (1, 2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    print(f"\n== {titulo} ==")
    for caja, r in sorted(resultados.items()):
        print(f"  {caja}: {r}")
    print(f"  Stock final: {stock_actual()}")


if __name__ == "__main__":
    for i in range(1, 4):
        correr(compra_sin_control, f"SIN control (intento {i})")
    correr(compra_con_control, "CON control (FOR UPDATE)")
