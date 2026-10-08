from pathlib import Path

import pandas as pd

# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CRUDOS_DIR = BASE_DIR / "crudos"
PROCESADOS_DIR = BASE_DIR / "procesados"

PROCESADOS_DIR.mkdir(exist_ok=True)


# ============================================================
# FUNCIONES GENERALES
# ============================================================


def limpiar_texto(df):
    """
    Elimina espacios innecesarios en columnas de texto.
    Convierte cadenas vacías en valores nulos.
    """
    columnas_texto = df.select_dtypes(include=["object"]).columns

    for columna in columnas_texto:
        df[columna] = df[columna].astype("string").str.strip()
        df[columna] = df[columna].replace("", pd.NA)

    return df


def convertir_booleanos(df, columnas):
    """
    Convierte valores comunes de booleanos a True/False.
    """
    valores = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
        "si": True,
        "sí": True,
        "no": False,
        "yes": True,
        "y": True,
        "n": False,
    }

    for columna in columnas:
        if columna in df.columns:
            df[columna] = (
                df[columna].astype("string").str.strip().str.lower().map(valores)
            )

    return df


def reporte_calidad(nombre, df):
    """
    Muestra información básica de calidad del dataset.
    """
    print("\n" + "=" * 60)
    print(f"REPORTE: {nombre}")
    print("=" * 60)

    print(f"Filas: {len(df)}")
    print(f"Columnas: {len(df.columns)}")

    print("\nValores nulos:")
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0]

    if len(nulos) == 0:
        print("No hay valores nulos.")
    else:
        print(nulos)

    print("\nDuplicados:")
    print(df.duplicated().sum())

    print("\nTipos de datos:")
    print(df.dtypes)


# ============================================================
# TRANSACCIONES
# ============================================================


def preparar_transacciones():

    ruta = CRUDOS_DIR / "transacciones.csv"

    df = pd.read_csv(ruta)

    filas_originales = len(df)

    # Limpiar textos
    df = limpiar_texto(df)

    # Convertir fecha
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    # Convertir columnas numéricas
    columnas_numericas = [
        "linea",
        "usuario_id",
        "cantidad",
        "precio_unitario",
        "descuento",
        "total",
    ]

    for columna in columnas_numericas:
        df[columna] = pd.to_numeric(df[columna], errors="coerce")

    # El pedido y la línea identifican una línea de compra
    df = df.drop_duplicates(subset=["pedido_id", "linea"], keep="first")

    # Las columnas fundamentales no deberían quedar vacías
    df = df.dropna(subset=["pedido_id", "linea", "usuario_id", "sku"])

    # Validaciones básicas
    df.loc[df["cantidad"] < 0, "cantidad"] = pd.NA
    df.loc[df["precio_unitario"] < 0, "precio_unitario"] = pd.NA
    df.loc[df["descuento"] < 0, "descuento"] = pd.NA

    # Guardar
    salida = PROCESADOS_DIR / "transacciones_limpias.csv"
    df.to_csv(salida, index=False)

    print("\nTRANSACCIONES")
    print(f"Filas originales: {filas_originales}")
    print(f"Filas finales: {len(df)}")
    print(f"Guardado en: {salida}")

    reporte_calidad("TRANSACCIONES", df)

    return df


# ============================================================
# USUARIOS
# ============================================================


def preparar_usuarios():

    ruta = CRUDOS_DIR / "usuarios.csv"

    df = pd.read_csv(ruta)

    filas_originales = len(df)

    df = limpiar_texto(df)

    # Fecha de registro
    df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce")

    # Edad
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce")

    # Booleanos
    df = convertir_booleanos(df, ["email_valido", "acepta_marketing"])

    # Un usuario debería tener un único registro
    df = df.drop_duplicates(subset=["usuario_id"], keep="first")

    # ID obligatorio
    df = df.dropna(subset=["usuario_id"])

    # Validación básica de edad
    df.loc[(df["edad"] < 0) | (df["edad"] > 120), "edad"] = pd.NA

    salida = PROCESADOS_DIR / "usuarios_limpios.csv"
    df.to_csv(salida, index=False)

    print("\nUSUARIOS")
    print(f"Filas originales: {filas_originales}")
    print(f"Filas finales: {len(df)}")
    print(f"Guardado en: {salida}")

    reporte_calidad("USUARIOS", df)

    return df


# ============================================================
# PRODUCTOS
# ============================================================


def preparar_productos():

    ruta = CRUDOS_DIR / "productos.csv"

    df = pd.read_csv(ruta)

    filas_originales = len(df)

    df = limpiar_texto(df)

    # Columnas numéricas
    columnas_numericas = ["precio_lista", "costo", "stock"]

    for columna in columnas_numericas:
        df[columna] = pd.to_numeric(df[columna], errors="coerce")

    # Fecha
    df["fecha_alta"] = pd.to_datetime(df["fecha_alta"], errors="coerce")

    # Booleano
    df = convertir_booleanos(df, ["activo"])

    # Un SKU debería identificar un producto
    df = df.drop_duplicates(subset=["sku"], keep="first")

    # SKU obligatorio
    df = df.dropna(subset=["sku"])

    # Valores imposibles
    df.loc[df["precio_lista"] < 0, "precio_lista"] = pd.NA
    df.loc[df["costo"] < 0, "costo"] = pd.NA
    df.loc[df["stock"] < 0, "stock"] = pd.NA

    salida = PROCESADOS_DIR / "productos_limpios.csv"
    df.to_csv(salida, index=False)

    print("\nPRODUCTOS")
    print(f"Filas originales: {filas_originales}")
    print(f"Filas finales: {len(df)}")
    print(f"Guardado en: {salida}")

    reporte_calidad("PRODUCTOS", df)

    return df


# ============================================================
# CLICKSTREAM
# ============================================================


def preparar_clickstream():

    ruta = CRUDOS_DIR / "clickstream.csv"

    df = pd.read_csv(ruta)

    filas_originales = len(df)

    df = limpiar_texto(df)

    # Timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Evento único
    df = df.drop_duplicates(subset=["evento_id"], keep="first")

    # ID del evento obligatorio
    df = df.dropna(subset=["evento_id"])

    salida = PROCESADOS_DIR / "clickstream_limpio.csv"
    df.to_csv(salida, index=False)

    print("\nCLICKSTREAM")
    print(f"Filas originales: {filas_originales}")
    print(f"Filas finales: {len(df)}")
    print(f"Guardado en: {salida}")

    reporte_calidad("CLICKSTREAM", df)

    return df


# ============================================================
# VALIDACIÓN ENTRE DATASETS
# ============================================================


def validar_relaciones(transacciones, usuarios, productos, clickstream):

    print("\n" + "=" * 60)
    print("VALIDACIÓN DE RELACIONES")
    print("=" * 60)

    usuarios_validos = set(usuarios["usuario_id"].dropna())

    productos_validos = set(productos["sku"].dropna())

    # Usuarios presentes en transacciones
    usuarios_transacciones = set(transacciones["usuario_id"].dropna())

    usuarios_no_encontrados = usuarios_transacciones - usuarios_validos

    print(
        f"Usuarios de transacciones que no existen en usuarios: "
        f"{len(usuarios_no_encontrados)}"
    )

    # Productos presentes en transacciones
    productos_transacciones = set(transacciones["sku"].dropna())

    productos_no_encontrados = productos_transacciones - productos_validos

    print(
        f"SKUs de transacciones que no existen en productos: "
        f"{len(productos_no_encontrados)}"
    )

    # Usuarios del clickstream
    usuarios_clickstream = set(clickstream["usuario_id"].dropna())

    usuarios_click_no_encontrados = usuarios_clickstream - usuarios_validos

    print(
        f"Usuarios de clickstream que no existen en usuarios: "
        f"{len(usuarios_click_no_encontrados)}"
    )


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================


def main():

    print("\nINICIANDO PREPARACIÓN DE DATOS")

    transacciones = preparar_transacciones()
    usuarios = preparar_usuarios()
    productos = preparar_productos()
    clickstream = preparar_clickstream()

    validar_relaciones(transacciones, usuarios, productos, clickstream)

    print("\n" + "=" * 60)
    print("PROCESO FINALIZADO")
    print("=" * 60)


if __name__ == "__main__":
    main()
