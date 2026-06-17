"""現在の実験エントリポイント。
モデルや特徴量を変えるときはここの import を 1〜2 行変える。
実験が決まったら experiments/ にコピーして保存する。
"""
import sys; sys.path.insert(0, "src")

from preprocess import load_data
from features.base import make_features       # ← FE を変えるときここを差し替える
from models.lgbm import train_cv              # ← モデルを変えるときここを差し替える
from predict import make_submission

train_df, test_df = load_data()
X_train, y_train, X_test = make_features(train_df, test_df)
oof, models = train_cv(X_train, y_train, notes="run: lgbm baseline")
make_submission(X_test, models, out_path="submission.csv")
