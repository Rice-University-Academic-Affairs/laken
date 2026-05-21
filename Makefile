.PHONY: build publish clean

clean:
	rm -rf dist

build: clean
	uv build

publish: build
ifndef PYPI_TOKEN
	$(error PYPI_TOKEN is not set)
endif
	uv run twine check dist/*
	@TWINE_USERNAME=__token__ TWINE_PASSWORD="$(PYPI_TOKEN)" uv run twine upload --non-interactive dist/*
