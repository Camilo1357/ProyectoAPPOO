

import json
import random
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
except Exception:
    pd = None

try:
    import folium
except Exception:
    folium = None

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None

DATA_FILE = Path("parqueadero_data.json")
MAP_OUTPUT_DIR = Path("maps")
MAP_OUTPUT_DIR.mkdir(exist_ok=True)


class Vehiculo:
    def __init__(self, placa: str, tipo: str, hora_entrada: str = None,
                 cliente: str = "normal", visitas: int = 0,
                 lat: float = None, lon: float = None):
        self.placa = placa.upper()
        self.tipo = tipo.lower()
        self.hora_entrada = hora_entrada if hora_entrada else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cliente = cliente.lower()
        self.visitas = visitas
        self.lat = lat
        self.lon = lon

    def to_dict(self):
        return {
            "placa": self.placa,
            "tipo": self.tipo,
            "hora_entrada": self.hora_entrada,
            "cliente": self.cliente,
            "visitas": self.visitas,
            "lat": self.lat,
            "lon": self.lon
        }

    @staticmethod
    def from_dict(d):
        return Vehiculo(
            placa=d.get("placa", ""),
            tipo=d.get("tipo", ""),
            hora_entrada=d.get("hora_entrada", None),
            cliente=d.get("cliente", "normal"),
            visitas=d.get("visitas", 0),
            lat=d.get("lat", None),
            lon=d.get("lon", None)
        )

    def __str__(self):
        loc = f"({self.lat:.5f}, {self.lon:.5f})" if (self.lat is not None and self.lon is not None) else "sin ubicación"
        return f"{self.tipo.upper()} | {self.placa} | Entrada: {self.hora_entrada} | Cliente: {self.cliente} | Ubicación: {loc}"


class Parqueadero:
    tarifas = {"carro": 2000, "moto": 1000, "bici": 500}  # por hora

    def __init__(self, cupos: dict, archivo_json: Path = DATA_FILE):
        self.cupos = cupos.copy()
        self.archivo_json = archivo_json
        self.vehiculos = []  # lista de Vehiculo
        self.historial = []  # lista de registros dict
        self.operador_actual = None
        self.cargar_datos()


    def login(self, operador_name: str):
        self.operador_actual = operador_name
        print(f"Sesión iniciada como '{operador_name}'")

    #  Entradas / Salidas
    def registrar_entrada(self, veh: Vehiculo):
        tipo = veh.tipo
        available = self.cupos.get(tipo, 0)
        if available <= 0:
            return False, ["No hay cupos disponibles para ese tipo de vehículo."]
        # actualizar visitas si existe historial
        visitas_previas = sum(1 for r in self.historial if r["placa"].upper() == veh.placa.upper())
        veh.visitas = visitas_previas + 1
        if veh.visitas >= 5:
            veh.cliente = "frecuente"
        self.vehiculos.append(veh)
        self.cupos[tipo] = available - 1
        self.guardar_datos()

        alerts = []
        if self.cupos[tipo] == 1:
            alerts.append(f"Alerta: queda 1 cupo para {tipo}s.")
        if veh.cliente == "frecuente":
            alerts.append("Cliente frecuente: descuento 10% en salida.")
        return True, alerts

    def registrar_salida(self, placa: str):
        placa = placa.upper()
        for v in list(self.vehiculos):
            if v.placa == placa:
                hora_salida = datetime.now()
                entrada = datetime.strptime(v.hora_entrada, "%Y-%m-%d %H:%M:%S")
                segundos = (hora_salida - entrada).total_seconds()
                horas = max(1, int(segundos // 3600))
                tarifa = self.tarifas.get(v.tipo, 1000)
                total = horas * tarifa
                if v.cliente == "frecuente":
                    total *= 0.9
                elif v.cliente == "mensual":
                    total = 0
                registro = {
                    "placa": v.placa,
                    "tipo": v.tipo,
                    "cliente": v.cliente,
                    "hora_entrada": v.hora_entrada,
                    "hora_salida": hora_salida.strftime("%Y-%m-%d %H:%M:%S"),
                    "horas": horas,
                    "total": float(total),
                    "operador": self.operador_actual,
                    "lat": v.lat,
                    "lon": v.lon
                }
                self.vehiculos.remove(v)
                self.cupos[v.tipo] = self.cupos.get(v.tipo, 0) + 1
                self.historial.append(registro)
                self.guardar_datos()
                return registro
        return None

    #  Consultas
    def ver_ocupacion(self):
        return self.vehiculos

    def ver_cupos(self):
        return self.cupos

    #  Alertas
    def alertas(self):
        alerts = []
        for v in self.vehiculos:
            entrada = datetime.strptime(v.hora_entrada, "%Y-%m-%d %H:%M:%S")
            if datetime.now() - entrada > timedelta(hours=24):
                alerts.append(f"Vehículo {v.placa} lleva más de 24 horas estacionado.")
        for tipo, cupo in self.cupos.items():
            if cupo == 1:
                alerts.append(f"Solo queda 1 cupo para {tipo}s.")
        return alerts

    #  Reportes / CSV
    def exportar_reporte(self, archivo_csv: str = "reporte_parqueadero.csv"):
        if pd is None:
            print("'pandas' no está instalado. Instálalo con: pip install pandas")
            return False
        if not self.historial:
            print("No hay historial para exportar.")
            return False
        df = pd.DataFrame(self.historial)
        df.to_csv(archivo_csv, index=False, encoding="utf-8")
        print(f"Reporte exportado a '{archivo_csv}'")
        return True

    def reporte_por_operador(self):
        if pd is None:
            print("'pandas' no está instalado. Instálalo con: pip install pandas")
            return None
        if not self.historial:
            print("No hay historial.")
            return None
        df = pd.DataFrame(self.historial)
        resumen = df.groupby("operador")["total"].sum()
        return resumen.to_dict()

    #  Gráficas
    def graficar_ocupacion(self):
        if plt is None:
            print("'matplotlib' no está instalado. Instálalo con: pip install matplotlib")
            return
        tipos = [v.tipo for v in self.vehiculos]
        if not tipos:
            print("No hay vehículos estacionados para graficar.")
            return
        serie = {}
        for t in tipos:
            serie[t] = serie.get(t, 0) + 1
        labels = list(serie.keys())
        values = list(serie.values())

        # Barra
        plt.figure()
        plt.bar(labels, values)
        plt.title("Ocupación actual (por tipo)")
        plt.xlabel("Tipo")
        plt.ylabel("Cantidad")
        plt.show()

        # torta
        plt.figure()
        plt.pie(values, labels=labels, autopct="%1.1f%%")
        plt.title("Distribución de vehículos")
        plt.show()

    #  Geolocalización
    def generar_mapa_para_placa(self, placa: str):
        placa = placa.upper()
        # buscar vehículo actualmente estacionado
        v = next((x for x in self.vehiculos if x.placa == placa), None)
        if v is None:
            # buscar última ubicación en historial
            last = None
            for rec in reversed(self.historial):
                if rec.get("placa", "").upper() == placa:
                    last = rec
                    break
            if last is None or last.get("lat") is None or last.get("lon") is None:
                print("No se encontró ubicación para esa placa.")
                return False
            lat, lon = last["lat"], last["lon"]
            label = f"{placa} (Última conocida)"
        else:
            if v.lat is None or v.lon is None:
                print("El vehículo no tiene ubicación registrada.")
                return False
            lat, lon = v.lat, v.lon
            label = f"{placa} (Actualmente estacionado)"

        if folium is None:
            print("'folium' no está instalado. Instálalo con: pip install folium")
            return False

        # Centrar mapa en la ubicación
        m = folium.Map(location=[lat, lon], zoom_start=18)
        folium.Marker(location=[lat, lon], popup=label).add_to(m)

        out_path = MAP_OUTPUT_DIR / f"map_{placa}.html"
        try:
            m.save(str(out_path))
            webbrowser.open(out_path.resolve().as_uri())
            print(f"Mapa generado y abierto en: {out_path}")
            return True
        except Exception as e:
            print(" Error al generar/abrir mapa:", e)
            return False

    #  Persistencia
    def guardar_datos(self):
        payload = {
            "cupos": self.cupos,
            "vehiculos": [v.to_dict() for v in self.vehiculos],
            "historial": self.historial
        }
        with open(self.archivo_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

    def cargar_datos(self):
        if not self.archivo_json.exists():
            return
        try:
            with open(self.archivo_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.cupos = data.get("cupos", self.cupos)
            self.vehiculos = [Vehiculo.from_dict(d) for d in data.get("vehiculos", [])]
            self.historial = data.get("historial", [])
        except Exception as e:
            print("Error cargando datos:", e)


#  Utilidades
def generar_ubicacion_aleatoria_en_campus():
    # aproximacion de coordenadas de la univerisdad de med
    lat = random.uniform(6.2500, 6.2750)
    lon = random.uniform(-75.5800, -75.5600)
    return lat, lon


# Menú consola
def menu():
    parqueadero = Parqueadero({"carro": 50, "moto": 80, "bici": 20})

    print("=== SISTEMA DE PARQUEADERO - Universidad de Medellín ===")
    operador = input("Ingrese su nombre de operador: ").strip()
    if not operador:
        operador = "Operador"
    parqueadero.login(operador)

    while True:
        print("\n--- Menú ---")
        print("1) Registrar entrada")
        print("2) Registrar salida")
        print("3) Listar ocupación actual")
        print("4) Ver cupos disponibles")
        print("5) Ver alertas inteligentes")
        print("6) Exportar reporte CSV (historial)")
        print("7) Reporte por operador")
        print("8) Graficar ocupación")
        print("9) Ver ubicación de un vehículo en el mapa")
        print("10) Salir")

        opt = input("Seleccione opción: ").strip()
        if opt == "1":
            placa = input("Placa: ").strip().upper()
            tipo = input("Tipo (carro/moto/bici): ").strip().lower()
            cliente = input("Cliente (normal/frecuente/mensual) [normal]: ").strip().lower() or "normal"
            usar_ubic = input("¿Desea ingresar ubicación manual? (s/n) [n]: ").strip().lower()
            lat = lon = None
            if usar_ubic == "s":
                try:
                    lat = float(input("Latitud (ej: 6.267): ").strip())
                    lon = float(input("Longitud (ej: -75.567): ").strip())
                except ValueError:
                    print("Coordenadas inválidas, se generará ubicación automática.")
                    lat, lon = generar_ubicacion_aleatoria_en_campus()
            else:
                lat, lon = generar_ubicacion_aleatoria_en_campus()

            veh = Vehiculo(placa=placa, tipo=tipo, cliente=cliente, lat=lat, lon=lon)
            ok, alerts = parqueadero.registrar_entrada(veh)
            if ok:
                print("Entrada registrada.")
                if alerts:
                    for a in alerts:
                        print(a)
            else:
                for a in alerts:
                    print(a)

        elif opt == "2":
            placa = input("Placa a retirar: ").strip().upper()
            registro = parqueadero.registrar_salida(placa)
            if registro:
                print(f"Salida registrada. Total a pagar: ${registro['total']} ({registro['horas']} horas).")
            else:
                print("Vehículo no encontrado.")

        elif opt == "3":
            ocup = parqueadero.ver_ocupacion()
            if not ocup:
                print("Parqueadero vacío.")
            else:
                print("Vehículos estacionados:")
                for v in ocup:
                    print("-", v)

        elif opt == "4":
            print("Cupos disponibles por tipo:")
            for t, c in parqueadero.ver_cupos().items():
                print(f"{t.capitalize()}: {c}")

        elif opt == "5":
            alerts = parqueadero.alertas()
            if not alerts:
                print("No hay alertas.")
            else:
                for a in alerts:
                    print(a)

        elif opt == "6":
            if pd is None:
                print("Instala pandas: pip install pandas")
            else:
                parqueadero.exportar_reporte()

        elif opt == "7":
            resumen = parqueadero.reporte_por_operador()
            if resumen is None:
                print("No hay datos.")
            else:
                print("Ingresos por operador:")
                for op, total in resumen.items():
                    print(f"{op}: ${total}")

        elif opt == "8":
            parqueadero.graficar_ocupacion()

        elif opt == "9":
            placa = input("Placa a localizar: ").strip().upper()
            parqueadero.generar_mapa_para_placa(placa)

        elif opt == "10":
            print("Guardando y saliendo...")
            parqueadero.guardar_datos()
            break
        else:
            print("Opción inválida. Intente de nuevo.")


if __name__ == "__main__":
    menu()