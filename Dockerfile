FROM python:3.10-slim
RUN apt update && apt install libsystemd-dev
RUN pip install poetry
ADD pyproject.toml /app/pyproject.toml
WORKDIR /app/
RUN poetry install --no-dev
ADD entrypoint.sh /entrypoint.sh
ADD ./telegram_mailing_help /app/telegram_mailing_help
VOLUME /app/config
VOLUME /app/db
EXPOSE 23455
ENTRYPOINT ["/entrypoint.sh"]
