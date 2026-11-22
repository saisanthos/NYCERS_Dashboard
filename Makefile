RAW ?= data/raw/nycers_holdings_20251008.csv

data:      ## Clean the raw CSV into data/processed/
	PYTHONPATH=src python -m nycers.clean --raw $(RAW)

notebook:  ## Re-run the analysis notebook and regenerate figures
	jupyter nbconvert --to notebook --execute --inplace notebooks/nycers_analysis.ipynb

app:       ## Launch the dashboard
	streamlit run app/streamlit_app.py

test:
	pytest -q
