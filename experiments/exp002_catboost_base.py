"""exp002: CatBoost + ベースライン特徴量"""
import sys; sys.path.insert(0, "src")

from preprocess import load_data
from features.base import make_features
from models.catboost_ import train_cv
from predict import make_submission

train_df, test_df = load_data()
X_train, y_train, X_test = make_features(train_df, test_df)
oof, models = train_cv(X_train, y_train, notes="exp002: catboost baseline")
make_submission(X_test, models, out_path="submission.csv")
