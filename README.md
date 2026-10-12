# co_writer_crew

A crewAI project using JSON-first configuration.

## Running

```bash
crewai run
```

## Project Structure

- `agents/` - Agent definitions (JSONC)
- `crew.jsonc` - Crew definition with tasks and configuration
- `tools/` - Custom tools (Python)
- `knowledge/` - Knowledge files for agents

> **Note:** `custom:<name>` tool references execute `tools/<name>.py` as local
> Python code when the crew loads. Only run crew projects from sources you
> trust.

## 対話型で実行したいときは以下コマンドで実行

```bash
uv run main.py
```


本プロジェクト全体で使用している技術スタックの一覧です。

---

### 本プロジェクトの使用技術一覧

**1. プログラミング言語・ランタイム**

* **Python**
* バージョン: 3.13（クラウド実行環境ログ: 3.13.16）



**2. パッケージ・プロジェクト管理ツール**

* **uv**（高速 Python パッケージマネージャー）

**3. Web アプリケーションフレームワーク**

* **Streamlit**（チャット UI 構築および Web アプリ化）

**4. AI / LLM フレームワーク**

* **CrewAI**（マルチエージェントオーケストレーション）

**5. AI モデル・SDK**

* **Google Gemini**（LLM モデル: `gemini-3.5-flash-lite`, `gemini-1.5-flash`）
* **google-genai**（Google GenAI Native Provider）

**6. 外部サービス連携・API**

* **Google Docs API** (v1)（ドキュメント読み書き）
* **google-api-python-client**（Google API 呼び出しクライアント）
* **google-auth**（Google 認証ライブラリ）

**7. クラウドインフラ・ホスティング**

* **Streamlit Community Cloud**（Linux ベースの非同期 Web アプリ実行基盤）

**8. バージョン管理・コードリポジトリ**

* **Git**（ローカルバージョン管理）
* **GitHub**（リモートリポジトリおよび Streamlit Cloud 連携）

**9. 認証・セキュリティ・環境変数**

* **Google Cloud Platform (GCP) IAM Service Account**（Headless 用サービスアカウント鍵認証）
* **Streamlit Secrets**（TOML 形式での API キー・サービスアカウント JSON・ドキュメント ID 保持）

**10. 主な内部依存ライブラリ**

* **Pydantic**（CrewAI のデータ構造・バリデーション）
* **PyArrow**（Streamlit 内部データ処理用）

---

### バージョン情報について

現在判明している固定バージョンおよび要件（`requirements.txt`）で指定されている状態は以下の通りです。

* Python: `3.13.16`
* pyarrow: `25.0.1` / `24.x`
* その他のライブラリ（`streamlit`, `crewai`, `google-genai` 等）: デプロイ時に最新安定版が自動インストールされる形式（バージョン未固定）

もし現在ローカル環境またはクラウド環境に入っている各ライブラリの厳密なピン留めバージョン（例: `streamlit==1.xx.x` や `crewai==0.xx.x`）をすべて特定・固定したい場合は、PC の PowerShell で以下のコマンドを実行することで一覧を出力・確認できます。

```powershell
uv pip list

```