# gpt-image

[English](README.md) | 日本語

Claude から OpenAI の GPT Image を呼び出して画像を作る Claude スキルです。既定のモデルは GPT Image 2.5 (`gpt-image-2.5-sunburst`) で、`--model` で高速版の `gpt-image-2.5-flare` や他のモデルも指定できます。GPT Image 2.6 は `complexity` が `low` でも画像に「もや」が出ることがあるため、今は既定にしていません。使う場合は `--model gpt-image-2.6-sunburst` を指定してください。

- 通常は品質 `medium` で下書きを作成
- キャラ設定画やポーズ参照など、手元の画像を入力にした生成（`edit`、最大16枚）
- 「リリース用に」と頼むと、medium の画像を入力にして構図を保ったまま `xhigh` で再出力
- Python 標準ライブラリのみで動作（追加インストール不要）

## 構成

```
gpt-image/
├── SKILL.md            # Claude 向けの手順
├── scripts/gpt_image.py  # generate / edit / release
└── .env.example
```

## インストール

### claude.ai（Claude Code のクラウドセッションにも自動で読み込まれます）

1. このリポジトリの [`gpt-image.zip`](https://github.com/Sinme52/gpt-image/raw/main/gpt-image.zip) をダウンロードする。または `gpt-image` フォルダから自分で zip を作る

   ```bash
   zip -r gpt-image.zip gpt-image -x '*/.env' '*/__pycache__/*' '*.DS_Store'
   ```

2. claude.ai の 設定 > 機能 > スキル から zip をアップロード

### Claude Code（ローカル）

```bash
cp -r gpt-image ~/.claude/skills/
```

## API キーの設定

キーは次の順に探します。

1. 環境変数 `OPENAI_IMAGE_API_KEY`
2. スキルフォルダ直下の `.env`
3. スクリプトを実行したディレクトリの `.env`

`.env` の書式は `.env.example` を参照してください。`.env` は `.gitignore` で除外しています。

### Claude Code のクラウド環境で使う場合

クラウド環境の設定で次の 2 つを行います。

- **Environment variables**: `OPENAI_IMAGE_API_KEY=sk-...`
- **Network access**: Custom にして Allowed domains に `api.openai.com` を追加（既定の Trusted リストには含まれていません）

## 使い方

Claude に頼むだけで使えます。

- 「雨の夜の喫茶店のイラストを作って」→ medium で下書き
- 「これをリリース用にして」→ xhigh で仕上げ

スクリプトを直接実行することもできます。

```bash
# 下書き (medium)
python3 gpt-image/scripts/gpt_image.py generate --prompt "..." --size 1536x1024

# 参照画像を使って作る (medium)。入力画像はプロンプトの中で IMAGE 1, IMAGE 2 ... と呼ぶ
python3 gpt-image/scripts/gpt_image.py edit --image character.png --image pose.png \
  --prompt "Draw the character from IMAGE 1 in the pose of IMAGE 2 ..." --n 2 --release-prompt "a knight walking to the left"

# リリース (xhigh)。プロンプトとサイズは下書きのサイドカー JSON から引き継ぐ（edit の結果なら --release-prompt の文）
python3 gpt-image/scripts/gpt_image.py release --image gpt-image-outputs/draft-xxxx.png
```

主なオプション: `--model gpt-image-2.5-flare`（高速版）、`--complexity low|medium|high`（描く前の計画の量。GPT Image 2.6 のみ）、`--background transparent`、`--n 2`、`release --mode regenerate`（元画像を使わずプロンプトから再生成）、`release --quality max`。

`complexity` は GPT Image 2.6 だけの設定で、2.6 では `generate`・`edit`・`release` のすべてで既定が `low` になり、`--complexity` を指定したときだけ変わります。既定の 2.5 には送りません（API が 400 エラーを返すため）。

`release` は、下書きのサイドカーにモデルが記録されていれば、そのモデルで仕上げます（別のモデルにするなら `--model`）。2.6 で作った下書きは 2.6 のまま仕上がります。

## テスト

API を模した手元のサーバーに対して、CLI の送信内容と保存結果を確認します（ネットワーク・課金なし）。

```bash
python3 -m unittest discover -s tests
```

`gpt-image.zip` は `gpt-image/` フォルダと一致している必要があります。`gpt-image/` 内を変更したら、zip を作り直して確認し、コミットしてください。

```bash
python3 tools/check_zip.py --build
```

GitHub Actions（`.github/workflows/ci.yml`）が、`main` への push とプルリクエストのたびにテストと `python3 tools/check_zip.py` を実行します。zip が古い、ファイルが欠けている、`.env` やキーらしい文字列が入っている場合は失敗します。

## 旧スキルからの移行

`gpt-image-2-5` からスキル名が変わりました。新しい `gpt-image` をアップロードしたら、古い `gpt-image-2-5` は削除してください（両方あると、どちらが使われるか定まりません）。

## 注意

- API の利用料金は OpenAI アカウントに課金されます。`xhigh` は `medium` より大幅に時間とコストがかかります。
- このスキル専用のキーを作り、権限を画像生成に絞って予算上限を設定しておくことをおすすめします。

## ライセンス

[MIT License](LICENSE)
