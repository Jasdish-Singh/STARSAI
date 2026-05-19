# STARSAI — reproducible build (FR-034).
# One-command rebuild: `make all`
# Stage targets are independent and rerunnable.

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
P := $(PYTHON) pipeline

.PHONY: help install bronze silver gold ml score public route all clean clean-artifacts

help:
	@echo "STARSAI build targets:"
	@echo "  make install       — install requirements"
	@echo "  make all           — full rebuild: bronze→silver→gold→ml→score→public"
	@echo "  make bronze        — download + preprocess raw sources"
	@echo "  make silver        — clean/enrich silver layer"
	@echo "  make gold          — H3 + spatial joins + OSM + equity"
	@echo "  make ml            — weak labels + calibrated logistic regression"
	@echo "  make score         — static + dynamic safety scores"
	@echo "  make public        — provenance.json + scores.json + GeoJSON + CSV"
	@echo "  make route         — street graph + edge weights (optional)"
	@echo "  make clean         — remove silver/gold/scores/public outputs"

install:
	$(PIP) install -r pipeline/requirements.txt

bronze:
	$(P)/ingest.py
	$(P)/preprocess.py
	$(P)/bronze_statcan.py

silver:
	$(P)/silver_crime.py
	$(P)/silver_poles.py
	$(P)/silver_311.py
	$(P)/silver_osm.py
	$(P)/silver_statcan.py

gold:
	$(P)/gold_h3.py
	$(P)/gold_joins.py
	$(P)/gold_osm.py
	$(P)/gold_equity.py

ml:
	$(P)/ml_labels.py
	$(P)/ml_train.py

score:
	$(P)/score.py
	$(P)/score_dynamic.py

public:
	$(P)/provenance.py
	$(P)/pack.py

route:
	$(P)/route_graph.py
	$(P)/route_weights.py

all:
	$(MAKE) install
	$(MAKE) bronze
	$(MAKE) silver
	$(MAKE) gold
	$(MAKE) ml
	$(MAKE) score
	$(MAKE) public

clean-artifacts:
	rm -rf data/silver data/gold data/scores data/public

clean: clean-artifacts
	rm -rf data/bronze/crime_night.parquet data/bronze/manifest.json
