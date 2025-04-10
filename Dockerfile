FROM python:3.10 AS build

# Install Poetry
ENV POETRY_VERSION=1.8.4
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    /root/.local/bin/poetry config virtualenvs.create false

# Check version of Poetry
RUN /root/.local/bin/poetry --version

# Copy files
WORKDIR /usr/src/app
COPY taguette taguette
COPY po po
COPY pyproject.toml poetry.lock README.rst tests.py ./
RUN mkdir scripts
COPY scripts/update_translations.sh scripts/

# Install translation dependencies
RUN /root/.local/bin/poetry install --only=i18n

# Compile translations (Skipped)
# RUN scripts/update_translations.sh

# Generate requirements
RUN /root/.local/bin/poetry export -o requirements.txt --without=dev -E postgres


FROM python:3.10

ENV TINI_VERSION=v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini

# Install Calibre from Ubuntu distro
RUN apt-get update && \
    apt-get install -y --no-install-recommends calibre wv && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY --from=build /usr/src/app/requirements.txt requirements.txt
RUN pip --disable-pip-version-check install --no-cache-dir -r requirements.txt

# Copy files
WORKDIR /usr/src/app
COPY taguette taguette
COPY config.py config.py
COPY pyproject.toml poetry.lock README.rst tests.py ./

# Install app
RUN pip --disable-pip-version-check install --no-deps -e .

# Copy translation from other stage (Skipped)
# COPY --from=build /usr/src/app/taguette/l10n taguette/l10n

VOLUME /data
ENV HOME=/data
EXPOSE 7465
ENTRYPOINT ["/tini", "--", "taguette", "--no-browser", "server", "config.py"]
CMD []
