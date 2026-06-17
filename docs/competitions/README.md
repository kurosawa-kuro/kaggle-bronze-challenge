再調査後の結論は、前回より少し厳しめです。

**ROGII は「黒澤さんに最適なコンペ」ではありません。**
ただし、2026年6月17日時点で見える現行・近日コンペの中では、**メダル対象で、LightGBM中心の表形式スキルをまだ活かせる可能性がある、ほぼ唯一の本命候補**です。

したがって判断はこうです。

> **ROGII は挑戦すべき。
> ただし「本命」ではなく、「条件付きGo」。
> 6月中に Stellar Class で提出テンプレを固め、7月から ROGII に入るのが最も合理的。**

---

## 1. 重要な修正点

まず、要件側の「ブロンズ＝上位40%前後」は修正した方がいいです。

Kaggleのメダル閾値は参加チーム数で変わり、1000チーム超級ではブロンズが **Top 10%** になります。また、Playground / Getting Started / InClass 系では原則メダルは得られません。([DataCamp][1])

ROGII は少なくとも1000人超規模として扱うべきコンペです。第三者集計では ROGII は2,000人超の参加規模として掲載されており、ブロンズ目標は「上位40%」ではなく、**上位10〜15%に入る設計**に修正すべきです。([EntrantHub][2])

---

## 2. ROGII は黒澤さんに適切か

### 判定：条件付きで適切

ROGII は Featured / 賞金あり / メダル対象のコンペで、課題は水平坑井に沿った地質・TVTを予測するものです。賞金総額は $50,000、Entry deadline は **2026年7月29日**、Final submission deadline は **2026年8月5日** と確認できます。([I Programmer][3])

ただし、これは「普通のCSV表形式回帰」ではありません。TVTは地層内での相対位置を表す値で、gamma ray log、坑井軌跡、typewell などを使って、水平坑井上の位置を推定する問題です。時系列・空間・地質アライメントの性質が強く、単純な行ごとの回帰よりも、well単位の分割、深度方向の特徴量、typewellとの対応づけが重要になります。([Zenn][4])

つまり、黒澤さんとの相性はこうです。

| 観点          |    判定 | コメント                                 |
| ----------- | ----: | ------------------------------------ |
| メダル対象か      |     ◎ | Featured / 賞金あり / medals対象。ここは条件に合う  |
| 48時間初回提出    |     ○ | 可能。ただしNotebook提出対応が先に必要              |
| LightGBM主軸  |     ○ | 使える。ただしLightGBM単体では上位に届きにくい可能性       |
| 純粋な表形式      |     △ | well・深度・空間・曲線アライメント問題に近い             |
| 黒澤さんの強みとの相性 |     ○ | リーク防止、GroupKFold、特徴量スキュー防止の意識はかなり活きる |
| ブロンズ難易度     | △〜やや高 | Top10%想定。上位40%目標では不足                 |

前回のタスク方針は大筋維持でよいですが、**「ROGIIをLightGBMで雑にbaseline」では危険**です。勝負所はモデルよりも CV と特徴量です。

---

## 3. ROGII で特に注意すべき罠

ROGII は kernel-only / Code Competition 型として扱うべきです。少なくとも公開情報では、提出時に見えている小さなテストセットが本番テストに差し替わる形式で、ハードコードやtarget leakが罠になると指摘されています。Kaggle CLI も code competition では `kaggle competitions submit -k <kernel>` のように kernel / notebook 経由の提出をサポートしています。([artgor][5])

そのため、現在のタスク順は少し直した方がいいです。

### 修正版タスク優先度

| 優先 | タスク                                | 修正後の内容                                                                 |
| -: | ---------------------------------- | ---------------------------------------------------------------------- |
|  1 | **KGL-002 Kaggle Notebook submit** | ROGIIがNotebook提出前提でも詰まらないよう、最初にNotebook提出フローを確立                        |
|  2 | **KGL-001 ROGII baseline**         | local CSV baselineではなく、kernel-safe LightGBM baselineを作る                |
|  3 | **KGL-003 CV design**              | GroupKFold / well単位 / typewell単位 / 深度順featureを検証                       |
|  4 | **KGL-006 ROGII feature pack**     | GR rolling、lag、depth差分、XYZ距離、typewell alignment、IDW系特徴量を追加             |
|  5 | **KGL-004 run logging**            | SQLiteに run_id, cv_score, lb_score, params, timestamp, feature_set を記録 |
|  6 | **KGL-005 bronze monitor**         | Top10〜15%を基準にCV/LBを監視                                                  |
|  7 | **KGL-007 public notebook audit**  | 公開Notebookの特徴量・CV・提出形式を吸収。ただしリーク系は使わない                                 |

ROGIIでは、公開Notebookや参加者メモでも GroupKFold by well、IDW特徴量、LightGBM residual、typewell alignment などが触れられています。別ソースでは、単発LightGBMは中位にとどまり、上位は粒子フィルタ、multi-model stacking、dynamic warping 的な工夫に寄っているという観測もあります。([artgor][5])

なので、ROGIIでブロンズを狙うなら、**「LightGBM上級者」だけではなく、「リークしない地質系列CVを組める人」として戦う**のが正しいです。

---

## 4. 他候補の再評価

現行・近日のKaggle/AIコンペ一覧を見ると、メダル対象っぽい本戦はありますが、かなりの数がゲーム、RL、画像、音声、LLM/Agent、AGI系です。CLISTやEntrantHub上でも、ROGII、Orbit Wars、AI Agent Security、ARC Prize、Leonardo、NeuroGolf、Hull Tactical、Playground Stellar などが確認できます。([CLIST][6])

黒澤さんの今回の要件に照らすと、こうなります。

| 候補                                              | 判定       | 理由                                                                      |
| ----------------------------------------------- | -------- | ----------------------------------------------------------------------- |
| **ROGII - Wellbore Geology Prediction**         | **本命**   | メダル対象、締切が8月5日、LightGBMを活かせる余地あり。ただし純粋表形式ではない                            |
| **Predicting Stellar Class / Playground S6E6**  | **練習用A** | 表形式・分類・LightGBM/CatBoost/XGBoost向き。ただしPlaygroundなのでメダル対象外。締切は6月30日      |
| **Hull Tactical - Market Prediction**           | 見送り      | 金融・表形式寄りで興味は合うが、2026年6月中旬で実質終盤。来月開始の本命には遅い                              |
| **AI Agent Security - Multi-Step Tool Attacks** | 除外       | OpenAI/Google/IEEE系で面白いが、Agent攻撃探索コンペ。今回の「LLM/RAGなし・LightGBM表形式」から外れる   |
| **Pokémon TCG AI Battle Challenge**             | 除外       | 2026年6月16日開始のAIエージェント/ゲーム系。Kaggleではあるが、表形式ブロンズ戦略ではない ([heroz.co.jp][7]) |
| **Orbit Wars / Maze Crawler**                   | 除外       | ゲーム・RL・シミュレーション寄り。48h表形式提出とは別競技                                         |
| **ARC Prize 2026 / NeuroGolf / Nemotron系**      | 除外       | AGI、推論、画像変換、最適化、LLM寄り。今回の非対象に該当                                         |
| **Leonardo Airborne Object Recognition**        | 除外       | 画像・動画・物体検出。今回の非対象                                                       |
| **BirdCLEF / CAFA系**                            | 除外       | 音声・バイオ・専門ドメインが強く、現時点の本命には不適                                             |

この中で、**黒澤さんの「Kaggleブロンズ」要件に本当に残るのは ROGII だけ**です。
ただし、ROGIIが理想だから残ったのではなく、**他の現行メダル対象がもっと外れているから残った**、という理解が正確です。

---

## 5. Predicting Stellar Class はどう使うべきか

Stellar Class は、黒澤さんのスキルにはかなり合います。天体を GALAXY / STAR / QSO に分類する多クラス分類で、balanced accuracy 系の表形式タスクとして扱えます。LightGBM、XGBoost、CatBoost、Optuna、特徴量エンジニアリングの練習には向いています。([LinkedIn][8])

ただし、Playgroundなのでメダル対象外です。ここで上位に入っても、今回の目的である Kaggle bronze には直接つながりません。([DataCamp][1])

使い方はこうです。

| 期間               | 目的                               |
| ---------------- | -------------------------------- |
| 2026年6月17日〜6月30日 | Stellar Classで48h提出テンプレを完成させる    |
| 2026年7月1日〜7月7日   | ROGIIのデータ構造、提出形式、baseline、CVを固める |
| 2026年7月8日〜7月29日  | ROGIIの特徴量とCV改善                   |
| 2026年7月30日〜8月5日  | 最終提出2本、CV最良とLB最良を選ぶ              |

Stellarで作るべきものは、順位狙いではなく、**Kaggle作業の型**です。

* `uv` 環境構築
* EDA notebook
* LightGBM / CatBoost / XGBoost baseline
* Optuna 30試行
* SQLite run log
* submission generation
* Kaggle Notebook push / submit
* CV最良とLB最良の2本管理

これをStellarで完成させてからROGIIに入ると、ROGIIの48時間初回提出リスクがかなり下がります。

---

## 6. ROGIIに行く場合の勝ち筋

ROGIIで黒澤さんが狙うべき勝ち筋は、これです。

### やるべきこと

| 領域     | 内容                                                  |
| ------ | --------------------------------------------------- |
| CV     | well単位 GroupKFold を基本にする                            |
| リーク防止  | target exposed rows、test placeholder、深度順の未来情報混入を避ける |
| 基本特徴量  | GR、MD/TVD、XYZ、深度差分、軌跡差分、rolling、lag                 |
| 空間特徴量  | 近傍well、typewellとの距離、IDW的な補間特徴量                      |
| アライメント | horizontal well と typewell の対応、深度方向のズレ補正            |
| モデル    | LightGBM主軸、CatBoost/XGBoostは薄い平均                    |
| ログ     | CV、LB、fold別、feature_set、paramsをSQLiteへ保存            |

### やらない方がいいこと

| 避けること                                   | 理由                               |
| --------------------------------------- | -------------------------------- |
| いきなり凝ったアーキテクチャ                          | Kaggleでは速度負けする                   |
| Public LBだけを見る                          | ROGIIはCV設計が崩れるとPrivateで落ちる可能性が高い |
| target leakっぽい公開Notebookを雑に吸収           | Code Competition型で罠になりやすい        |
| 地質ドメインを深掘りしすぎる                          | ブロンズ狙いでは時間対効果が悪い                 |
| Particle filter / DTW / stackingを初手からやる | 48h初回提出の目的から外れる                  |

---

## 7. Go / No-Go 基準

ROGIIに本格投入するかは、最初の48〜72時間で判定できます。

| 判定項目       | Go条件                           | No-Go寄りの兆候        |
| ---------- | ------------------------------ | ----------------- |
| Notebook提出 | 1回通る                           | Notebook提出で詰まり続ける |
| CV         | well単位CVが安定して回る                | Foldごとのスコアが極端に暴れる |
| LB         | baselineが極端に沈まない               | 公開baselineより明確に弱い |
| 特徴量        | rolling / lag / spatialでCV改善する | 何を足しても改善しない       |
| リーク管理      | CVとLBの方向が大きく矛盾しない              | LBだけ良くCVが壊れる      |
| 順位         | 初期で中位、改善後に上位20〜30%が見える         | 1週間で下位半分から抜けない    |

目安として、**7月第1週に提出完了、7月第2週に上位30%圏が見えない場合は、ブロンズ狙いとしては危険信号**です。
逆に、CV改善がLBにも反映され、上位20〜30%まで行けるなら、7月後半にTop10〜15%を狙う価値があります。

---

## 8. 更新後の推奨ロードマップ

### 6月17日〜6月30日：Stellarで練習

目的はメダルではなく、**提出パイプラインの完成**です。

| 優先 | タスク                             |
| -: | ------------------------------- |
|  1 | Stellar ClassでLightGBM baseline |
|  2 | Optuna 30試行                     |
|  3 | SQLite run log                  |
|  4 | CatBoost / XGBoost平均            |
|  5 | Kaggle Notebook submit練習        |
|  6 | CV最良・LB最良の2本管理                  |

### 7月1日〜7月7日：ROGII初回提出

| 優先 | タスク                                     |
| -: | --------------------------------------- |
|  1 | ROGIIのNotebook提出フロー確認                   |
|  2 | データ構造、well、typewell、depth、target mask確認 |
|  3 | GroupKFold baseline                     |
|  4 | LightGBM最小回帰                            |
|  5 | 1回目提出                                   |
|  6 | SQLiteにrun記録                            |

### 7月8日〜7月29日：ROGII改善

| 優先 | タスク                          |
| -: | ---------------------------- |
|  1 | rolling / lag / depth順特徴量    |
|  2 | XYZ / distance / typewell特徴量 |
|  3 | Public Notebookの安全な特徴量だけ吸収   |
|  4 | Optuna 30〜50試行               |
|  5 | CatBoost / XGBoost平均         |
|  6 | Top10〜15%監視                  |

### 7月30日〜8月5日：最終提出

| 優先 | タスク                    |
| -: | ---------------------- |
|  1 | CV最良モデルを固定             |
|  2 | LB最良モデルを固定             |
|  3 | Notebook再実行性確認         |
|  4 | 最終提出2本選択               |
|  5 | Private落ちしそうなリーク系提出を除外 |

---

## 9. 最終判断

黒澤さんにとって、ROGIIは**適切だが、楽な相手ではありません**。

前回の結論を修正すると、こうです。

> **ROGIIは本命。ただし「表形式LightGBMでブロンズを取りやすいコンペ」ではなく、
> 「現行メダル対象の中で、黒澤さんのリーク防止・CV設計・LightGBM経験が最も活きるコンペ」。**

他候補は、現時点では明確に弱いです。

* Stellar Class：練習には最適、メダルには不適
* Hull Tactical：興味は合うが、時期が遅い
* AI Agent Security / Pokémon / Orbit Wars：別競技
* ARC / NeuroGolf / Leonardo / BirdCLEF：今回の非対象

したがって、行動方針はこれでよいです。

**6月中はStellarで型を作る。
7月からROGIIに入る。
ROGIIは48〜72時間でGo/No-Go判定。
続行するならTop40%ではなくTop10〜15%を狙う。**

タスクセットは、現在の5本に **KGL-006 feature pack** と **KGL-007 public notebook audit** を追加し、**KGL-002 Notebook submit を最優先に繰り上げる**のが妥当です。

[1]: https://www.datacamp.com/blog/kaggle-competitions-the-complete-guide?utm_source=chatgpt.com "Kaggle Competitions: The Complete Guide | DataCamp"
[2]: https://entranthub.com/competitions?utm_source=chatgpt.com "AI/ML Competitions | EntrantHub"
[3]: https://www.i-programmer.info/news/204-challenges/18870-drilling-for-oil-a-kaggle-contest.html?utm_source=chatgpt.com "Drilling For Oil - A Kaggle Contest"
[4]: https://zenn.dev/kkj/articles/06923d55516152 "Kaggleコンペ紹介: ROGII - Wellbore Geology Prediction"
[5]: https://andlukyane.com/blog/minimax-m27-workflows "Testing MiniMax M2.7 via API on three real ML and coding workflows – Andrey Lukyanenko"
[6]: https://clist.by/?utm_source=chatgpt.com "CLIST"
[7]: https://heroz.co.jp/release/2026/06/16_press01-5/?utm_source=chatgpt.com "ポケモンカードゲームのプレイを競う、AIエージェントの開発コンテストを開催！～「ポケモンカードゲーム AI Battle Challenge」を6月16日（火）より開催！～ - HEROZ株式会社（ヒーローズ）"
[8]: https://pk.linkedin.com/in/hammadfarooq-ai?utm_source=chatgpt.com "Hammad Farooq - Kaggle | LinkedIn"
