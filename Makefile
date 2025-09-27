.PHONY: setup-test teardown-test clean test-integration

setup-test:
	docker compose -f docker-compose.test.yml up -d
	sleep 30

teardown-test:
	docker compose -f docker-compose.test.yml down -v

clean:
	docker compose -f docker-compose.test.yml down -v
	docker system prune -f

test-integration: setup-test
	uv run pytest tests/ -m integration -v
	$(MAKE) teardown-test
