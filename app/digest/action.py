from __future__ import annotations

from app.pipeline.types import PipelineArticle

_TECHNICAL_CVE_ACTION = "Проверить версии ПО и применить патч/обновление."
_TECHNICAL_RULES: list[tuple[tuple[str, ...], str]] = [
    (("ransomware", "шифровальщик", "вымогател"), "Проверить резервные копии, сегментацию сети и EDR-покрытие."),
    (
        ("supply chain", "supply-chain", "npm", "pypi", "docker", "ci/cd", "cicd", "pipeline"),
        "Проверить зависимости и подписи сборок в CI/CD, закрепить версии/хэши.",
    ),
    (("phishing", "фишинг"), "Напомнить пользователям о признаках фишинга, проверить правила детектирования почты."),
    (
        ("iam", "s3", "bucket", "misconfig", "конфигурац"),
        "Проверить конфигурацию доступа (IAM/облачное хранилище) на избыточные права.",
    ),
]
_TECHNICAL_DEFAULT = "Оценить применимость к своей инфраструктуре и приоритизировать при необходимости."

_MANAGEMENT_CVE_ACTION = "Запросить у ИТ/ИБ статус патчинга и сроки устранения."
_MANAGEMENT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("ransomware", "шифровальщик", "вымогател"), "Оценить риск простоя и соответствие плану реагирования на инциденты."),
    (("штраф", "regulator", "регулятор", "fine", "gdpr"), "Проверить соответствие регуляторным требованиям и репутационные риски."),
]
_MANAGEMENT_DEFAULT = "Держать на контроле, обсудить на ближайшем статусе по ИБ-рискам."


def derive_action_line(article: PipelineArticle, audience: str) -> str:
    haystack = f"{article.title} {article.text}".lower()
    has_cve = any(tag.upper().startswith("CVE") for tag in (article.tags or []))

    if audience == "management":
        if has_cve:
            return _MANAGEMENT_CVE_ACTION
        for keywords, action in _MANAGEMENT_RULES:
            if any(k in haystack for k in keywords):
                return action
        return _MANAGEMENT_DEFAULT

    if has_cve:
        return _TECHNICAL_CVE_ACTION
    for keywords, action in _TECHNICAL_RULES:
        if any(k in haystack for k in keywords):
            return action
    return _TECHNICAL_DEFAULT
