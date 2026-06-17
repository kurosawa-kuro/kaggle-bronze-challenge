"""exp001: LightGBM + ベースライン特徴量"""
import sys; sys.path.insert(0, "src")

from pipelines.ingest import load_data
from pipelines.featurize import make_features
from models.lgbm import train_cv
from pipelines.score import make_submission

train_df, test_df = load_data()
X_train, y_train, X_test = make_features(train_df, test_df)
oof, models = train_cv(X_train, y_train, notes="exp001: lgbm baseline")
make_submission(X_test, models, out_path="submission.csv")
