# 第3回 解答

## 演習

### 第1回（素のLLM）と第3回（エージェント）の回答の違い

同じ質問「AIE2026の講座の宿題にある『3レベル』とは何ですか？」を、第1回の `app.ask` と第3回の `app.agent` に入力して比較した。

第1回の `app.ask` は講座固有の用語集を参照できないため、「3レベル」を一般的な3段階の難易度別課題だと推測して回答した。回答には「可能性が非常に高い」という表現があり、講座資料を根拠にした説明ではなかった。

一方、第3回の `app.agent` は用語集検索ツールで講座固有の情報を確認し、「3レベル」は宿題の「基礎・実装・発展」を指し、そのうちどれか1つに取り組めば完了することを説明できた。素のLLMが一般知識から推測するのに対し、エージェントはツールで用語集を検索し、その結果を根拠に回答できる点が異なる。

### `--trace` で見えたツール呼び出し

質問「LoRAとQLoRAの違いは？」では、`search_glossary` がそれぞれ次の引数で呼び出された。

```text
[tool call] search_glossary({'query': 'LoRA'})
[tool call] search_glossary({'query': 'QLoRA'})
```

トレースでは `requests=2`、`tool_calls=2` だった。1回目のLLM呼び出しでツール利用を決め、検索結果を受け取った後、2回目のLLM呼び出しで最終回答を生成した。`requests` はLLMの呼び出し回数、`tool_calls` はツールの呼び出し回数を表す。

### 1つの質問でのLLM呼び出し回数

「LoRAとQLoRAの違いは？」では `requests=2` だった。第1回の `app.ask` はLLMに質問を1回渡して回答を生成するが、第3回の `app.agent` は次のようにツール実行を挟むため、複数回のLLM呼び出しが発生する。

```text
LLM → ツール → LLM
```

### 追加したツールとdocstringの説明

`app/tools.py` に `make_quiz(lecture: int) -> str` を追加した。このツールは指定した講義回の用語から1つを選び、その用語の意味を尋ねる復習問題と定義をJSON文字列で返す。該当する用語がない場合は、例外ではなく問題を作成できない旨の説明文を返す。

docstringには、指定回の用語から復習問題を作ること、確認問題・復習クイズ・第N回の問題を求められた場合に使うこと、`lecture` が講義回の番号であること、用語が見つからない場合の扱いを記載した。また、`app/agent.py` に次の登録を追加した。

```python
agent.tool_plain(tools.make_quiz)
```

`uv run python -m app.agent --list-tools` では、`search_glossary`、`get_lecture_summary`、`make_quiz` の3つが表示され、`make_quiz` のdocstringもツール説明として表示された。

次の質問を `--trace` 付きで実行した。

```bash
uv run python -m app.agent --trace "第2回の内容から確認問題を1問出して"
```

実際に次の呼び出しが確認できた。

```text
[tool call] make_quiz({'lecture': 2})
```

このときは `requests=2`、`tool_calls=1` だった。第2回の用語を使った問題と答えが返り、エージェントが最終回答を表示した。また、`lecture=0` の直接実行では例外が発生せず、該当する用語がない旨の説明文が返った。

### テスト結果

```text
$ uv run pytest -q
...............                                                          [100%]
15 passed in 4.88s
```

すべてのテストに成功した。

## 宿題

- 取り組んだレベル：実装
- やったこと：
  - `app/tools.py` に `save_learning_log(topic, note)` を追加し、学習記録をリポジトリ直下の `learning_log/` に JSON 形式で保存するようにした。
  - ファイル名には日時と UUID を使い、利用者の入力をパスに使わず、同じ時刻の記録も上書きしないようにした。
  - `app/agent.py` で保存ツールを `requires_approval=True` で登録し、ツールの docstring に保存時の用途と承認要件を記載した。
  - 承認待ちの呼び出しごとに CLI で確認し、`y` または `yes` 以外は拒否として、承認結果と会話履歴を渡してエージェントを再実行するようにした。
- 結果：
  - 承認されるまでは保存関数が実行されず、承認するとファイルが作成され、拒否するとファイルが作成されないことをテストで確認した。
  - 保存内容が JSON として読めることを確認した。`uv run python -m app.agent --list-tools` に `save_learning_log` が表示された。
  - `uv run pytest -q` は `18 passed`。
- 手作業による確認：
  - 学習記録の保存を依頼して `y` で承認したところ、`learning_log/20261108_141329_816610d00e454e7e943c7df72658a62a.json` が作成された。内容はテーマ「第3回 AIエージェントのモデル・ループ・ツール」、記録「理解度80」の JSON だった。
  - 別の保存依頼を `n` で拒否したところ、保存しない旨のメッセージが表示された。`find learning_log -maxdepth 1 -type f | wc -l` の結果は拒否前後とも `1` で、新しいファイルは作成されなかった。
- 気づき・疑問：
  - QuriとCodespacesのチャットでここまで実装できるのだと感動した。