# GitHub Actions Agent Guide

`.github` 配下、特に workflow YAML を編集する時だけ読む。

## YAML Rules

- 編集後はPyYAMLで構文確認する。

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/<file>.yml', encoding='utf-8'))"
```

- `jobs` キーと `on` キー（PyYAMLでは `True` として扱われる場合あり）が存在することを確認する。
- GitHub Actions の `run: |` ブロックにマルチラインPythonを埋め込まない。
- Pythonを使う場合は単一行 `python3 -c "import sys,json; ..."` にするか、外部スクリプトを呼ぶ。
- APIキーやRailwayシークレットをworkflowに直書きしない。
