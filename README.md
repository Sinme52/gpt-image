# gpt-image

English | [日本語](README.ja.md)

A Claude skill that lets Claude create images with OpenAI's GPT Image. The default model is GPT Image 2.5 (`gpt-image-2.5-sunburst`). Use `--model` to pick the faster `gpt-image-2.5-flare` or another model. GPT Image 2.6 is not the default for now, because it can add a haze to images even with `complexity` set to `low`. To use it, pass `--model gpt-image-2.6-sunburst`.

- Makes drafts at `medium` quality by default
- Generates from your own images, such as a character sheet or a pose reference (`edit`, up to 16 images)
- Ask for a "release" version, and it redraws a `medium` image at `xhigh` quality while keeping the composition
- Runs on the Python standard library only (nothing extra to install)

Want a character in a specific pose? Use it together with [Pose Doll](https://github.com/Sinme52/pose-doll), which uses this skill's `edit`.

## Contents

```
gpt-image/
├── SKILL.md              # instructions for Claude
├── scripts/gpt_image.py  # generate / edit / release
└── .env.example
```

## Install

First, get the files:

```bash
git clone https://github.com/Sinme52/gpt-image.git
cd gpt-image
```

### claude.ai (also loaded automatically in Claude Code cloud sessions)

1. Download [`gpt-image.zip`](https://github.com/Sinme52/gpt-image/raw/main/gpt-image.zip) from this repository, or build it yourself from the `gpt-image` folder:

   ```bash
   zip -r gpt-image.zip gpt-image -x '*/.env' '*/__pycache__/*' '*.DS_Store'
   ```

2. Upload the zip in claude.ai under Settings > Capabilities > Skills.

### Claude Code (local)

```bash
cp -r gpt-image ~/.claude/skills/
```

## API key

The skill looks for the key in this order:

1. The environment variable `OPENAI_IMAGE_API_KEY`
2. A `.env` file in the skill folder
3. A `.env` file in the directory you ran the script from

See `.env.example` for the format. `.env` is excluded by `.gitignore`.

### Claude Code cloud environments

In the cloud environment settings:

- **Environment variables**: `OPENAI_IMAGE_API_KEY=sk-...`
- **Network access**: choose Custom and add `api.openai.com` to Allowed domains (it is not in the default Trusted list)

## Usage

Just ask Claude.

- "Make an illustration of a café on a rainy night" → a draft at `medium`
- "Make this a release version" → finished at `xhigh`

You can also run the script directly.

```bash
# Draft (medium)
python3 gpt-image/scripts/gpt_image.py generate --prompt "..." --size 1536x1024

# Generate from reference images (medium). Refer to the input images in the prompt as IMAGE 1, IMAGE 2, ...
python3 gpt-image/scripts/gpt_image.py edit --image character.png --image pose.png \
  --prompt "Draw the character from IMAGE 1 in the pose of IMAGE 2 ..." --n 2 --release-prompt "a knight walking to the left"

# Release (xhigh). The prompt and size come from the draft's sidecar JSON (for an edit result, the --release-prompt text)
python3 gpt-image/scripts/gpt_image.py release --image gpt-image-outputs/draft-xxxx.png
```

Main options: `--model gpt-image-2.5-flare` (faster), `--complexity low|medium|high` (how much planning the model does before drawing; GPT Image 2.6 only), `--background transparent`, `--n 2`, `release --mode regenerate` (redraw from the prompt without the source image), `release --quality max`.

`complexity` applies only to GPT Image 2.6. With 2.6 it defaults to `low` for `generate`, `edit` and `release`, and changes only when you pass `--complexity`. It is never sent to the default 2.5 (the API returns a 400 error).

If the draft's sidecar records a model, `release` finishes with that model (pass `--model` to use another). A draft made with 2.6 is finished with 2.6.

## Tests

The tests run the CLI against a local server that imitates the API, and check what it sends and saves (no network, no charges).

```bash
python3 -m unittest discover -s tests
```

## Moving from the old skill

The skill was renamed from `gpt-image-2-5`. After you install the new `gpt-image`, delete the old `gpt-image-2-5` (if both are installed, which one runs is not defined).

## Notes

- API usage is billed to your OpenAI account. `xhigh` takes much more time and costs much more than `medium`.
- We recommend creating a key just for this skill, limiting it to image generation, and setting a budget limit.

## License

[MIT License](LICENSE)
