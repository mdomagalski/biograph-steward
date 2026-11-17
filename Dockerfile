ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}
ARG INSTALL_AWS=0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BIOGRAPH_HOST=0.0.0.0 \
    BIOGRAPH_PORT=8766 \
    BIOGRAPH_DATA_DIR=/data

RUN groupadd --gid 10001 steward \
    && useradd --uid 10001 --gid steward --create-home steward \
    && mkdir -p /app /data \
    && chown steward:steward /app /data
WORKDIR /app
COPY requirements-aws.txt /app/requirements-aws.txt
RUN if [ "$INSTALL_AWS" = "1" ]; then python -m pip install --no-cache-dir --require-hashes -r /app/requirements-aws.txt; fi
COPY --chown=steward:steward app.py LICENSE /app/
COPY --chown=steward:steward biograph_steward /app/biograph_steward
COPY --chown=steward:steward scripts /app/scripts
USER 10001:10001
EXPOSE 8766
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import ProxyHandler,build_opener; build_opener(ProxyHandler({})).open('http://127.0.0.1:8766/healthz', timeout=3).read()"
ENTRYPOINT ["python", "app.py"]
CMD ["serve", "--no-browser"]
