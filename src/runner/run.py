"""現在の実験エントリポイント。
モデルや特徴量を変えるときはここの import を 1〜2 行変える。
実験が確定したら notebooks/ にコピーして保存する。
"""
from pipelines.ingest import load_data
from pipelines.featurize import make_features
from models.lgbm import train_cv
from pipelines.score import make_submission

BEST_PARAMS = {
    "num_leaves": 158,
    "min_child_samples": 40,
    "learning_rate": 0.042387,
    "feature_fraction": 0.638674,
    "bagging_fraction": 0.980003,
    "lambda_l1": 1.918585,
    "lambda_l2": 1e-8,
}

def main() -> None:
    train_df, test_df = load_data()
    X_train, y_train, X_test = make_features(train_df, test_df)
    oof, models = train_cv(X_train, y_train, params=BEST_PARAMS, notes="lgbm optuna best")
    make_submission(X_test, models, out_path="submission.csv", original_test=test_df)


# import では実行しない（`make run` = python -m runner.run のときだけ走る）。
if __name__ == "__main__":
    main()
