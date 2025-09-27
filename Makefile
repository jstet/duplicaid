.PHONY: setup-test teardown-test clean test-integration commit bump-patch bump-minor bump-major release

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

commit:
	uv run cz commit

bump-patch:
	uv run cz bump --increment PATCH

bump-minor:
	uv run cz bump --increment MINOR

bump-major:
	uv run cz bump --increment MAJOR

release: test-integration
	uv run cz bump --changelog
	uv build
	git push --follow-tags
	uv publish
