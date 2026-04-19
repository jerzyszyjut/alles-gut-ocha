# Getting data

1. Get it from [our drive](https://drive.google.com/drive/folders/119UF38zKSD6lHwrBdllwuujHDMsiP7l-?usp=sharing) [source: HDX]
2. Extract to `data` in project directory

# Claude API

```
echo "ANTHROPIC_API_KEY=<PUT YOUR API KEY HERE>\n" > .env
echo "HDX_APP_IDENTIFIER=<PUT YOUR HDX API KEY HERE>" >> .env
```

# Running backend

```
uv run uvicorn api.main:app
```

# Running frontend

```
cd frontend && npm install && npm start
```

# Making docs

```
cd docs && latexmk -pdf -interaction=nonstopmode documentation.tex
```