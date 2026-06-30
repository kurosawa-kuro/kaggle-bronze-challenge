# Superseded: Vertex-ready 初期方針メモ

Status: Superseded

このメモは ADR 0001 時点の「Custom Job + GCS + Artifact Registry に絞る」初期方針メモ。
現在は ADR 0002 により、非 DL/GPU の Vertex/GCP マネージド機能をより広く使う方針へ進んでいる。

現コードでは以下も実装済み:
- `src/runner/` への entrypoint 集約
- BigQuery `experiments` / `cost_estimates`
- seed 平均
- sweep
- Optuna tune
- Vertex Hyperparameter Tuning
- cost tracking / Discord notify

したがって、このメモを active な設計根拠として使わない。
歴史的な判断ログとしてのみ残す。

結論

これで方針確定で良いです。
Kaggleブロンズ目的に対して、最も勝率が高いのは 新規構築ではなく、過去GCP資産を流用して gcp-vertex-kaggle を Vertex-ready 実験ランナー化すること です。

特に今回の仕様は、目的がズレていません。

GCP/Vertex = 本番MLOps基盤ではない
GCP/Vertex = Kaggle実験を外に投げる並列・overnightランナー

添付の方針でも、GCP利用を Custom Job + GCS + Artifact Registry に絞り、Feature Store / Pipelines / Endpoint / Model Registry / Monitoring を明確に除外しています。これはブロンズ狙いとして正しい切り方です。

理由

今回の勝ち筋は、「GCPを使う」ではなく「過去資産で配線コストを下げる」 です。

添付内容を見る限り、流用できる資産がかなり揃っています。

- GCS成果物 upload/download
- コンテナ内GCP認証
- argparseベースのtrain CLI
- uv slim Dockerfile
- Artifact Registry push
- 軽量config precedence
- Makefile CLI UX
- Vertex job状態ポーリングの参考

一方で、Vertex Custom Job投入コードだけは流用元なしで新規 と明記されています。

これはかなり良い整理です。
作るべき新規部分が狭い。

つまり、実装リスクはこうです。

大きい新規開発:
× GCP ML基盤を作る
× Feature Storeを作る
× Vertex Pipelinesを作る

小さい新規開発:
○ vertex_run.pyだけ新規
○ train.pyをconfig駆動へ寄せる
○ run_id成果物契約を固定する

この差は大きいです。

有力シナリオ

このタスクは、次の順番で切るのが一番安全です。

KGL-BRONZE-001:
skeleton 配線

KGL-BRONZE-002:
train.py --config --run-id のlocal実行

KGL-BRONZE-003:
run_id成果物契約の固定

KGL-BRONZE-004:
Artifact Registry学習コンテナ

KGL-BRONZE-005:
vertex_run.py Custom Job投入

KGL-BRONZE-006:
collect.py GCS回収

KGL-BRONZE-007:
submit.py / make submit 整理

最初にやるべきは、モデル性能ではありません。

空成果物で配線を固定することです。

添付でも、ビジネスロジックを入れる前に train.py --config がダミー成果物を出し、vertex_run.py と collect.py のパス対応を固定する方針になっています。これは正しいです。

破綻条件

破綻条件は、すでに文書内に出ています。

投入までが面倒になること。

ここは最重要です。

make smoke CONFIG=configs/lgbm_baseline.yaml
make train-local CONFIG=configs/lgbm_baseline.yaml
make train-vertex CONFIG=configs/catboost_seed_avg.yaml
make collect RUN_ID=latest
make submit RUN_ID=latest

このUXが崩れたら、Vertexは優位ではなく負債になります。

もう1つの破綻条件は、GKEに寄せたくなることです。
文書では、GKEのコード資産は使うが、実行基盤としてGKEクラスタは使わない、と切っています。これも正解です。ブロンズ規模では、GKEはバッチ実験のスループットより運用負荷を増やします。

実務・行動への影響

この方針なら、Claude / Code への依頼もかなり明確になります。

最初に投げるべき作業はこれです。

KGL-BRONZE-001: Vertex-ready 実験ランナー skeleton 配線

目的:
同一 train.py を local / Vertex Custom Job で動かし、
同一 run_id 成果物レイアウトを出す。

やること:
- train.py --config --run-id を追加
- ダミー成果物を outputs/runs/{competition}/{run_id}/ に出す
- configs/lgbm_baseline.yaml を最小作成
- Makefile に smoke / train-local を追加
- collect.py はまだdry-runでも可
- vertex_run.py はdry-runでCustom Job spec表示まで

まだ本物のLightGBMやCatBoostを入れなくていいです。
まず 配線が勝ち です。

この判断で進めるなら、最終方針はこう固定できます。

Kaggleブロンズ第一優先。
過去GCP資産を流用。
GCP/Vertexは本番MLOpsではなく、Kaggle実験ランナーとして使う。
新規実装は vertex_run.py に絞る。
Feature Store / Pipelines / Endpoint / Model Registry / Monitoring は禁止。
1コマンドUXを品質ゲートにする。

かなり良いです。
これは 過去資産活用 × Kaggleブロンズ × Vertex-ready の判断として筋が通っています。
