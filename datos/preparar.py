"""Limpieza documentada de los datos procesados de Nexus.

Este script reproduce, de forma reproducible y sin alterar la estructura de los
archivos, las correcciones de calidad aplicadas a datos/procesados/:

1. productos_limpio.csv
   - precio_lista nulo o <= 0  -> imputado con la mediana de su categoria.
                                 Si la categoria no tiene mediana valida, se usa la mediana global.
   - stock nulo                -> 0.
   - stock negativo            -> 0 si el producto NO es recomendable;
                                -> stock_minimo (3, segun metadatos.pkl) si SI es recomendable.

2. usuarios_limpio.csv
   - email_valido nulo         -> "desconocido".

3. transacciones_limpio.csv y clickstream_limpio.csv
   - Solo se verificaron las reglas de calidad de tests/test_datos.py
     (sin huorfanos, cantidades positivas, montos no negativos, fechas validas,
     sin duplicados). No se modificaron.

Importante: este script NO toca los notebooks ni el codigo de la API.
Solo corrige valores dentro de los CSV existentes, conservando columnas,
orden y cantidad de filas.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "datos" / "procesados"
BACKUP = Path(__file__).resolve().parent.parent / "datos" / "procesados_backup_limpieza"
STOCK_MINIMO = 3  # definido en metadatos.pkl y exigido por tests/test_datos.py


def respaldar_csvs() -> None:
    """Copia los 4 CSV originales a una carpeta de respaldo antes de modificar."""
    BACKUP.mkdir(parents=True, exist_ok=True)
    for nombre in [
        "usuarios_limpio.csv",
        "productos_limpio.csv",
        "clickstream_limpio.csv",
        "transacciones_limpio.csv",
    ]:
        src = BASE / nombre
        dst = BACKUP / nombre
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    print(f"Respaldados los 4 CSV en {BACKUP}")


def limpiar_productos() -> pd.DataFrame:
    """Corrige precios invalidos y stocks negativos/nulos en productos_limpio.csv."""
    path = BASE / "productos_limpio.csv"
    df = pd.read_csv(path)

    columnas_antes = list(df.columns)
    filas_antes = len(df)
    skus_dup_antes = df["sku"].duplicated().sum()

    recomendable = df["recomendable"] == True

    # --- Precio lista: imputar nulos y ceros con mediana por categoria ---
    validos = df[df["precio_lista"] > 0]
    mediana_por_categoria = validos.groupby("categoria")["precio_lista"].median()
    mediana_global = validos["precio_lista"].median()

    invalido_precio = df["precio_lista"].isna() | (df["precio_lista"] <= 0)
    df.loc[invalido_precio, "precio_lista"] = (
        df.loc[invalido_precio, "categoria"]
        .map(mediana_por_categoria)
        .fillna(mediana_global)
    )

    # --- Stock: nulos a 0; negativos a 0 (no recomendables) o stock_minimo (recomendables) ---
    df["stock"] = df["stock"].fillna(0)
    stock_negativo = df["stock"] < 0
    df.loc[stock_negativo & ~recomendable, "stock"] = 0
    df.loc[recomendable & (df["stock"] < STOCK_MINIMO), "stock"] = STOCK_MINIMO

    df["stock"] = df["stock"].astype(float)

    print("=== PRODUCTOS LIMPIEZA ===")
    print(f"Filas: {filas_antes} -> {len(df)} (sin cambios)")
    print(f"Columnas: {columnas_antes} (sin cambios)")
    print(f"SKU duplicados antes/despues: {skus_dup_antes} / {df['sku'].duplicated().sum()}")
    print(f"Precios <= 0 o nulos corregidos: {int(invalido_precio.sum())}")
    print(f"Stocks negativos corregidos: {int(stock_negativo.sum())}")
    print(f"Stocks nulos corregidos: {int(df['stock'].isna().sum())}")
    print(f"Precios <= 0 o nulos restantes: {int((df['precio_lista'].isna() | (df['precio_lista'] <= 0)).sum())}")
    print(f"Stocks negativos restantes: {int((df['stock'] < 0).sum())}")

    df.to_csv(path, index=False)
    return df


def limpiar_usuarios() -> pd.DataFrame:
    """Rellena email_valido nulos con 'desconocido' en usuarios_limpio.csv."""
    path = BASE / "usuarios_limpio.csv"
    df = pd.read_csv(path)

    columnas_antes = list(df.columns)
    filas_antes = len(df)

    nulos_email = int(df["email_valido"].isna().sum())
    df["email_valido"] = df["email_valido"].fillna("desconocido")

    print("=== USUARIOS LIMPIEZA ===")
    print(f"Filas: {filas_antes} -> {len(df)} (sin cambios)")
    print(f"Columnas: {columnas_antes} (sin cambios)")
    print(f"email_valido nulos corregidos: {nulos_email}")
    print(f"email_valido nulos restantes: {int(df['email_valido'].isna().sum())}")
    print(f"Valores de email_valido: {df['email_valido'].unique().tolist()}")

    df.to_csv(path, index=False)
    return df


def main() -> None:
    respaldar_csvs()
    limpiar_productos()
    limpiar_usuarios()
    print("\nLimpieza terminada. Estructura de los CSV sin cambios.")


if __name__ == "__main__":
    main()
