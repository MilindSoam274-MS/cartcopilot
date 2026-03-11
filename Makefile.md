infra:
	cd infra && docker compose up -d

catalog:
	python services/catalog-service/load_swiggy.py

index:
	python services/index-service/build_index.py

assistant:
	cd services/assistant-service && uvicorn src.main:app --port 8002 --reload

retrieval:
	cd services/retrieval-service && uvicorn src.main:app --port 8001 --reload

checkout:
	cd services/checkout-service && uvicorn src.main:app --port 8003 --reload

ui:
	cd ui && streamlit run app.py

stop:
	docker compose down

logs:
	docker compose logs -f

clean:
	rm -rf indexes/*