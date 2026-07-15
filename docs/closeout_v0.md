# Agent Frontdoor v0 Closeout

## 実施済み

- 既存の`agent-frontdoor`を継承し、`intake.v0` schema、fail-closed validator、human-readable formatter、boundary drift detector、4つのread-only CLIを完成させた。
- fixtureを`positive: 30`、`negative: 40`、`drift: 20`へ固定し、必須12カテゴリとsafe controlを機械テスト化した。
- local editable installとinstalled CLIを検証した。CLIは`validate`、`card`、`explain`、`check-drift`の4つだけである。
- 同一20入力を承認済みlocal worker aliasへ1回ずつ渡し、raw output、fixed oracle、差分scorecardを保存した。worker回答はvalidatorへ反映していない。
- 独立Codex監査の3回のFAILをTDDで修正し、audited implementation commit `ab2b87ffb093a35bfb3eba816fbaf809316337f0`で最終PASSを得た。
- legacy v0.1 assetsは削除せずhistorical referenceとして明示した。

## 現在地

```text
FINAL_STATUS: COMPLETE

TESTS:
- total: 500
- pass: 500
- fail: 0

SAFETY:
- negative blocking recall: 25/25 = 1.00
- boundary drift recall: 16/16 = 1.00
- safe drift controls: 4/4 = 1.00
- forbidden execution paths: 0 in runtime source
- network calls: 0 in runtime source
- out-of-scope mutations: 0

WORKER SCORE:
- qwen-fast-mini: failed / cross-verified; 120s timeout; no retry; format 0.00
- gemma-fast-mini: partial / cross-verified; task class 0.90; risk recall 1.00; blocking recall 1.00; format 1.00

COMMIT:
- audited implementation: ab2b87ffb093a35bfb3eba816fbaf809316337f0
- final documentation commit: repository HEAD after this memo is committed

REMOTE:
- push not performed
- configured remote: none
```

- Package install: `.venv/bin/python -m pip install --no-deps --no-build-isolation -e .` = exit 0。
- CLI smoke: `validate/card/explain` = exit 0、intentional drift = exit 3。
- Independent audit: `docs/final_audit.md` = PASS / cross-verified。
- Assetization audit: PASS。schema、runtime contract、fixtures、tests、README、worker artifacts、scorecard、audit、closeoutはすべてproject内のdurable homeにある。

## 残タスク（優先順）

- なし。`NEXT: none`。
- deploy、push、public release、hook/settings integrationは本taskの禁止範囲であり、残タスクへ昇格していない。

## 判断履歴

- 2026-07-15 / Codex: 既存targetを再設計せず継承し、working v0を`schema/intake.v0.json`へ固定した。
- 2026-07-15 / Qwen `qwen-fast-mini`: 1回のworker evalが120秒でtimeout。retry contractに従い再試行せずfailure evidenceとして保存した。
- 2026-07-15 / Gemma `gemma-fast-mini`: 20件を分類。oracleとの差分は`eval-14`と`eval-18`の2件で、project-local scorecardへ保存した。
- 2026-07-15 / Independent Codex: delete、authority、UNKNOWN mutationのlexical fail-openとoverblockingを3回検出。各回をRED testで再現し、bounded patternとsafe controlで修正した。最終監査はPASS。
- 2026-07-15 / Codex: shared worker registry sourceは明示的な変更禁止境界のため更新せず、scorecardを`docs/worker_comparison_scorecard.yaml`へ限定した。
- 2026-07-15 / Codex: no new skill or global policy was created。手順と判断はdesign、README、audit、closeoutへmaterialize済みであり、assetization gapはない。
