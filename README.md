# 🚀 201_breakout — ブレイクアウト戦略

10日高値ブレイク・出来高急増・RSフィルターで銘柄をスキャンし、
エントリー後は毎日モニタリングして決済シグナルを Discord に通知します。

## 戦略概要（バックテスト 2015–2025）

| 項目 | 値 |
|---|---|
| 勝率 | 53% |
| プロフィットファクター | 1.25 |
| 平均保有日数 | 21日 |
| 損切りライン | エントリー価格 × 0.95 |

## スケジュール

| ワークフロー | 時刻 (JST) | 内容 |
|---|---|---|
| `scan.yml` | 平日 16:13 | ブレイクアウト銘柄スキャン |
| `monitor.yml` | 平日 08:06 / 15:49 | 保有ポジション監視・決済判定 |

## Secrets

| 名前 | 内容 |
|---|---|
| `DISCORD_WEBHOOK` | Discord の Webhook URL |
| `PAT_TOKEN` | 102_market_phase の market_phase.json 読み取り用 |
| `ANTHROPIC_API_KEY` | Claude API（銘柄コメント生成） |

## ファイル構成

```
201_breakout/
├── scan.py                    # エントリースキャン
├── monitor.py                 # ポジション監視・決済判定
├── claude_comment.py          # Claude API コメント生成
├── strategy_params.py         # 戦略パラメータ定義
├── utils.py                   # データ取得ユーティリティ
├── universe230.csv            # 対象銘柄リスト（230銘柄）
├── requirements.txt
└── .github/workflows/
    ├── scan.yml
    └── monitor.yml
```

## 主要ファイル

- `selected_positions_breakout.json` — スキャン結果（Actions が自動コミット）
- `positions.json` — 保有ポジション（手動または他ツールで管理）
