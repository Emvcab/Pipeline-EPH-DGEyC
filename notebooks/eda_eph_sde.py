"""
EDA — EPH Santiago del Estero · 2023-2025
Práctica Profesionalizante II · ITSE 2026
Grupo: Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas

Versión script para VSCode/local. Requiere historico_SDE.csv en la carpeta.
Uso:  python eda_eph_sde.py
Genera 4 gráficos PNG.
"""


# ────────────────────────────────────────────────────────────────────
# # Análisis Exploratorio de Datos (EDA) — EPH Santiago del Estero
# ## Evolución del mercado laboral · 2023-2025
# 
# **Práctica Profesionalizante II — ITSE 2026**
# **Grupo:** Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas
# **Entidad:** Dirección General de Estadística y Censos — Santiago del Estero
# 
# ---
# 
# ### Sobre este análisis
# 
# Este EDA se enfoca en **cuatro visualizaciones clave** que resumen la evolución del
# mercado laboral del aglomerado Santiago del Estero — La Banda (código 18):
# 
# 1. **Serie de tiempo** de actividad y empleo oficiales
# 2. **Informalidad laboral** trimestre a trimestre
# 3. **Ingresos y no respuesta** de ingresos
# 4. **Comparación interanual** (mismo trimestre entre años)
# 
# Se priorizó la claridad interpretativa por sobre la cantidad de gráficos: con solo
# 12 trimestres de datos, un conjunto acotado de visualizaciones bien elegidas comunica
# mejor que una batería extensa de gráficos estadísticos.
# 
# **Fuente:** histórico generado por el pipeline ETL a partir de microdatos EPH-INDEC.


# ────────────────────────────────────────────────────────────────────
# ## 1. Preparación del entorno y carga de datos

# Este notebook funciona tanto en Google Colab como en VSCode/Jupyter local.
# Detecta el entorno automáticamente.

import sys

EN_COLAB = "google.colab" in sys.modules

# Instalar dependencias solo si hace falta (Colab las trae casi todas)
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "pandas", "matplotlib"], check=True)
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick

print("Entorno detectado:", "Google Colab" if EN_COLAB else "Local (VSCode/Jupyter)")

import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

EN_COLAB = False
candidatos = [
    Path("historico_SDE.csv"),
    Path("results/historico_SDE.csv"),
    Path("data_snapshot/historico_SDE.csv"),
    Path("../results/historico_SDE.csv"),
    Path("../data_snapshot/historico_SDE.csv"),
]
ARCHIVO = next((str(p) for p in candidatos if p.exists()), "historico_SDE.csv")
df = pd.read_csv(ARCHIVO)
df = df.sort_values(["anio","trimestre"]).reset_index(drop=True)
print(f"Cargados {len(df)} trimestres desde: {ARCHIVO}")

# Configuración visual común a todos los gráficos

plt.rcParams.update({
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})

AZUL    = "#1F3A6E"
VERDE   = "#1D6A3A"
NARANJA = "#C47A00"
ROJO    = "#922B21"
VIOLETA = "#5B2C8C"
GRIS    = "#666666"

x = list(range(len(df)))
periodos = df["periodo"]

print("Configuración lista.")


# ────────────────────────────────────────────────────────────────────
# ## 2. Descripción general

# Resumen rápido de los indicadores clave

cols_resumen = ["periodo", "tasa_actividad_oficial", "tasa_empleo_oficial",
                "tasa_desocupacion", "proporcion_inactiva_total", "tasa_informalidad",
                "tasa_no_respuesta_ingresos_ocupados",
                "ingreso_promedio_ponderado_observado"]
cols_disponibles = [c for c in cols_resumen if c in df.columns]

print("Estadísticas descriptivas de los indicadores principales:\n")
print(df[[c for c in cols_disponibles if c != "periodo"]].describe().round(2).to_string())

print(f"\nMuestra promedio por trimestre: {df['n_personas_muestra'].mean():.0f} personas")
print(f"Población representada (último trim): {df['poblacion_expandida_total'].iloc[-1]:,.0f}")


# ────────────────────────────────────────────────────────────────────
# ## 3. Gráfico 1 — Serie de tiempo del mercado laboral
# 
# Muestra la evolución trimestral de la actividad y el empleo oficiales. Es la
# visualización central: permite ver la tendencia general del mercado laboral.

fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(x, df["tasa_actividad_oficial"], color=AZUL, marker="o", linewidth=2.2,
        label="Actividad oficial")
ax.plot(x, df["tasa_empleo_oficial"], color=VERDE, marker="s", linewidth=2.2,
        label="Empleo oficial")

ax.set_xticks(x)
ax.set_xticklabels(periodos, rotation=45, ha="right", fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.set_ylabel("% de la población total", fontsize=10)
ax.set_title("Evolución del mercado laboral — Santiago del Estero · 2023-2025",
             fontsize=13, fontweight="bold", pad=12)
ax.legend(loc="center right", fontsize=10, frameon=True)

# Separadores de año
for sep in [3.5, 7.5]:
    ax.axvline(sep, color="gray", linestyle=":", alpha=0.4)

plt.tight_layout()
plt.savefig("eda_1_mercado_laboral.png", bbox_inches="tight", dpi=140)
plt.show()

# Lectura automática
act_ini, act_fin = df["tasa_actividad_oficial"].iloc[0], df["tasa_actividad_oficial"].iloc[-1]
print(f"\nLa actividad pasó de {act_ini:.1f}% a {act_fin:.1f}% "
      f"({'▼' if act_fin < act_ini else '▲'} {abs(act_fin-act_ini):.1f} pp)")


# ────────────────────────────────────────────────────────────────────
# ## 4. Gráfico 2 — Informalidad laboral
# 
# Proporción de ocupados que trabajan sin registro. Disponible desde el 4T2023, cuando
# el INDEC incorporó la variable EMPLEO. Es el hallazgo más relevante para política social.

fig, ax = plt.subplots(figsize=(12, 4.5))

# Solo trimestres con dato de informalidad
mask = df["tasa_informalidad"].notna()
x_inf = [i for i, m in zip(x, mask) if m]
periodos_inf = periodos[mask]
valores_inf = df["tasa_informalidad"][mask]

barras = ax.bar(x_inf, valores_inf, color=NARANJA, alpha=0.85,
                edgecolor="white", linewidth=1.5)

promedio = valores_inf.mean()
ax.axhline(promedio, color=GRIS, linestyle="--", linewidth=1.5,
           label=f"Promedio: {promedio:.1f}%")

# Etiquetas sobre cada barra
for xi, v in zip(x_inf, valores_inf):
    ax.text(xi, v + 0.8, f"{v:.0f}", ha="center", fontsize=8, color=GRIS)

ax.set_xticks(x_inf)
ax.set_xticklabels(periodos_inf, rotation=45, ha="right", fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.set_ylim(0, max(valores_inf) + 8)
ax.set_ylabel("% de ocupados sin registro", fontsize=10)
ax.set_title("Informalidad laboral — Santiago del Estero · desde 4T2023",
             fontsize=13, fontweight="bold", pad=12)
ax.legend(loc="upper right", fontsize=10)

plt.tight_layout()
plt.savefig("eda_2_informalidad.png", bbox_inches="tight", dpi=140)
plt.show()

print(f"\nInformalidad promedio del período: {promedio:.1f}%")
print(f"Más de la mitad de los ocupados trabaja sin registro en todos los trimestres.")


# ────────────────────────────────────────────────────────────────────
# ## 5. Gráfico 3 — Ingresos y no respuesta
# 
# Combina dos series en un mismo gráfico con doble eje: la evolución del ingreso promedio
# ponderado (barras) y la tasa de no respuesta de ingresos (línea). Esta última es el
# indicador de calidad que requiere seguimiento periódico.

fig, ax1 = plt.subplots(figsize=(12, 5))

# Eje izquierdo: ingreso ponderado (barras)
ax1.bar(x, df["ingreso_promedio_ponderado_observado"], color=VERDE, alpha=0.30,
        label="Ingreso promedio ponderado")
ax1.set_xticks(x)
ax1.set_xticklabels(periodos, rotation=45, ha="right", fontsize=9)
ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
ax1.set_ylabel("Ingreso mensual ($)", fontsize=10, color=VERDE)
ax1.tick_params(axis="y", labelcolor=VERDE)

# Eje derecho: no respuesta (línea)
ax2 = ax1.twinx()
ax2.plot(x, df["tasa_no_respuesta_ingresos_ocupados"], color=ROJO, marker="o",
         linewidth=2.5, label="No respuesta de ingresos")
ax2.set_ylabel("% de ocupados que no responden", fontsize=10, color=ROJO)
ax2.tick_params(axis="y", labelcolor=ROJO)
ax2.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax2.grid(False)

ax1.set_title("Ingresos y no respuesta de ingresos — Santiago del Estero · 2023-2025",
              fontsize=13, fontweight="bold", pad=12)

# Leyenda combinada
lineas1, labels1 = ax1.get_legend_handles_labels()
lineas2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lineas1 + lineas2, labels1 + labels2, loc="upper left", fontsize=9)

plt.tight_layout()
plt.savefig("eda_3_ingresos_no_respuesta.png", bbox_inches="tight", dpi=140)
plt.show()

nr_ini = df["tasa_no_respuesta_ingresos_ocupados"].iloc[0]
nr_fin = df["tasa_no_respuesta_ingresos_ocupados"].iloc[-1]
print(f"\nNo respuesta de ingresos: {nr_ini:.1f}% → {nr_fin:.1f}%")
print("La no respuesta se monitorea como indicador de calidad de los microdatos públicos.")


# ────────────────────────────────────────────────────────────────────
# ## 6. Gráfico 4 — Comparación interanual
# 
# Compara el mismo trimestre entre distintos años. Permite detectar patrones estacionales
# y confirmar tendencias más allá de la variación trimestre a trimestre.

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
fig.suptitle("Comparación interanual — mismo trimestre entre años",
             fontsize=13, fontweight="bold", y=1.02)

indicadores = [
    ("tasa_actividad_oficial", "Tasa de actividad oficial (%)", AZUL),
    ("proporcion_inactiva_total", "Proporción inactiva total (%)", VIOLETA),
    ("tasa_no_respuesta_ingresos_ocupados", "No respuesta ingresos (%)", ROJO),
]

for ax, (col, titulo, color) in zip(axes, indicadores):
    data = df.groupby(["trimestre", "anio"])[col].first().unstack()
    for anio in data.columns:
        ax.plot(data.index, data[anio], marker="o", linewidth=2,
                markersize=7, label=str(int(anio)))
    ax.set_title(titulo, fontsize=10, fontweight="bold")
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(["T1", "T2", "T3", "T4"])
    ax.set_xlabel("Trimestre", fontsize=9)
    ax.legend(title="Año", fontsize=8)

plt.tight_layout()
plt.savefig("eda_4_interanual.png", bbox_inches="tight", dpi=140)
plt.show()

print("\nLa comparación interanual confirma las tendencias:")
print("- Actividad: cae año a año")
print("- Inactividad: sube año a año")
print("- No respuesta: claramente más alta en 2025")


# ────────────────────────────────────────────────────────────────────
# ## 7. Conclusiones

# Resumen automático de hallazgos

primer, ultimo = df.iloc[0], df.iloc[-1]

print("=" * 58)
print(f"RESUMEN — {primer['periodo']} → {ultimo['periodo']}")
print("=" * 58)

for col, label in [
    ("tasa_actividad_oficial",             "Actividad oficial "),
    ("tasa_empleo_oficial",                "Empleo oficial    "),
    ("tasa_desocupacion",                  "Desocupación      "),
    ("proporcion_inactiva_total",          "Prop. inactiva    "),
    ("tasa_no_respuesta_ingresos_ocupados","No resp. ingresos "),
]:
    vi, vf = primer[col], ultimo[col]
    signo = "▲" if vf > vi else "▼"
    print(f"  {label} {vi:>6.1f}%  →  {vf:>6.1f}%   {signo} {abs(vf-vi):.1f} pp")

# Informalidad (desde 4T2023)
inf = df[df["tasa_informalidad"].notna()]
if len(inf) > 0:
    print(f"  Informalidad       {inf['tasa_informalidad'].iloc[0]:>6.1f}%  →  "
          f"{inf['tasa_informalidad'].iloc[-1]:>6.1f}%   (promedio {inf['tasa_informalidad'].mean():.1f}%)")

print("=" * 58)


# ────────────────────────────────────────────────────────────────────
# ### Principales hallazgos
# 
# **1. La participación laboral cae de forma sostenida** — la actividad bajó ~6 puntos
# porcentuales en tres años, con la inactividad subiendo en espejo.
# 
# **2. La desocupación es estructuralmente baja** — nunca superó el 1,5%, pero debe leerse
# junto a la alta informalidad: no refleja pleno empleo sino absorción informal.
# 
# **3. La informalidad es persistente y elevada** — más de la mitad de los ocupados trabaja
# sin registro en todos los trimestres disponibles.
# 
# **4. La no respuesta de ingresos creció en 2025** — de menos del 1% en 2023 a valores de
# 3-4% en 2025. Este patrón se mantiene como indicador de calidad para seguimiento.
# 
# ---
# *EDA — Práctica Profesionalizante II · ITSE 2026*
# *Grupo: Achaval · Cabaña · Constantinidi · Gomez · Pinto Villegas*


# ────────────────────────────────────────────────────────────────────
# ## 8. Descarga de gráficos (solo Colab)

print("Los 4 gráficos PNG están guardados en la carpeta actual.")
