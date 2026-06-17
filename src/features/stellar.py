"""Stellar Class コンペ用 FE。encode() 前に呼ぶこと（文字列カラムを使うため）。"""
import numpy as np
import pandas as pd


def add_stellar_fe(
    X_train: pd.DataFrame, X_test: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    for df in (X_train, X_test):
        # SDSS 測光色指数（クラス間で分布が大きく異なる天文学的特徴量）
        df["u_g"] = df["u"] - df["g"]
        df["g_r"] = df["g"] - df["r"]
        df["r_i"] = df["r"] - df["i"]
        df["i_z"] = df["i"] - df["z"]

        # spectral_type × galaxy_population 交差特徴（encode 前に文字列で作る）
        df["spectral_pop"] = df["spectral_type"].astype(str) + "_" + df["galaxy_population"].astype(str)

        # redshift 10 分位ビン（非線形パターンを補助）
        df["redshift_bin"] = pd.qcut(df["redshift"], q=10, labels=False, duplicates="drop")

    return X_train, X_test
