"""exp003: LightGBM + CatBoost の単純平均アンサンブル"""
import sys; sys.path.insert(0, "src")

from preprocess import load_data
from features.base import make_features
from models import lgbm, catboost_
from models.ensemble import average
from predict import make_submission, predict

train_df, test_df = load_data()
X_train, y_train, X_test = make_features(train_df, test_df)

oof_lgbm, models_lgbm = lgbm.train_cv(X_train, y_train, notes="exp003: lgbm part")
oof_cat,  models_cat  = catboost_.train_cv(X_train, y_train, notes="exp003: catboost part")

test_lgbm = predict(X_test, models_lgbm)
test_cat  = predict(X_test, models_cat)

final = average([test_lgbm, test_cat])

import pandas as pd
sub = pd.DataFrame({"MedHouseVal": final})
sub.to_csv("submission.csv", index=False)
print(f"[ensemble] submission saved → submission.csv  shape={sub.shape}")
