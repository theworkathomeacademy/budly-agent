FROM python:3.12-slim

WORKDIR /app
RUN useradd -u 10001 -m -s /bin/bash appuser
RUN mkdir -p /app/src/budly_runtime /app/config/budly_runtime /app/config/tool_gateway
COPY src/budly_runtime/__init__.py src/budly_runtime/config.py src/budly_runtime/events.py src/budly_runtime/http_service.py src/budly_runtime/model.py src/budly_runtime/personality.py src/budly_runtime/preference_registry.py src/budly_runtime/production_knowledge.py src/budly_runtime/production_runtime.py src/budly_runtime/prompt.py src/budly_runtime/relationship_registry.py src/budly_runtime/session.py src/budly_runtime/tool_gateway.py /app/src/budly_runtime/
COPY config/budly_runtime/education-corpus-v0.1.json config/budly_runtime/personality-package-v0.1.json config/budly_runtime/runtime.production.example.json /app/config/budly_runtime/
COPY config/tool_gateway/tg-p05a-preference-registry.json config/tool_gateway/tg-p05b-relationship-fact-registry.json /app/config/tool_gateway/
COPY config/policies.json config/products.json /app/config/
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8791
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8791/v1/health', timeout=3)" || exit 1
ENTRYPOINT ["python", "-m", "src.budly_runtime.http_service"]
