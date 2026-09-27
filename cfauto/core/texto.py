"""Normalização de texto para busca: sem acentos, casefold e espaços simples."""

import unicodedata


def normalizar_texto(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())
