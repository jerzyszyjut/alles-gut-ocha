# Alles Gut OCHA

Project for humanitarian crisis data exploration, scoring, and visualization.


## Slides

Presentation slides are available in `slides.pdf` at the repository root.

## Authors

Contributors (from git history):

- Dominik Lau
- Jerzy Szyjut
- Maciej Krzyżanowski
- Hubert Malinowski

## Technical documentation

## Getting data

1. Download datasets from [our drive](https://drive.google.com/drive/folders/119UF38zKSD6lHwrBdllwuujHDMsiP7l-?usp=sharing) (source: HDX).
2. Extract files into the `data/` directory in the project root.

## Environment variables

Create a `.env` file with required API keys:

```bash
echo "ANTHROPIC_API_KEY=<PUT YOUR API KEY HERE>\n" > .env
echo "HDX_APP_IDENTIFIER=<PUT YOUR HDX API KEY HERE>" >> .env
```

## Run backend

```bash
uv run uvicorn api.main:app
```

## Run frontend

```bash
cd frontend && npm install && npm start
```

## Build documentation

```bash
cd docs && latexmk -pdf -interaction=nonstopmode documentation.tex
```
